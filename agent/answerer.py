# agent/answerer.py

import os
import re
from typing import Generator
from groq import Groq

MODEL = "llama-3.3-70b-versatile"
MAX_ANSWER_TOKENS = 1024

_SYSTEM_PROMPT = """\
You are a thorough research assistant. You will be given excerpts from web pages \
and a user question. Your task is to write a clear, well-structured answer.

CITATION RULES (mandatory):
- Every factual claim MUST be followed by an inline citation in this exact format:
  [Title — domain](URL)
- Use the exact title and URL from the sources provided.
- If multiple sources support the same claim, cite all of them.
- Never cite the same URL more than once in the entire answer. If you have already
  cited a source, do not repeat it — refer to the claim it supported earlier instead.

UNCERTAINTY RULES (mandatory — do not skip):
- Before writing, scan all sources for contradictions.
- If sources GENUINELY DISAGREE on a claim (e.g. some say beneficial, others say harmful),
  you MUST open that section with the exact phrase: "Sources conflict on this point:"
  Then present each side with citations. Do NOT synthesise toward a single conclusion
  when real disagreement exists — leave the conflict visible to the reader.
- If the provided excerpts do not contain enough information to answer confidently,
  open with the exact phrase: "Based on available sources, I cannot determine…"
  then state what CAN be inferred from the evidence.
- Never fabricate facts. When uncertain, hedge explicitly.

FORMAT:
- Use markdown headers (##) to organise long answers.
- Write a minimum of 200 words. Never give a one-paragraph answer to a research question.
- When expressing uncertainty, still explain what the sources DO say — projections,
  ranges, models, competing estimates. Do not stop after saying "I cannot determine";
  always follow it with a substantive discussion of what evidence exists.
"""


_CITATION_RE = re.compile(r'\[([^\]]+)\]\((https?://[^\)]+)\)')


def _deduplicate_citations(text: str) -> str:
    """Remove every repeat occurrence of a citation with the same URL, keeping the first."""
    seen: set[str] = set()

    def _replace(m: re.Match) -> str:
        url = m.group(2)
        if url in seen:
            return ""          # drop the duplicate entirely
        seen.add(url)
        return m.group(0)      # keep the first occurrence unchanged

    return _CITATION_RE.sub(_replace, text)


def _build_context(chunks: list[dict]) -> str:
    parts = []
    for i, chunk in enumerate(chunks, 1):
        header = f"[SOURCE {i}] {chunk['title']} | {chunk['domain']} | {chunk['url']}"
        parts.append(f"{header}\n{chunk['text']}")
    return "\n\n---\n\n".join(parts)


def generate_answer(
    question: str,
    chunks: list[dict],
    conversation_history: list[dict] | None = None,
    stream: bool = True,
    language: str = "English",
) -> Generator[str, None, None] | str:
    client = Groq(api_key=os.environ["GROQ_API_KEY"])

    system = _SYSTEM_PROMPT
    if language != "English":
        system += (
            f"\n\nLANGUAGE: The user asked in {language}. "
            f"You MUST respond entirely in {language}. "
            "Keep citation URLs and domain names in their original Latin script."
        )

    messages = [{"role": "system", "content": system}]
    messages.extend(conversation_history or [])

    context_block = _build_context(chunks)
    user_content = (
        f"## Research Sources\n\n{context_block}\n\n"
        f"## Question\n\n{question}"
    )
    messages.append({"role": "user", "content": user_content})

    if stream:
        def _token_stream() -> Generator[str, None, None]:
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                max_tokens=MAX_ANSWER_TOKENS,
                temperature=0.2,
                stream=True,
            )
            for chunk in response:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    yield delta.content
        return _token_stream()
    else:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=MAX_ANSWER_TOKENS,
            temperature=0.2,
            stream=False,
        )
        raw = response.choices[0].message.content or ""
        return _deduplicate_citations(raw)
