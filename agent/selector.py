# agent/selector.py

import re
from utils.tokens import truncate_to_chars
from agent.trust import get_trust_score

CHUNK_WORD_TARGET    = 350
CHAR_BUDGET          = 15_000
MAX_CHUNKS_PER_SOURCE = 2

_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "in", "on",
    "at", "to", "for", "of", "and", "or", "with", "what", "how",
    "why", "when", "who", "which", "that", "this", "it", "be",
    "do", "does", "did", "has", "have", "had", "not", "but"
}


def _split_into_chunks(text: str, target_words: int = CHUNK_WORD_TARGET) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current_parts: list[str] = []
    current_word_count = 0

    for para in paragraphs:
        para_words = len(para.split())
        if current_word_count + para_words > target_words * 1.5 and current_parts:
            chunks.append("\n\n".join(current_parts))
            current_parts = []
            current_word_count = 0
        current_parts.append(para)
        current_word_count += para_words
        if current_word_count >= target_words and current_parts:
            chunks.append("\n\n".join(current_parts))
            current_parts = []
            current_word_count = 0

    if current_parts:
        chunks.append("\n\n".join(current_parts))

    if len(chunks) == 1 and len(chunks[0].split()) > target_words * 2:
        words = chunks[0].split()
        chunks = []
        for i in range(0, len(words), target_words):
            chunks.append(" ".join(words[i:i + target_words]))

    return chunks


def _score_chunk(chunk: str, query: str) -> float:
    query_words = {
        w.lower() for w in re.findall(r"\w+", query)
        if w.lower() not in _STOPWORDS and len(w) > 2
    }
    if not query_words:
        return 0.0
    chunk_lower = chunk.lower()
    hits = sum(1 for w in query_words if w in chunk_lower)
    return hits / len(query_words)


def select_chunks(pages: list[dict], query: str) -> tuple[list[dict], list[dict]]:
    scored: list[tuple[str, dict, float, float]] = []
    for page in pages:
        domain = page.get("domain", "")
        trust  = get_trust_score(domain)
        chunks = _split_into_chunks(page["text"])
        for chunk in chunks:
            keyword = _score_chunk(chunk, query)
            # 75% keyword relevance + 25% source trust
            combined = keyword * 0.75 + trust * 0.25
            scored.append((chunk, page, combined, trust))

    scored.sort(key=lambda x: x[2], reverse=True)

    selected_chunks: list[dict] = []
    used_sources_order: list[dict] = []
    seen_source_urls: set[str] = set()
    source_chunk_counts: dict[str, int] = {}
    total_chars = 0

    for chunk_text, page, score, trust in scored:
        url = page["url"]
        if source_chunk_counts.get(url, 0) >= MAX_CHUNKS_PER_SOURCE:
            continue
        chunk_chars = len(chunk_text)
        if total_chars + chunk_chars > CHAR_BUDGET:
            remaining = CHAR_BUDGET - total_chars
            if remaining < 200:
                break
            chunk_text = truncate_to_chars(chunk_text, remaining)
            chunk_chars = len(chunk_text)

        selected_chunks.append({
            "text":        chunk_text,
            "url":         url,
            "title":       page.get("title", ""),
            "domain":      page.get("domain", ""),
            "score":       round(score, 4),
            "trust_score": round(trust, 2),
        })
        source_chunk_counts[url] = source_chunk_counts.get(url, 0) + 1
        total_chars += chunk_chars

        if url not in seen_source_urls:
            seen_source_urls.add(url)
            used_sources_order.append({
                "url":         url,
                "title":       page.get("title", ""),
                "domain":      page.get("domain", ""),
                "trust_score": round(trust, 2),
            })

        if total_chars >= CHAR_BUDGET:
            break

    return selected_chunks, used_sources_order
