# eval/harness.py
"""
Evaluation harness. Run with:
    cd deep_research_agent
    python -m eval.harness              # full run
    python -m eval.harness --start 4    # resume single-turn questions from index 4
    python -m eval.harness --skip-mt    # skip multi-turn conversations
"""

import argparse
import json
import re
import os
import sys
import time
import urllib.request
from datetime import datetime

_ROOT = os.path.join(os.path.dirname(__file__), "..")
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dotenv import load_dotenv
load_dotenv()

from agent.loop import run
from session.manager import Session

DATASET_PATH = os.path.join(os.path.dirname(__file__), "dataset.json")
RESULTS_PATH = os.path.join(os.path.dirname(__file__), "results.json")

_CITATION_RE     = re.compile(r"\[.+?(?:—|\|)\s*.+?\]\(https?://[^\)]+\)")
_CITATION_URL_RE = re.compile(r"\[.+?(?:—|\|)\s*.+?\]\((https?://[^\)]+)\)")

_UNCERTAINTY_PHRASES = [
    "cannot determine", "cannot confirm", "i cannot", "uncertain",
    "insufficient", "not enough information", "don't know", "unclear",
    "conflict", "conflicting", "sources disagree", "varies", "depends",
    "no consensus", "cannot predict", "unable to",
]


# ── Metric helpers ────────────────────────────────────────────────────────────

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


def _check_citation_urls(answer: str, timeout: int = 5) -> dict:
    """
    HEAD-check every cited URL. Returns reachable/total counts.
    Sites that block HEAD but return a valid domain are marked 'unknown'.
    """
    urls = list(dict.fromkeys(_CITATION_URL_RE.findall(answer)))  # unique, ordered
    reachable = unknown = broken = 0
    for url in urls:
        try:
            req = urllib.request.Request(url, method="HEAD",
                                         headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status < 400:
                    reachable += 1
                else:
                    broken += 1
        except urllib.error.HTTPError as e:
            if e.code in (403, 405, 429):   # blocked HEAD, not broken URL
                unknown += 1
            else:
                broken += 1
        except Exception:
            unknown += 1
    total = len(urls)
    return {
        "total_cited_urls":  total,
        "reachable":         reachable,
        "unknown":           unknown,
        "broken":            broken,
        "reachability_rate": round(reachable / total, 4) if total else None,
    }


# ── Single-turn runner ────────────────────────────────────────────────────────

def _run_question(
    question: str,
    session: Session | None = None,
    conversation_history: list[dict] | None = None,
) -> tuple[str, list[dict], list[str]]:
    answer_parts: list[str] = []
    sources: list[dict] = []
    queries: list[str] = []

    for event in run(question, session=session,
                     conversation_history=conversation_history or []):
        if event["stage"] == "streaming":
            answer_parts.append(event["token"])
        elif event["stage"] == "done":
            sources = event.get("sources", [])
            queries = event.get("search_queries", [])
        elif event["stage"] == "error":
            print(f"    [ERROR] {event['message']}", flush=True)

    return "".join(answer_parts), sources, queries


# ── Multi-turn runner ─────────────────────────────────────────────────────────

def _run_multi_turn(item: dict) -> dict:
    """
    Run a multi-turn conversation, measuring per-turn quality and context
    continuity (does turn 2+ correctly carry over topic from prior turns?).
    """
    turns_spec  = item["turns"]
    session     = Session()          # shared session across all turns
    conv_history: list[dict] = []
    turn_results = []

    for t_idx, turn_spec in enumerate(turns_spec):
        question     = turn_spec["question"]
        exp_kws      = turn_spec.get("expected_keywords", [])
        ctx_kws      = turn_spec.get("context_keywords", [])   # only T2+

        print(f"    Turn {t_idx + 1}: {question}")
        t0 = time.time()
        answer, sources, queries = _run_question(
            question, session=session, conversation_history=conv_history
        )
        elapsed = round(time.time() - t0, 2)

        citation_count   = _count_citations(answer)
        kw_coverage      = _keyword_coverage(answer, exp_kws)
        answer_len_words = len(answer.split())

        # Context continuity — only meaningful from turn 2 onward
        context_continuity: float | None = None
        if ctx_kws and t_idx > 0:
            context_continuity = _keyword_coverage(answer, ctx_kws)

        url_integrity = _check_citation_urls(answer)

        turn_result = {
            "turn":              t_idx + 1,
            "question":          question,
            "answer":            answer,
            "sources_count":     len(sources),
            "search_queries":    queries,
            "metrics": {
                "citation_count":        citation_count,
                "keyword_coverage":      kw_coverage,
                "answer_length_words":   answer_len_words,
                "elapsed_seconds":       elapsed,
                "context_continuity":    context_continuity,
                "citation_url_check":    url_integrity,
            },
        }
        turn_results.append(turn_result)

        cont_str = ""
        if context_continuity is not None:
            cont_str = f" | Context continuity: {context_continuity:.0%}"
        url_str = (f" | URLs: {url_integrity['reachable']}/"
                   f"{url_integrity['total_cited_urls']} reachable"
                   if url_integrity["total_cited_urls"] else "")
        print(f"      Citations: {citation_count} | KW: {kw_coverage:.0%} "
              f"| Words: {answer_len_words} | Time: {elapsed}s"
              f"{cont_str}{url_str}")

        # Build conversation history for the next turn
        conv_history.append({"role": "user",      "content": question})
        conv_history.append({"role": "assistant",  "content": answer})

        if t_idx < len(turns_spec) - 1:
            time.sleep(5)

    # Overall continuity: avg of all turns that have a continuity score
    cont_scores = [
        t["metrics"]["context_continuity"]
        for t in turn_results
        if t["metrics"]["context_continuity"] is not None
    ]
    overall_continuity = round(sum(cont_scores) / len(cont_scores), 4) if cont_scores else None
    continuity_pass    = overall_continuity is not None and overall_continuity >= 0.5

    return {
        "id":                   item["id"],
        "type":                 "multi_turn",
        "turns":                turn_results,
        "overall_continuity":   overall_continuity,
        "continuity_pass":      continuity_pass,
    }


# ── Persistence ───────────────────────────────────────────────────────────────

def _load_existing_results() -> dict[str, dict]:
    if not os.path.exists(RESULTS_PATH):
        return {}
    try:
        with open(RESULTS_PATH) as f:
            saved = json.load(f)
        return {r["id"]: r for r in saved.get("results", [])}
    except Exception:
        return {}


def _save_results(single_results: list[dict], mt_results: list[dict]) -> dict:
    all_results = single_results + mt_results
    if not all_results:
        return {}

    # Single-turn summary
    if single_results:
        avg_cit  = sum(r["metrics"]["citation_count"]      for r in single_results) / len(single_results)
        avg_kw   = sum(r["metrics"]["keyword_coverage"]    for r in single_results) / len(single_results)
        avg_wds  = sum(r["metrics"]["answer_length_words"] for r in single_results) / len(single_results)
        avg_time = sum(r["metrics"]["elapsed_seconds"]     for r in single_results) / len(single_results)
        unc_rs   = [r for r in single_results if r["metrics"].get("uncertainty_score") is not None]
        unc_rate = (
            sum(1 for r in unc_rs if r["metrics"]["uncertainty_score"] == 1.0) / len(unc_rs)
            if unc_rs else None
        )
    else:
        avg_cit = avg_kw = avg_wds = avg_time = 0.0
        unc_rate = None

    # Multi-turn summary
    mt_pass_count = sum(1 for r in mt_results if r.get("continuity_pass")) if mt_results else 0

    summary = {
        "single_turn": {
            "total_questions":         len(single_results),
            "avg_citation_count":      round(avg_cit, 2),
            "avg_keyword_coverage":    round(avg_kw, 4),
            "avg_answer_length_words": round(avg_wds),
            "avg_elapsed_seconds":     round(avg_time, 2),
            "uncertainty_pass_rate":   round(unc_rate, 4) if unc_rate is not None else None,
        },
        "multi_turn": {
            "total_conversations": len(mt_results),
            "continuity_pass":     mt_pass_count,
        },
    }
    output = {
        "timestamp": datetime.now().isoformat(),
        "summary":   summary,
        "results":   all_results,
    }
    with open(RESULTS_PATH, "w") as f:
        json.dump(output, f, indent=2)
    return summary


# ── Main eval loop ────────────────────────────────────────────────────────────

def run_eval(start_from: int = 1, skip_mt: bool = False) -> None:
    with open(DATASET_PATH) as f:
        dataset = json.load(f)

    single_items = [d for d in dataset if d["type"] != "multi_turn"]
    mt_items     = [d for d in dataset if d["type"] == "multi_turn"]

    existing = _load_existing_results()
    single_results: list[dict] = []
    mt_results:     list[dict] = []

    print(f"\n{'='*60}")
    print(f"Deep Research Agent — Evaluation Harness")
    print(f"Single-turn: {len(single_items)} | Multi-turn: {len(mt_items)} conversations")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    # ── Single-turn questions ──────────────────────────────────
    for i, item in enumerate(single_items, 1):
        qid      = item["id"]
        qtype    = item["type"]
        question = item["question"]
        exp_kws  = item.get("expected_keywords", [])

        if i < start_from:
            if qid in existing:
                single_results.append(existing[qid])
                print(f"[{i}/{len(single_items)}] {qid} — skipped (using saved result)")
            else:
                print(f"[{i}/{len(single_items)}] {qid} — skipped (no saved result)")
            continue

        print(f"[{i}/{len(single_items)}] {qid} ({qtype})")
        print(f"  Q: {question}")

        t0 = time.time()
        answer, sources, queries = _run_question(question)
        elapsed = round(time.time() - t0, 2)

        citation_count   = _count_citations(answer)
        kw_coverage      = _keyword_coverage(answer, exp_kws)
        expresses_unc    = _expresses_uncertainty(answer)
        answer_len_words = len(answer.split())
        url_integrity    = _check_citation_urls(answer)

        uncertainty_score = (
            1.0 if expresses_unc else 0.0
            if qtype in ("insufficient_evidence", "conflicting_sources") else None
        )

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
                "citation_url_check":    url_integrity,
            },
        }
        single_results.append(result)
        _save_results(single_results, mt_results)

        url_str = (f" | URLs: {url_integrity['reachable']}/"
                   f"{url_integrity['total_cited_urls']} reachable"
                   if url_integrity["total_cited_urls"] else "")
        print(f"  Citations: {citation_count} | KW: {kw_coverage:.0%} "
              f"| Words: {answer_len_words} | Time: {elapsed}s{url_str}")
        if uncertainty_score is not None:
            print(f"  Uncertainty: {'PASS' if uncertainty_score == 1.0 else 'FAIL'}")
        print()

        if i < len(single_items):
            time.sleep(5)

    # ── Multi-turn conversations ───────────────────────────────
    if mt_items and not skip_mt:
        print(f"\n{'─'*60}")
        print(f"Multi-turn conversations")
        print(f"{'─'*60}\n")

        for j, item in enumerate(mt_items, 1):
            mid = item["id"]
            if mid in existing and existing[mid].get("type") == "multi_turn":
                mt_results.append(existing[mid])
                print(f"[{j}/{len(mt_items)}] {mid} — skipped (using saved result)\n")
                continue

            print(f"[{j}/{len(mt_items)}] {mid} ({len(item['turns'])} turns)")
            mt_result = _run_multi_turn(item)
            mt_results.append(mt_result)
            _save_results(single_results, mt_results)

            cont = mt_result["overall_continuity"]
            status = "PASS" if mt_result["continuity_pass"] else "FAIL"
            print(f"  Context continuity: {cont:.0%} — {status}\n")

            if j < len(mt_items):
                time.sleep(5)

    # ── Final summary ──────────────────────────────────────────
    summary = _save_results(single_results, mt_results)
    st = summary.get("single_turn", {})
    mt = summary.get("multi_turn", {})

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"  Single-turn ({st.get('total_questions', 0)} questions):")
    print(f"    Avg citations     : {st.get('avg_citation_count', 0):.1f}")
    print(f"    Avg KW coverage   : {st.get('avg_keyword_coverage', 0):.0%}")
    print(f"    Avg answer words  : {st.get('avg_answer_length_words', 0):.0f}")
    print(f"    Avg time          : {st.get('avg_elapsed_seconds', 0):.1f}s")
    if st.get("uncertainty_pass_rate") is not None:
        print(f"    Uncertainty       : {st['uncertainty_pass_rate']:.0%}")
    if mt.get("total_conversations", 0) > 0:
        print(f"\n  Multi-turn ({mt['total_conversations']} conversations):")
        print(f"    Context continuity PASS: {mt['continuity_pass']}/{mt['total_conversations']}")
    print()
    print(f"Results saved to: {RESULTS_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--start", type=int, default=1, metavar="N",
        help="Start single-turn questions from index N (1-indexed).",
    )
    parser.add_argument(
        "--skip-mt", action="store_true",
        help="Skip multi-turn conversation tests.",
    )
    args = parser.parse_args()
    run_eval(start_from=args.start, skip_mt=args.skip_mt)
