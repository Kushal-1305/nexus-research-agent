# agent/fetcher.py

import re
from datetime import datetime, timezone
from urllib.parse import urlparse
from typing import Optional

try:
    import trafilatura
    _HAS_TRAFILATURA = True
except ImportError:
    _HAS_TRAFILATURA = False

try:
    import requests as _requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False


def _extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc
    except Exception:
        return ""


def _fetch_with_trafilatura(url: str) -> Optional[str]:
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        return None
    text = trafilatura.extract(
        downloaded,
        include_comments=False,
        include_tables=True,
        no_fallback=False,
        favor_precision=False,
    )
    return text or None


def _fetch_with_requests(url: str) -> Optional[str]:
    if not _HAS_REQUESTS:
        return None
    try:
        headers = {"User-Agent": "DeepResearchAgent/1.0"}
        resp = _requests.get(url, timeout=10, headers=headers)
        resp.raise_for_status()
        html = resp.text
        html = re.sub(r"<(script|style)[^>]*>.*?</(script|style)>", " ", html, flags=re.S | re.I)
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        return text if len(text) > 100 else None
    except Exception:
        return None


def fetch_page(url: str, title: str = "") -> Optional[dict]:
    text: Optional[str] = None

    if _HAS_TRAFILATURA:
        text = _fetch_with_trafilatura(url)

    if text is None:
        text = _fetch_with_requests(url)

    if not text or len(text.strip()) < 50:
        return None

    return {
        "url":          url,
        "title":        title,
        "text":         text.strip(),
        "domain":       _extract_domain(url),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }


_FETCH_TIMEOUT_SECONDS = 20  # max wall-clock time to wait for the whole batch


def fetch_pages(search_results: list[dict], max_pages: int = 10) -> list[dict]:
    from concurrent.futures import ThreadPoolExecutor, wait

    targets = search_results[:max_pages]
    if not targets:
        return []

    def _fetch(result: dict) -> Optional[dict]:
        return fetch_page(result["url"], title=result.get("title", ""))

    pages: list[Optional[dict]] = [None] * len(targets)
    with ThreadPoolExecutor(max_workers=min(8, len(targets))) as pool:
        futures = {pool.submit(_fetch, r): i for i, r in enumerate(targets)}
        done, not_done = wait(futures.keys(), timeout=_FETCH_TIMEOUT_SECONDS)
        for fut in done:
            idx = futures[fut]
            try:
                pages[idx] = fut.result()
            except Exception:
                pass
        for fut in not_done:
            fut.cancel()

    return [p for p in pages if p is not None]
