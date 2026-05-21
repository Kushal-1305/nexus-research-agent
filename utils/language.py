# utils/language.py

_LANGUAGE_RANGES = {
    "Hindi":     ('\u0900', '\u097F'),
    "Bengali":   ('\u0980', '\u09FF'),
    "Punjabi":   ('\u0A00', '\u0A7F'),
    "Gujarati":  ('\u0A80', '\u0AFF'),
    "Odia":      ('\u0B00', '\u0B7F'),
    "Tamil":     ('\u0B80', '\u0BFF'),
    "Telugu":    ('\u0C00', '\u0C7F'),
    "Kannada":   ('\u0C80', '\u0CFF'),
    "Malayalam": ('\u0D00', '\u0D7F'),
}

_LANGUAGE_FLAGS = {
    "Hindi":     "🇮🇳",
    "Bengali":   "🇮🇳",
    "Tamil":     "🇮🇳",
    "Telugu":    "🇮🇳",
    "Kannada":   "🇮🇳",
    "Malayalam": "🇮🇳",
    "Gujarati":  "🇮🇳",
    "Punjabi":   "🇮🇳",
    "Odia":      "🇮🇳",
    "English":   "🇺🇸",
}


def detect_language(text: str) -> str:
    counts = {
        lang: sum(1 for c in text if lo <= c <= hi)
        for lang, (lo, hi) in _LANGUAGE_RANGES.items()
    }
    best = max(counts, key=counts.get)
    return best if counts[best] >= 3 else "English"


def language_flag(language: str) -> str:
    return _LANGUAGE_FLAGS.get(language, "🌐")
