# agent/followup.py
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
                print(f"[followup] Per-minute rate limit, retrying in {delay}s…", flush=True)
                time.sleep(delay)
                delay *= 2
            else:
                raise


def suggest_followups(question: str, answer: str, language: str = "English") -> list[str]:
    """Generate 3 follow-up research questions based on the Q&A."""
    client = Groq(api_key=os.environ["GROQ_API_KEY"])

    lang_note = (
        f"Write the follow-up questions in {language}."
        if language != "English" else ""
    )

    prompt = f"""Based on this research Q&A, suggest exactly 3 follow-up questions a curious researcher might ask next.

Question: {question}
Answer (summary): {answer[:600]}

Rules:
- Cover different angles: one deeper dive, one broader context, one practical application
- Each question should be self-contained and specific
- Output ONLY a numbered list (1. 2. 3.), no explanations or preamble
{lang_note}"""

    raw = _groq_with_retry(
        client,
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
        temperature=0.7,
    )

    questions = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if line[0].isdigit():
            line = line.split(".", 1)[-1].strip()
            line = line.split(")", 1)[-1].strip()
        if line and len(line) > 10:
            questions.append(line)
    return questions[:3]
