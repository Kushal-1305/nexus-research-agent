# agent/trust.py

# Domains that produce no extractable research content — skip entirely.
_BLOCKED_DOMAINS: set[str] = {
    "facebook.com", "instagram.com", "twitter.com", "x.com",
    "tiktok.com", "pinterest.com", "snapchat.com", "threads.net",
    "tumblr.com", "vk.com", "weibo.com", "t.me",
}

# Community platforms — allowed as sources, but trigger a warning when
# they are the only sources available for a question.
_COMMUNITY_DOMAINS: set[str] = {
    "reddit.com", "linkedin.com", "quora.com",
}

_DOMAIN_TRUST: dict[str, float] = {
    # Academic / Scientific
    "arxiv.org": 0.95,
    "nature.com": 0.98,
    "science.org": 0.98,
    "pubmed.ncbi.nlm.nih.gov": 0.98,
    "ncbi.nlm.nih.gov": 0.95,
    "scholar.google.com": 0.90,
    "jstor.org": 0.92,
    "springer.com": 0.90,
    "ieee.org": 0.92,
    "acm.org": 0.90,
    # Reference
    "wikipedia.org": 0.88,
    "britannica.com": 0.90,
    # International news
    "reuters.com": 0.92,
    "apnews.com": 0.90,
    "bbc.com": 0.88,
    "bbc.co.uk": 0.88,
    "nytimes.com": 0.85,
    "theguardian.com": 0.85,
    "economist.com": 0.88,
    "ft.com": 0.88,
    "wsj.com": 0.85,
    # Indian news
    "thehindu.com": 0.85,
    "hindustantimes.com": 0.80,
    "ndtv.com": 0.78,
    "timesofindia.com": 0.78,
    "indianexpress.com": 0.82,
    "livemint.com": 0.80,
    "business-standard.com": 0.80,
    # Community / professional networks (allowed but flagged when sole source)
    "reddit.com":  0.60,
    "linkedin.com": 0.62,
    "quora.com":   0.55,
    # Tech
    "techcrunch.com": 0.75,
    "wired.com": 0.78,
    "arstechnica.com": 0.80,
    "theverge.com": 0.75,
    "github.com": 0.82,
    "stackoverflow.com": 0.82,
    # International orgs
    "who.int": 0.95,
    "un.org": 0.92,
    "worldbank.org": 0.90,
}


def get_trust_score(domain: str) -> float:
    domain = domain.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    if domain in _DOMAIN_TRUST:
        return _DOMAIN_TRUST[domain]
    if domain.endswith(".gov") or domain.endswith(".gov.in"):
        return 0.90
    if domain.endswith(".edu") or domain.endswith(".ac.in"):
        return 0.85
    if domain.endswith(".org"):
        return 0.68
    return 0.50


def is_blocked(domain: str) -> bool:
    """Returns True for social media domains that should never be used as sources."""
    domain = domain.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain in _BLOCKED_DOMAINS


def is_community_source(domain: str) -> bool:
    """Returns True for Reddit/LinkedIn/Quora — allowed but flagged when sole source."""
    domain = domain.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain in _COMMUNITY_DOMAINS


def get_trust_label(score: float) -> tuple[str, str]:
    """Returns (label, emoji)"""
    if score >= 0.88:
        return "High", "🟢"
    elif score >= 0.70:
        return "Medium", "🟡"
    else:
        return "Low", "🔴"
