# agent/searcher.py

import os
from urllib.parse import urlparse
from tavily import TavilyClient
from agent.trust import is_blocked


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        return ""


def search(query: str, max_results: int = 7) -> list[dict]:
    client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    response = client.search(
        query=query,
        search_depth="basic",
        max_results=max_results,
        include_answer=False,
        include_images=False,
        include_raw_content=False,
    )
    results = []
    for item in response.get("results", []):
        results.append({
            "title":   item.get("title", ""),
            "url":     item.get("url", ""),
            "snippet": item.get("content", ""),
            "score":   item.get("score", 0.0),
        })
    return results


def search_all(queries: list[str], max_results_per_query: int = 5) -> list[dict]:
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _safe_search(query: str) -> list[dict]:
        try:
            return search(query, max_results=max_results_per_query)
        except Exception:
            return []

    raw: list[list[dict]] = [[] for _ in queries]
    with ThreadPoolExecutor(max_workers=len(queries)) as pool:
        futures = {pool.submit(_safe_search, q): i for i, q in enumerate(queries)}
        for fut in as_completed(futures):
            raw[futures[fut]] = fut.result()

    seen_urls: set[str] = set()
    all_results: list[dict] = []
    for results in raw:
        for r in results:
            url = r["url"]
            if url not in seen_urls and not is_blocked(_domain(url)):
                seen_urls.add(url)
                all_results.append(r)

    all_results.sort(key=lambda r: r["score"], reverse=True)
    return all_results
