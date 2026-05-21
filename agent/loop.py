# agent/loop.py

from typing import Generator
from agent.planner    import generate_search_queries
from agent.searcher   import search_all
from agent.fetcher    import fetch_pages
from agent.selector   import select_chunks
from agent.answerer   import generate_answer, _deduplicate_citations
from agent.followup   import suggest_followups
from agent.confidence import compute_confidence
from agent.trust      import is_community_source
from utils.language   import detect_language

ProgressEvent = dict


def run(
    question: str,
    session=None,
    conversation_history: list[dict] | None = None,
    max_search_results: int = 5,
    max_pages: int = 8,
) -> Generator[ProgressEvent, None, None]:
    """
    Generator that runs the full research pipeline, yielding progress events.

    Stages: planning → searching → fetching → selecting → answering
            → followups → done  (or error)
    """
    answer_tokens: list[str] = []

    try:
        # ── Language detection ─────────────────────────────────
        language = detect_language(question)
        if language != "English":
            yield {"stage": "planning", "message": f"Detected language: {language}"}

        # ── Stage 1: Planning ──────────────────────────────────
        yield {"stage": "planning", "message": "Generating search queries…"}
        summary = session.get_summary() if session else ""
        search_queries = generate_search_queries(question, conversation_summary=summary or "")
        yield {
            "stage": "planning",
            "message": f"Generated {len(search_queries)} queries: "
                       + " | ".join(f'"{q}"' for q in search_queries),
        }

        # ── Stage 2: Searching ─────────────────────────────────
        yield {"stage": "searching", "message": f"Searching the web with {len(search_queries)} queries…"}
        search_results = search_all(search_queries, max_results_per_query=max_search_results)
        yield {"stage": "searching", "message": f"Found {len(search_results)} unique URLs."}

        if not search_results:
            yield {"stage": "error", "message": "No search results. Try rephrasing the question."}
            return

        # ── Stage 3: Fetching ──────────────────────────────────
        yield {"stage": "fetching", "message": f"Fetching content from up to {max_pages} pages…"}
        pages = fetch_pages(search_results, max_pages=max_pages)
        yield {"stage": "fetching", "message": f"Successfully fetched {len(pages)} pages."}

        if not pages:
            from urllib.parse import urlparse
            pages = [
                {
                    "url":          r["url"],
                    "title":        r["title"],
                    "text":         r["snippet"],
                    "domain":       urlparse(r["url"]).netloc,
                    "retrieved_at": "",
                }
                for r in search_results if r.get("snippet")
            ]

        # ── Stage 4: Selecting ─────────────────────────────────
        yield {"stage": "selecting", "message": "Ranking and selecting the most relevant content…"}
        chunks, sources = select_chunks(pages, question)
        total_chars = sum(len(c["text"]) for c in chunks)
        yield {
            "stage": "selecting",
            "message": f"Selected {len(chunks)} chunks from {len(sources)} sources ({total_chars:,} chars).",
        }

        if not chunks:
            yield {"stage": "error", "message": "No relevant content found."}
            return

        # ── Stage 5: Answering ─────────────────────────────────
        yield {"stage": "answering", "message": "Generating cited answer…"}
        for token in generate_answer(
            question=question,
            chunks=chunks,
            conversation_history=conversation_history or [],
            stream=True,
            language=language,
        ):
            answer_tokens.append(token)
            yield {"stage": "streaming", "token": token}

        final_answer = _deduplicate_citations("".join(answer_tokens))

        # ── Confidence score (instant) ─────────────────────────
        confidence = compute_confidence(final_answer, chunks, sources)

        # ── Community-only source warning ──────────────────────
        social_warning: str | None = None
        if sources:
            non_community = [
                s for s in sources
                if not is_community_source(s.get("domain", ""))
            ]
            if not non_community:
                names = sorted({s.get("domain", "") for s in sources})
                social_warning = (
                    f"Only community sources were available for this question "
                    f"({', '.join(names)}). Answers may reflect opinions or "
                    "unverified claims rather than established facts."
                )

        # ── Follow-up questions ────────────────────────────────
        yield {"stage": "followups", "message": "Suggesting follow-up questions…"}
        followups = suggest_followups(question, final_answer, language)

        # ── Persist ────────────────────────────────────────────
        if session:
            session.add_turn(
                question=question,
                answer=final_answer,
                sources=sources,
                search_queries=search_queries,
                context_snippets=chunks,
            )
            _update_session_summary(session, question, final_answer)

        yield {
            "stage":          "done",
            "answer":         final_answer,
            "sources":        sources,
            "search_queries": search_queries,
            "confidence":     confidence,
            "followups":      followups,
            "language":       language,
            "social_warning": social_warning,
        }

    except Exception as exc:
        yield {"stage": "error", "message": f"Pipeline error: {type(exc).__name__}: {exc}"}


def _update_session_summary(session, question: str, answer: str) -> None:
    from groq import Groq
    import os

    turns = session.get_turns()
    if not turns:
        return

    if len(turns) % 3 != 0:
        existing = session.get_summary() or ""
        session.update_summary(f"{existing}\nQ: {question[:120]}")
        return

    history_text = "\n".join(
        f"Q: {t['question'][:200]}\nA: {t['answer'][:400]}"
        for t in turns[-6:]
    )
    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=128,
        messages=[{
            "role": "user",
            "content": (
                "Summarise the following research conversation in 2-3 sentences "
                "for use as context in future searches:\n\n" + history_text
            ),
        }],
    )
    session.update_summary(resp.choices[0].message.content.strip())
