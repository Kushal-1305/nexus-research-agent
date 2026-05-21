# agent/confidence.py
import re


def compute_confidence(answer: str, chunks: list[dict], sources: list[dict]) -> dict:
    """
    Compute a confidence score (0-100) for a research answer.

    Weighted components:
      40%  Citation density  — how many inline citations appear
      20%  Source diversity  — how many unique domains were used
      25%  Context relevance — average keyword-overlap score of selected chunks
      15%  Completeness      — word count proxy for answer depth
    """
    # 1. Citation density
    citations = re.findall(r'\[.+?(?:—|\|)\s*.+?\]\(https?://[^\)]+\)', answer)
    citation_score = min(len(citations) / 5.0, 1.0)

    # 2. Source diversity
    domains = {s.get("domain", "") for s in sources if s.get("domain")}
    diversity_score = min(len(domains) / 4.0, 1.0)

    # 3. Context relevance
    if chunks:
        avg_rel = sum(c.get("score", 0.0) for c in chunks) / len(chunks)
        relevance_score = min(avg_rel / 0.6, 1.0)
    else:
        relevance_score = 0.0

    # 4. Completeness
    words = len(answer.split())
    completeness_score = min(words / 250.0, 1.0)

    overall = (
        citation_score     * 0.40
        + diversity_score  * 0.20
        + relevance_score  * 0.25
        + completeness_score * 0.15
    )

    return {
        "overall":        round(overall * 100),
        "citations":      round(citation_score * 100),
        "diversity":      round(diversity_score * 100),
        "relevance":      round(relevance_score * 100),
        "completeness":   round(completeness_score * 100),
        "citation_count": len(citations),
        "source_count":   len(sources),
    }
