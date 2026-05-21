from dotenv import load_dotenv
load_dotenv()

from agent.planner import generate_search_queries

question = "What are the latest breakthroughs in fusion energy?"
print(f"Question: {question}\n")

queries = generate_search_queries(question)
print("Generated search queries:")
for i, q in enumerate(queries, 1):
    print(f"  {i}. {q}")
