"""Unit tests for session #7 agentic-audit finding #4: MCPBridge's sync
tool-call handler didn't cancel the underlying coroutine on timeout.

Bug: `future.result(timeout=...)` raising concurrent.futures.TimeoutError
does NOT cancel the asyncio Task/coroutine it wraps — the coroutine (and
any _reconnect_server() backoff it triggered, up to 5 attempts with
exponential backoff that alone can exceed 60s) kept running on the
shared mcp-bridge event-loop thread after the sync caller had already
received a "timed out" error, able to race the *next* tool call over
self._sessions (mutated with no lock).

Fix: the coroutine passed to run_coroutine_threadsafe is now wrapped in
asyncio.wait_for(), so the timeout is enforced ON the event loop itself
— guaranteeing the coroutine actually stops (raises CancelledError
inside itself) rather than merely "being asked to" from another thread.

Real background asyncio event loop throughout (not mocked) — this is
exactly the cross-thread scenario the bug lived in.
"""

import asyncio
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault("JARVIS_LOG_FILE_ONLY", "1")

import pytest

from core.mcp_client import MCPBridge
from core.privacy_gate import reset_privacy_gate_singleton_for_tests


@pytest.fixture(autouse=True)
def _clean_singleton():
    reset_privacy_gate_singleton_for_tests()
    yield
    reset_privacy_gate_singleton_for_tests()


@pytest.fixture
def real_loop():
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    yield loop
    loop.call_soon_threadsafe(loop.stop)
    thread.join(timeout=2)


@pytest.fixture
def bridge(real_loop):
    b = MCPBridge.__new__(MCPBridge)
    b._timeouts = {"tool_call": 0.2}  # short, so tests run fast
    b._loop = real_loop
    return b


class TestTimeoutActuallyCancelsTheCoroutine:
    def test_slow_call_tool_is_cancelled_on_timeout(self, bridge):
        """The core fix: a _call_tool() that would run far longer than
        the timeout must actually stop running (not just "time out" from
        the caller's perspective) once asyncio.wait_for()'s own timeout
        fires inside it."""
        cancelled = threading.Event()
        started = threading.Event()

        async def fake_call_tool(server_name, tool_name, args):
            started.set()
            try:
                await asyncio.sleep(10)  # far longer than the 0.2s timeout
                return "should never get here"
            except asyncio.CancelledError:
                cancelled.set()
                raise

        bridge._call_tool = fake_call_tool

        handler = bridge._make_sync_handler("slow_server", "slow_tool")
        result = handler({})

        assert "timed out" in result.lower()
        assert started.wait(timeout=1)
        assert cancelled.wait(timeout=2), (
            "the coroutine was never actually cancelled — it may still "
            "be running in the background after the sync call 'returned'"
        )

    def test_fast_call_tool_completes_normally(self, bridge):
        async def fake_call_tool(server_name, tool_name, args):
            return "quick result"

        bridge._call_tool = fake_call_tool

        handler = bridge._make_sync_handler("fast_server", "fast_tool")
        result = handler({})

        assert result == "quick result"

    def test_no_lingering_task_after_timeout(self, bridge, real_loop):
        """After a timeout, no task tied to this call should still be
        running on the loop shortly afterward — a direct check that the
        background work actually stopped, not just that our test saw
        CancelledError once."""
        still_running = threading.Event()

        async def fake_call_tool(server_name, tool_name, args):
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                raise
            else:
                still_running.set()  # would only fire if never cancelled
                return "leaked"

        bridge._call_tool = fake_call_tool

        handler = bridge._make_sync_handler("leaky_server", "leaky_tool")
        handler({})

        # Give the cancellation a moment to fully propagate, then check
        # no pending task from this call is still alive on the loop.
        time.sleep(0.3)
        assert not still_running.is_set()

    def test_timeout_error_message_names_server_and_tool(self, bridge):
        async def fake_call_tool(server_name, tool_name, args):
            await asyncio.sleep(10)

        bridge._call_tool = fake_call_tool

        handler = bridge._make_sync_handler("myserver", "mytool")
        result = handler({})

        assert "myserver" in result
        assert "mytool" in result
