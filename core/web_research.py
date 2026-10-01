"""
Web Research Module

Provides web search (Serper/Google primary, DuckDuckGo fallback) and page
content extraction (trafilatura) for LLM-driven web research via tool calling.

Thread-safe, error-resilient — never crashes the pipeline.
"""

import os
import re
import time
import threading
import logging
from functools import wraps
from dataclasses import dataclass, field
from urllib.parse import urlsplit
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Optional

from core.logger import get_logger


@dataclass
class SearchOutcome:
    """Per-call search evidence, separate from provider availability."""

    status: str
    results: list[dict] = field(default_factory=list)
    backend: Optional[str] = None
    error_type: Optional[str] = None

    @property
    def has_results(self) -> bool:
        return self.status == "success" and bool(_valid_results(self.results, self.backend))

    @property
    def event_status(self) -> str:
        if self.has_results:
            return "success"
        if self.status == "empty":
            return "empty"
        return "blocked" if self.status == "invalid_query" else "error"

    @property
    def failure_message(self) -> str:
        if self.status == "empty":
            return "Ich habe keine belastbaren Suchergebnisse gefunden."
        if self.status == "invalid_query":
            return "Diese Suchanfrage ist ungültig. Bitte formuliere eine öffentliche Websuche."
        return "Ich kann die aktuellen Informationen gerade nicht abrufen."


def _valid_results(results, backend=None) -> list[dict]:
    valid = []
    if not isinstance(results, list):
        return valid
    for row in results:
        if not isinstance(row, dict):
            continue
        snippet = row.get("snippet") or row.get("content")
        if not isinstance(snippet, str) or not snippet.strip():
            continue
        url = row.get("url", "")
        if not isinstance(url, str):
            continue
        try:
            parsed = urlsplit(url)
            public_url = parsed.scheme in {"http", "https"} and bool(parsed.hostname)
        except ValueError:
            public_url = False
        if not public_url and not (backend == "serper" and not url and row.get("title") == "Quick Answer"):
            continue
        valid.append({"title": str(row.get("title", "")), "url": url, "snippet": snippet})
    return valid


_PROVIDER_LOG_NAMES = ("ddgs", "duckduckgo_search")
_TRANSPORT_LOG_NAMES = ("httpx", "httpcore", "primp", "urllib3", "requests")
_SEARCH_LOG_CONTEXT = threading.local()


class _ProviderContentFilter(logging.Filter):
    def filter(self, record):
        provider_content = any(record.name == name or record.name.startswith(name + ".") for name in _PROVIDER_LOG_NAMES)
        search_transport = bool(getattr(_SEARCH_LOG_CONTEXT, "depth", 0)) and any(
            record.name == name or record.name.startswith(name + ".") for name in _TRANSPORT_LOG_NAMES)
        return not (provider_content or search_transport)


_PROVIDER_CONTENT_FILTER = _ProviderContentFilter()


def _quiet_provider_logs() -> None:
    """Protect source loggers, including children created by a later provider call.

    Provider messages are sensitive by definition. HTTP diagnostics are suppressed
    only within the current thread's search call. Existing factories and unrelated
    logging levels, handlers, propagation and HTTP diagnostics remain intact.
    """
    previous_factory = logging.getLogRecordFactory()
    if getattr(previous_factory, "_jarvis_search_boundary", False):
        return

    def factory(*args, **kwargs):
        record = previous_factory(*args, **kwargs)
        namespaces = _PROVIDER_LOG_NAMES + _TRANSPORT_LOG_NAMES
        if any(record.name == name or record.name.startswith(name + ".") for name in namespaces):
            source = logging.getLogger(record.name)
            if _PROVIDER_CONTENT_FILTER not in source.filters:
                source.addFilter(_PROVIDER_CONTENT_FILTER)
        return record

    factory._jarvis_search_boundary = True
    logging.setLogRecordFactory(factory)


def _search_log_boundary(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        _quiet_provider_logs()
        depth = getattr(_SEARCH_LOG_CONTEXT, "depth", 0)
        _SEARCH_LOG_CONTEXT.depth = depth + 1
        try:
            return function(*args, **kwargs)
        finally:
            _SEARCH_LOG_CONTEXT.depth = depth
    return wrapped


def _error_outcome(exc: Exception, backend=None) -> SearchOutcome:
    """Classify known technical failures without exposing exception messages."""
    errors = []
    current = exc
    while isinstance(current, BaseException) and id(current) not in {id(item) for item in errors}:
        errors.append(current)
        current = current.__cause__ or current.__context__
        if current is None:
            current = next((arg for arg in errors[-1].args if isinstance(arg, BaseException)), None)
    names = {type(item).__name__ for item in errors}
    if any(isinstance(item, ModuleNotFoundError) for item in errors):
        status = "dependency_missing"
    elif any(isinstance(item, TimeoutError) for item in errors) or names & {"Timeout", "TimeoutException", "ReadTimeout", "ConnectTimeout"}:
        status = "timeout"
    elif (any(isinstance(item, ConnectionError) for item in errors)
          or names & {"ConnectionError", "ConnectError", "RatelimitException", "NoResultsException"}
          or any(type(item).__name__ == "DDGSException" and str(item) == "No results found." for item in errors)):
        status = "provider_unavailable"
    else:
        status = "error"
    return SearchOutcome(status, backend=backend, error_type=type(exc).__name__)


def run_search(researcher, query, max_results=5) -> SearchOutcome:
    """Frontend boundary: absent or broken search providers fail honestly."""
    if researcher is None:
        return SearchOutcome("provider_unavailable")
    try:
        outcome = researcher.search(query, max_results=max_results)
        if not isinstance(outcome, SearchOutcome):
            return SearchOutcome("error", error_type="InvalidSearchOutcome")
        if (not isinstance(outcome.status, str)
                or outcome.status not in {"success", "empty", "dependency_missing", "provider_unavailable", "error", "invalid_query", "timeout"}
                or not isinstance(outcome.results, list)):
            return SearchOutcome("error", error_type="InvalidSearchOutcome")
        if outcome.status == "success":
            results = _valid_results(outcome.results, outcome.backend)
            if outcome.results and not results:
                return SearchOutcome("error", backend=outcome.backend, error_type="InvalidSearchResults")
            return SearchOutcome("success" if results else "empty", results, outcome.backend, outcome.error_type)
        return SearchOutcome(outcome.status, backend=outcome.backend, error_type=outcome.error_type)
    except Exception as exc:
        return _error_outcome(exc)


class _TTLCache:
    """Simple thread-safe TTL cache."""

    def __init__(self, ttl_seconds: int):
        self._ttl = ttl_seconds
        self._data: dict = {}
        self._lock = threading.Lock()

    def get(self, key: str):
        with self._lock:
            entry = self._data.get(key)
            if entry and (time.time() - entry[1]) < self._ttl:
                return entry[0]
            # Expired or missing
            self._data.pop(key, None)
            return None

    def put(self, key: str, value):
        with self._lock:
            self._data[key] = (value, time.time())

    def clear(self):
        with self._lock:
            self._data.clear()


@_search_log_boundary
def _fetch_page_worker(url: str, max_chars: int = 4000,
                       timeout: float = 4.0) -> Optional[tuple[str, str]]:
    """Fetch and extract page content in a subprocess (process-safe).

    Returns (url, extracted_text) on success, or None on failure.
    Must be a module-level function for ProcessPoolExecutor pickling.
    """
    try:
        import requests as _req
        import trafilatura

        resp = _req.get(url, timeout=timeout, headers={
            "User-Agent": "Mozilla/5.0 (compatible; research-bot/1.0)",
        })
        resp.raise_for_status()
        html = resp.text
        if not html:
            return None

        text = trafilatura.extract(html, include_links=False,
                                   include_tables=True,
                                   include_comments=False)
        if not text:
            return None

        return (url, text[:max_chars])
    except Exception:
        return None


class WebResearcher:
    """Web search and page content extraction for LLM tool calling."""

    def __init__(self, config=None):
        self.logger = get_logger(__name__, config)
        self._search_cache = _TTLCache(ttl_seconds=300)   # 5 min
        self._page_cache = _TTLCache(ttl_seconds=600)      # 10 min
        self._last_search_time = 0.0
        self._rate_limit_gap = 1.0  # seconds between searches
        self._serper_key = os.environ.get("SERPER_API_KEY")
        self.last_backend = None  # "serper" or "ddg" — set by search()
        self.last_search_stats = None  # Set after each search+fetch cycle
        if self._serper_key:
            self.logger.info("WebResearcher initialized (serper primary, ddg fallback)")
        else:
            self.logger.info("WebResearcher initialized (ddg only — no SERPER_API_KEY)")

    # Local filesystem path patterns — web search is never useful for these
    _LOCAL_PATH_RE = re.compile(
        r'(?:^|[ "\'(])(?:/home/|~/|/mnt/|/usr/|/etc/|/opt/|/var/|/tmp/|'
        r'\./|\.\./|file://|'
        r'[A-Z]:\\)',
    )

    def _search_serper(self, query: str, max_results: int = 5) -> list[dict]:
        """Search via Serper.dev (Google SERP). Returns same contract as search()."""
        import requests as _req

        resp = _req.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": self._serper_key},
            json={"q": query, "num": max_results},
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()

        results = []

        # Prepend answer box if present (instant answer)
        ab = data.get("answerBox")
        if ab:
            answer = ab.get("answer") or ab.get("snippet") or ab.get("title", "")
            if answer:
                results.append({
                    "title": "Quick Answer",
                    "url": "",
                    "snippet": answer,
                })

        # Prepend knowledge graph if present
        kg = data.get("knowledgeGraph")
        if kg and kg.get("description"):
            results.append({
                "title": kg.get("title", "Knowledge Graph"),
                "url": kg.get("website", ""),
                "snippet": kg["description"],
            })

        # Map organic results
        for r in data.get("organic", [])[:max_results]:
            results.append({
                "title": r.get("title", ""),
                "url": r.get("link", ""),
                "snippet": r.get("snippet", ""),
            })

        return results

    @_search_log_boundary
    def search(self, query: str, max_results: int = 5) -> SearchOutcome:
        """Return evidence and technical status for this call, never an error row."""
        self.last_backend = None
        self.last_search_stats = None
        if (not isinstance(query, str) or not query.strip()
                or not isinstance(max_results, int) or isinstance(max_results, bool)
                or max_results < 1 or self._LOCAL_PATH_RE.search(query)):
            return SearchOutcome("invalid_query")
        _quiet_provider_logs()

        # Check cache
        cache_key = f"{query}:{max_results}"
        cached = self._search_cache.get(cache_key)
        if cached is not None:
            self.last_backend = cached.backend
            self.logger.debug("Search cache hit")
            return cached

        # Rate limiting
        elapsed = time.time() - self._last_search_time
        if elapsed < self._rate_limit_gap:
            time.sleep(self._rate_limit_gap - elapsed)

        # A successful empty primary response remains evidence of a valid empty
        # search even if the optional fallback cannot run.
        empty_primary = None
        if self._serper_key:
            try:
                raw_results = self._search_serper(query, max_results)
                results = _valid_results(raw_results, "serper")
                if results:
                    self._last_search_time = time.time()
                    outcome = SearchOutcome("success", results, "serper")
                    self._search_cache.put(cache_key, outcome)
                    self.last_backend = "serper"
                    self.logger.info("Web search (serper): %d results", len(results))
                    return outcome
                if isinstance(raw_results, list) and not raw_results:
                    empty_primary = SearchOutcome("empty", backend="serper")
            except Exception as e:
                self.logger.warning("Serper search failed; DDG fallback (%s)", type(e).__name__)

        # Fallback: DuckDuckGo
        try:
            from ddgs import DDGS
            _quiet_provider_logs()

            self.logger.debug("Search exec (ddg): max_results=%d", max_results)
            results = []
            with DDGS(timeout=5) as ddgs:
                for r in ddgs.text(query, max_results=max_results, backend="duckduckgo"):
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "snippet": r.get("body", ""),
                    })

            raw_results = results
            results = _valid_results(raw_results, "ddg")
            self._last_search_time = time.time()
            if raw_results and not results:
                self.last_backend = "ddg"
                return SearchOutcome("error", backend="ddg", error_type="InvalidSearchResults")
            outcome = SearchOutcome("success" if results else "empty", results, "ddg")
            self._search_cache.put(cache_key, outcome)
            self.last_backend = "ddg"
            self.logger.info("Web search (ddg): %d results", len(results))
            return outcome

        except Exception as e:
            outcome = empty_primary or _error_outcome(e, "ddg")
            self.logger.error("Web search (ddg): status=%s error_type=%s", outcome.status, type(e).__name__)
            self._last_search_time = time.time()
            self.last_backend = outcome.backend
            if empty_primary is not None:
                self._search_cache.put(cache_key, outcome)
            return outcome

    @_search_log_boundary
    def fetch_page(self, url: str, max_chars: int = 4000,
                   timeout: float = 4.0) -> Optional[str]:
        """Fetch and extract main content from a web page.

        Uses requests for download (hard timeout) + trafilatura for extraction.

        Args:
            url: Page URL to fetch
            max_chars: Maximum characters to return (default 4000)
            timeout: HTTP request timeout in seconds (default 4.0)

        Returns:
            Extracted text content, or None on failure.
        """
        # Check cache
        cached = self._page_cache.get(url)
        if cached is not None:
            self.logger.debug("Page cache hit")
            return cached[:max_chars]

        try:
            import requests as _req
            import trafilatura

            # Use requests with hard timeout (trafilatura's timeout is unreliable)
            resp = _req.get(url, timeout=timeout, headers={
                "User-Agent": "Mozilla/5.0 (compatible; research-bot/1.0)",
            })
            resp.raise_for_status()
            html = resp.text
            if not html:
                self.logger.warning("Page fetch returned nothing")
                return None

            text = trafilatura.extract(html, include_links=False,
                                       include_tables=True,
                                       include_comments=False)
            if not text:
                self.logger.warning("Content extraction empty")
                return None

            # Cache full text, return truncated
            self._page_cache.put(url, text)
            self.logger.info("Page fetched (%d chars)", len(text))
            return text[:max_chars]

        except Exception as e:
            self.logger.error("Page fetch failed (%s)", type(e).__name__)
            return None

    def fetch_pages_parallel(self, results: list[dict], max_results: int = 5,
                             max_chars: int = 4000, timeout: float = 5.0,
                             min_chars: int = 300) -> list[str]:
        """Fetch page content from multiple search results concurrently.

        Args:
            results: Search results (each has 'title', 'url', 'snippet')
            max_results: Maximum number of pages to fetch
            max_chars: Max characters per page
            timeout: Hard wall-clock timeout for all fetches (seconds)
            min_chars: Minimum content length to include

        Returns:
            List of formatted page sections: "[Title] (url):\ncontent..."
        """
        urls = []
        for r in results[:max_results]:
            url = r.get("url", "")
            if url:
                urls.append((r.get("title", ""), url))

        if not urls:
            return []

        page_sections = []
        start = time.time()

        # ProcessPoolExecutor: each fetch runs in its own process to avoid
        # lxml/trafilatura SEGV from concurrent C-extension parsing in threads.
        pool = ProcessPoolExecutor(max_workers=len(urls))
        try:
            future_to_info = {
                pool.submit(_fetch_page_worker, url, max_chars, timeout - 1):
                    (title, url)
                for title, url in urls
            }
            self.logger.debug("Parallel fetch: %d URLs, timeout=%ds", len(future_to_info), timeout)
            try:
                for future in as_completed(future_to_info, timeout=timeout):
                    # Cooperative mid-step cancellation (session #8, see
                    # core/task_planner.py's current_cancel_event()):
                    # when this fetch is running as part of a plan step
                    # the user cancelled, stop waiting for further pages
                    # and return whatever was collected so far — a clean
                    # early exit, not a forced kill of in-flight
                    # subprocess fetches (cancel_futures=True in the
                    # finally block below still only cancels futures
                    # that haven't started running yet).
                    from core.task_planner import current_cancel_event
                    _cancel_evt = current_cancel_event()
                    if _cancel_evt is not None and _cancel_evt.is_set():
                        self.logger.info(
                            "Parallel fetch: cancelled — stopping with %d/%d pages collected",
                            len(page_sections), len(urls),
                        )
                        break
                    title, url = future_to_info[future]
                    try:
                        result = future.result(timeout=0.5)
                        if result:
                            fetched_url, page_text = result
                            if len(page_text) >= min_chars:
                                # Cache in parent process
                                self._page_cache.put(fetched_url, page_text)
                                page_sections.append(
                                    f"[{title}] ({url}):\n{page_text}"
                                )
                    except Exception as e:
                        self.logger.debug("Page fetch skipped (%s)", type(e).__name__)
            except TimeoutError:
                timed_out = len(future_to_info) - len(page_sections)
                self.logger.warning(
                    f"Parallel fetch: {timed_out} page(s) timed out, "
                    f"continuing with {len(page_sections)} collected"
                )
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

        elapsed = time.time() - start
        self.logger.info(
            f"Parallel fetch: {len(page_sections)}/{len(urls)} pages "
            f"in {elapsed:.1f}s"
        )
        self.last_search_stats = {
            "pages_ok": len(page_sections),
            "pages_total": len(urls),
            "fetch_latency_ms": round(elapsed * 1000),
            "backend": self.last_backend,
        }
        return page_sections

    def clear_cache(self):
        """Clear all caches (e.g. when conversation window closes)."""
        self._search_cache.clear()
        self._page_cache.clear()


def format_search_results(results: list[dict]) -> str:
    """Format search results as numbered text for LLM context.

    Args:
        results: List of search result dicts (title, url, snippet)

    Returns:
        Formatted string like:
        [1] Title - url
        Snippet text...

        [2] Title - url
        ...
    """
    if not results:
        return ("Keine Suchergebnisse gefunden. "
                "Teile mit, dass keine aktuellen Informationen zu diesem Thema gefunden wurden. "
                "Rate nicht und erfinde keine Antwort.")

    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] {r['title']} - {r['url']}")
        if r.get("snippet"):
            lines.append(f"    {r['snippet']}")
        lines.append("")
    return "\n".join(lines).rstrip()
