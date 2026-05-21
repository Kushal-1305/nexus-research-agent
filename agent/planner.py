# agent/planner.py

from groq import Groq
import os

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

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = response.choices[0].message.content.strip()

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