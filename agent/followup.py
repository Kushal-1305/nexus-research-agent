# agent/followup.py
import os
from groq import Groq


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

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=200,
        temperature=0.7,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.choices[0].message.content.strip()

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
