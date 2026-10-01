"""Search provider failures remain distinguishable from successful empty searches."""
import logging
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core.web_research import SearchOutcome, WebResearcher, run_search


ROW = {"title": "Controlled", "url": "https://example.invalid", "snippet": "Controlled evidence"}


@pytest.fixture
def researcher(monkeypatch):
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    instance = WebResearcher()
    instance._rate_limit_gap = 0
    return instance


def provider(monkeypatch, rows=None, error=None):
    class FakeDDGS:
        def __init__(self, **kwargs):
            assert kwargs == {"timeout": 5}
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def text(self, query, **kwargs):
            assert kwargs == {"max_results": 5, "backend": "duckduckgo"}
            logging.getLogger("ddgs.engines").error("private query https://private.invalid sensitive response")
            logging.getLogger("httpcore.connection").debug("private HTTP request")
            if error:
                raise error
            return rows if rows is not None else []
    monkeypatch.setitem(sys.modules, "ddgs", SimpleNamespace(DDGS=FakeDDGS))


def test_success_is_grounded_and_cached(researcher, monkeypatch):
    provider(monkeypatch, [{"title": ROW["title"], "href": ROW["url"], "body": ROW["snippet"]}])
    first = researcher.search("controlled query")
    assert first.status == "success" and first.results == [ROW]
    assert first.has_results and first.event_status == "success"
    researcher.last_backend = "stale"
    assert researcher.search("controlled query") is first
    assert researcher.last_backend == "ddg"


def test_empty_is_successfully_executed_but_not_grounded(researcher, monkeypatch):
    provider(monkeypatch)
    outcome = researcher.search("controlled query")
    assert outcome.status == "empty" and not outcome.has_results
    assert outcome.event_status == "empty"
    assert "keine belastbaren" in outcome.failure_message
    assert researcher.search("controlled query") is outcome


def test_missing_dependency_does_not_use_legacy_provider(researcher, monkeypatch):
    monkeypatch.setitem(sys.modules, "ddgs", None)
    legacy = Mock()
    monkeypatch.setitem(sys.modules, "duckduckgo_search", SimpleNamespace(DDGS=legacy))
    outcome = researcher.search("controlled query")
    assert outcome.status == "dependency_missing" and outcome.error_type == "ModuleNotFoundError"
    assert outcome.event_status == "error" and not outcome.has_results
    legacy.assert_not_called()
    assert researcher._search_cache.get("controlled query:5") is None


@pytest.mark.parametrize("error,status", [(RuntimeError("sensitive query"), "error"),
    (ConnectionError("private URL"), "provider_unavailable"), (TimeoutError("private query"), "timeout")])
def test_provider_failures_are_not_empty_or_success(researcher, monkeypatch, caplog, error, status):
    provider(monkeypatch, error=error)
    with caplog.at_level(logging.DEBUG):
        outcome = researcher.search("controlled query")
    assert outcome.status == status and outcome.event_status == "error"
    assert not outcome.has_results and outcome.results == []
    assert "private" not in caplog.text and "sensitive" not in caplog.text
    assert "controlled query" not in caplog.text
    assert researcher._search_cache.get("controlled query:5") is None


def test_wrapped_timeout_is_classified():
    outer = RuntimeError("private outer", TimeoutError("private inner"))
    outcome = run_search(SimpleNamespace(search=Mock(side_effect=outer)), "controlled")
    assert outcome.status == "timeout"


def test_exception_cause_timeout_is_classified():
    outer = RuntimeError("sensitive outer")
    outer.__cause__ = TimeoutError("sensitive inner")
    outcome = run_search(SimpleNamespace(search=Mock(side_effect=outer)), "controlled")
    assert outcome.status == "timeout"


def test_rate_limit_is_provider_unavailable(researcher, monkeypatch):
    exception_type = type("RatelimitException", (Exception,), {})
    provider(monkeypatch, error=exception_type("sensitive response"))
    assert researcher.search("controlled query").status == "provider_unavailable"


def test_ddgs_no_results_does_not_prove_successful_empty(researcher, monkeypatch):
    exception_type = type("DDGSException", (Exception,), {})
    provider(monkeypatch, error=exception_type("No results found."))
    assert researcher.search("controlled query").status == "provider_unavailable"


@pytest.mark.parametrize("query", [None, 42, "", "  ", "/home/private/file", "C:\\private\\file"])
def test_invalid_query_never_calls_provider(researcher, monkeypatch, query):
    fake = Mock()
    monkeypatch.setitem(sys.modules, "ddgs", SimpleNamespace(DDGS=fake))
    outcome = researcher.search(query)
    assert outcome.status == "invalid_query" and outcome.event_status == "blocked"
    fake.assert_not_called()


@pytest.mark.parametrize("row", [{"title": "Only title", "url": "https://example.invalid"},
    {"title": "Unsafe", "url": "file:///private", "snippet": "text"}, {"snippet": "text"}])
def test_unusable_results_do_not_count_as_grounding(row):
    outcome = run_search(SimpleNamespace(search=Mock(return_value=SearchOutcome("success", [row], "ddg"))), "controlled")
    assert outcome.status == "error" and outcome.error_type == "InvalidSearchResults"
    assert not outcome.has_results


def test_serper_answer_box_is_supported(researcher, monkeypatch):
    researcher._serper_key = "test-placeholder"
    monkeypatch.setattr(researcher, "_search_serper", Mock(return_value=[
        {"title": "Quick Answer", "url": "", "snippet": "Controlled evidence"}]))
    outcome = researcher.search("controlled query")
    assert outcome.has_results and outcome.backend == "serper"


def test_boundary_rejects_legacy_list_and_absent_provider():
    assert run_search(None, "controlled").status == "provider_unavailable"
    outcome = run_search(SimpleNamespace(search=Mock(return_value=[ROW])), "controlled")
    assert outcome.status == "error" and outcome.error_type == "InvalidSearchOutcome"


@pytest.mark.parametrize("status", ["dependency_missing", "provider_unavailable", "error", "invalid_query", "timeout", "empty"])
def test_failure_status_cannot_be_grounded_by_stray_results(status):
    outcome = SearchOutcome(status, [ROW], "ddg")
    assert not outcome.has_results
    assert outcome.event_status != "success"


def test_content_field_is_valid_evidence():
    row = {"title": "Controlled", "url": "https://example.invalid", "content": "Controlled evidence"}
    outcome = run_search(SimpleNamespace(search=Mock(return_value=SearchOutcome("success", [row], "ddg"))), "controlled")
    assert outcome.has_results and outcome.results == [ROW]


def test_provider_logs_with_direct_handlers_are_suppressed(researcher, monkeypatch):
    from io import StringIO
    stream = StringIO()
    logger = logging.getLogger("ddgs.engines")
    handler = logging.StreamHandler(stream)
    logger.addHandler(handler)
    try:
        provider(monkeypatch, error=RuntimeError("sensitive content"))
        researcher.search("controlled query")
        assert stream.getvalue() == ""
    finally:
        logger.removeHandler(handler)


def test_successful_empty_serper_survives_missing_optional_fallback(researcher, monkeypatch):
    researcher._serper_key = "test-placeholder"
    monkeypatch.setattr(researcher, "_search_serper", Mock(return_value=[]))
    monkeypatch.setitem(sys.modules, "ddgs", None)
    outcome = researcher.search("controlled query")
    assert outcome.status == "empty" and outcome.backend == "serper"


@pytest.mark.parametrize("status,results", [("unknown", []), ([], []), ("success", None),
    ("empty", {}), ("error", "invalid")])
def test_boundary_rejects_malformed_contract(status, results):
    outcome = run_search(SimpleNamespace(search=Mock(return_value=SearchOutcome(status, results))), "controlled")
    assert outcome.status == "error" and outcome.error_type == "InvalidSearchOutcome"
    assert outcome.results == []


def test_boundary_strips_failure_results():
    outcome = run_search(SimpleNamespace(search=Mock(return_value=SearchOutcome("timeout", [ROW]))), "controlled")
    assert outcome.status == "timeout" and outcome.results == []


def test_real_provider_invalid_rows_are_error(researcher, monkeypatch):
    provider(monkeypatch, [{"title": "No evidence", "href": "file:///private", "body": "text"}])
    outcome = researcher.search("controlled query")
    assert outcome.status == "error" and outcome.error_type == "InvalidSearchResults"


def test_future_provider_logger_with_own_handler_cannot_leak(researcher, monkeypatch):
    from io import StringIO
    stream = StringIO()
    created = []
    class FakeDDGS:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def text(self, *args, **kwargs):
            logger = logging.getLogger("ddgs.new_provider_during_search")
            handler = logging.StreamHandler(stream)
            logger.addHandler(handler)
            logger.setLevel(logging.DEBUG)
            created.append((logger, handler))
            logger.error("private query https://private.invalid sensitive response")
            return []
    monkeypatch.setitem(sys.modules, "ddgs", SimpleNamespace(DDGS=FakeDDGS))
    try:
        assert researcher.search("controlled query").status == "empty"
        assert stream.getvalue() == ""
    finally:
        for logger, handler in created:
            logger.removeHandler(handler)


def test_transport_diagnostics_resume_after_search_failure(researcher, monkeypatch, caplog):
    provider(monkeypatch, error=RuntimeError("private content"))
    with caplog.at_level(logging.DEBUG):
        researcher.search("controlled query")
        logging.getLogger("httpcore.connection").warning("Unrelated HTTP diagnostic after search")
    assert "private" not in caplog.text
    assert "Unrelated HTTP diagnostic after search" in caplog.text


def test_existing_log_record_factory_is_preserved(researcher, monkeypatch):
    original = logging.getLogRecordFactory()
    calls = []
    def previous(*args, **kwargs):
        calls.append(args[0])
        record = logging.LogRecord(*args, **kwargs)
        record.custom_previous_factory = True
        return record
    monkeypatch.setattr(logging, "_logRecordFactory", previous)
    provider(monkeypatch)
    researcher.search("controlled query")
    record = logging.getLogRecordFactory()("unrelated", logging.INFO, __file__, 1, "diagnostic", (), None)
    assert record.custom_previous_factory
    assert "unrelated" in calls
    logging.setLogRecordFactory(original)


@pytest.mark.parametrize("worker", [False, True])
@pytest.mark.parametrize("failure", [False, True])
def test_page_fetch_http_content_is_scoped(researcher, monkeypatch, caplog, worker, failure):
    from core.web_research import _fetch_page_worker
    def request(*args, **kwargs):
        logging.getLogger("urllib3.connectionpool").warning("private URL private response")
        if failure:
            raise ConnectionError("private URL")
        return SimpleNamespace(text="controlled html", raise_for_status=lambda: None)
    monkeypatch.setitem(sys.modules, "requests", SimpleNamespace(get=request))
    monkeypatch.setitem(sys.modules, "trafilatura", SimpleNamespace(extract=lambda *a, **kw: "controlled text"))
    with caplog.at_level(logging.DEBUG):
        result = (_fetch_page_worker("https://example.invalid") if worker
                  else researcher.fetch_page("https://example.invalid"))
        logging.getLogger("urllib3.connectionpool").warning("Unrelated HTTP diagnostic after fetch")
    assert (result is None) == failure
    assert "private" not in caplog.text
    assert "Unrelated HTTP diagnostic after fetch" in caplog.text
