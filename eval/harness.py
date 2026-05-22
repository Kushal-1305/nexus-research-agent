# eval/harness.py
"""
Evaluation harness. Run with:
    cd deep_research_agent
    python -m eval.harness            # full run
    python -m eval.harness --start 4  # resume from question 4 (1-indexed)
"""

import argparse
import json
import re
import os
import sys
import time
from datetime import datetime

_ROOT = os.path.join(os.path.dirname(__file__), "..")
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dotenv import load_dotenv
load_dotenv()

from agent.loop import run

DATASET_PATH = os.path.join(os.path.dirname(__file__), "dataset.json")
RESULTS_PATH = os.path.join(os.path.dirname(__file__), "results.json")

_CITATION_RE = re.compile(r"\[.+?(?:—|\|)\s*.+?\]\(https?://[^\)]+\)")

_UNCERTAINTY_PHRASES = [
    "cannot determine", "cannot confirm", "i cannot", "uncertain",
    "insufficient", "not enough information", "don't know", "unclear",
    "conflict", "conflicting", "sources disagree", "varies", "depends",
    "no consensus", "cannot predict", "unable to",
]


def _count_citations(answer: str) -> int:
    return len(_CITATION_RE.findall(answer))


def _keyword_coverage(answer: str, keywords: list[str]) -> float:
    if not keywords:
        return 1.0
    answer_lower = answer.lower()
    hits = sum(1 for kw in keywords if kw.lower() in answer_lower)
    return round(hits / len(keywords), 4)


def _expresses_uncertainty(answer: str) -> bool:
    answer_lower = answer.lower()
    return any(phrase in answer_lower for phrase in _UNCERTAINTY_PHRASES)


def _run_question(question: str) -> tuple[str, list[dict], list[str]]:
    answer_parts: list[str] = []
    sources: list[dict] = []
    queries: list[str] = []

    for event in run(question):
        if event["stage"] == "streaming":
            answer_parts.append(event["token"])
        elif event["stage"] == "done":
            sources = event.get("sources", [])
            queries = event.get("search_queries", [])
        elif event["stage"] == "error":
            print(f"    [ERROR] {event['message']}", flush=True)

    return "".join(answer_parts), sources, queries


def _load_existing_results() -> dict[str, dict]:
    """Load previously saved per-question results keyed by question id."""
    if not os.path.exists(RESULTS_PATH):
        return {}
    try:
        with open(RESULTS_PATH) as f:
            saved = json.load(f)
        return {r["id"]: r for r in saved.get("results", [])}
    except Exception:
        return {}


def run_eval(start_from: int = 1) -> None:
    with open(DATASET_PATH) as f:
        dataset = json.load(f)

    # Load any previously completed results so we can merge them
    existing = _load_existing_results()
    results = []

    print(f"\n{'='*60}")
    print(f"Deep Research Agent — Evaluation Harness")
    print(f"Dataset: {len(dataset)} questions  |  Starting from: {start_from}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    for i, item in enumerate(dataset, 1):
        qid      = item["id"]
        qtype    = item["type"]
        question = item["question"]
        exp_kws  = item.get("expected_keywords", [])

        # Reuse existing result if we're skipping this question
        if i < start_from:
            if qid in existing:
                results.append(existing[qid])
                print(f"[{i}/{len(dataset)}] {qid} — skipped (using saved result)")
            else:
                print(f"[{i}/{len(dataset)}] {qid} — skipped (no saved result, will be missing from summary)")
            continue

        print(f"[{i}/{len(dataset)}] {qid} ({qtype})")
        print(f"  Q: {question}")

        t0 = time.time()
        answer, sources, queries = _run_question(question)
        elapsed = round(time.time() - t0, 2)

        citation_count   = _count_citations(answer)
        kw_coverage      = _keyword_coverage(answer, exp_kws)
        expresses_unc    = _expresses_uncertainty(answer)
        answer_len_words = len(answer.split())

        if qtype in ("insufficient_evidence", "conflicting_sources"):
            uncertainty_score = 1.0 if expresses_unc else 0.0
        else:
            uncertainty_score = None

        result = {
            "id":             qid,
            "type":           qtype,
            "question":       question,
            "answer":         answer,
            "sources_count":  len(sources),
            "search_queries": queries,
            "metrics": {
                "citation_count":        citation_count,
                "keyword_coverage":      kw_coverage,
                "expresses_uncertainty": expresses_unc,
                "uncertainty_score":     uncertainty_score,
                "answer_length_words":   answer_len_words,
                "elapsed_seconds":       elapsed,
            },
        }
        results.append(result)

        # Save incrementally after each question so a crash/limit loses minimal work
        _save_results(results)

        print(f"  Citations: {citation_count} | KW coverage: {kw_coverage:.0%} "
              f"| Words: {answer_len_words} | Time: {elapsed}s")
        if uncertainty_score is not None:
            status = "PASS" if uncertainty_score == 1.0 else "FAIL"
            print(f"  Uncertainty check: {status}")
        print()

        if i < len(dataset):
            time.sleep(5)

    summary = _save_results(results)
    print(f"{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"  Avg citations per answer : {summary['avg_citation_count']:.1f}")
    print(f"  Avg keyword coverage     : {summary['avg_keyword_coverage']:.0%}")
    print(f"  Avg answer length (words): {summary['avg_answer_length_words']:.0f}")
    print(f"  Avg time per question    : {summary['avg_elapsed_seconds']:.1f}s")
    if summary["uncertainty_pass_rate"] is not None:
        unc_results = [r for r in results if r["metrics"]["uncertainty_score"] is not None]
        print(f"  Uncertainty detection    : {summary['uncertainty_pass_rate']:.0%} ({len(unc_results)} questions)")
    print()
    print(f"Results saved to: {RESULTS_PATH}")


def _save_results(results: list[dict]) -> dict:
    if not results:
        return
    avg_citations   = sum(r["metrics"]["citation_count"]      for r in results) / len(results)
    avg_kw_coverage = sum(r["metrics"]["keyword_coverage"]    for r in results) / len(results)
    avg_words       = sum(r["metrics"]["answer_length_words"] for r in results) / len(results)
    avg_time        = sum(r["metrics"]["elapsed_seconds"]     for r in results) / len(results)
    unc_results     = [r for r in results if r["metrics"]["uncertainty_score"] is not None]
    unc_pass_rate   = (
        sum(1 for r in unc_results if r["metrics"]["uncertainty_score"] == 1.0) / len(unc_results)
        if unc_results else None
    )
    summary = {
        "total_questions":          len(results),
        "avg_citation_count":       round(avg_citations, 2),
        "avg_keyword_coverage":     round(avg_kw_coverage, 4),
        "avg_answer_length_words":  round(avg_words),
        "avg_elapsed_seconds":      round(avg_time, 2),
        "uncertainty_pass_rate":    round(unc_pass_rate, 4) if unc_pass_rate is not None else None,
    }
    output = {
        "timestamp": datetime.now().isoformat(),
        "summary":   summary,
        "results":   results,
    }
    with open(RESULTS_PATH, "w") as f:
        json.dump(output, f, indent=2)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--start", type=int, default=1, metavar="N",
        help="Start from question N (1-indexed). Questions before N reuse saved results.",
    )
    args = parser.parse_args()
    run_eval(start_from=args.start)
