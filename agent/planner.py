# agent/planner.py

import os
import time
from groq import Groq


def _groq_with_retry(client: Groq, *, model: str, messages: list, max_tokens: int,
                     temperature: float = 0.0, retries: int = 4) -> str:
    delay = 15
    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(
                model=model, messages=messages,
                max_tokens=max_tokens, temperature=temperature,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            if attempt == retries - 1:
                raise
            s = str(e).lower()
            is_tpm = ("rate_limit" in s or "429" in s) and "per day" not in s and "tokens per day" not in s
            if is_tpm:
                print(f"[planner] Per-minute rate limit, retrying in {delay}s…", flush=True)
                time.sleep(delay)
                delay *= 2
            else:
                raise


def generate_search_queries(user_question: str, conversation_summary: str = "") -> list[str]:
    client = Groq(api_key=os.environ["GROQ_API_KEY"])

    context_block = ""
    if conversation_summary:
        context_block = f"\nPrior conversation context:\n{conversation_summary}\n"

    prompt = f"""You are a research planning assistant.
Given a user question, generate 5 focused web search queries that together will help answer it comprehensively.{context_block}
Rules:
- Each query should be short, keyword-dense, and search-engine friendly
- Queries should cover different angles: background facts, specific entities mentioned, comparisons, recent developments, and expert/authoritative sources
- For multi-part questions, dedicate at least one query to each named entity or concept
- Do not explain anything, return ONLY a numbered list

User question: {user_question}

Search queries:"""

    raw = _groq_with_retry(
        client,
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=256,
    )

    queries = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        # Strip leading "1. " or "1) " or "- "
        if line[0].isdigit():
            line = line.split(".", 1)[-1].strip()
            line = line.split(")", 1)[-1].strip()
        elif line.startswith("-"):
            line = line[1:].strip()
        if line:
            queries.append(line)

    return queries[:5]  # cap at 5 queries max