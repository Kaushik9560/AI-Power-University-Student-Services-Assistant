"""
Evaluation (guide §7, R12). Runs data/evaluation/questions.jsonl through the full pipeline and
reports measured results. Method: deterministic exact-match checks (no LLM-as-judge):

  answer correctness      answer_type matches AND every expected value string appears in answer+explanation
  citation accuracy       every expected doc_id is cited AND no forbidden doc_id (expected_not_doc_ids) is cited
  abstention accuracy     not_found questions return not_found; answerable questions do not
  tool-result correctness expected tools were invoked with status ok AND verdict matches
  retrieval hit rate      every expected doc_id appears in the top-k retrieved chunks (before precedence)
  latency / cost          p50, p95 latency; LLM calls and tokens per question (from the audit record)

Usage
  python scripts/evaluation.py                       # current .env configuration
  python scripts/evaluation.py --compare             # top_k 8 vs 4 on the existing persistent index
  python scripts/evaluation.py --offline             # fake store + mock LLM (no Chroma/Ollama needed)
  python scripts/evaluation.py --out docs/evaluation_report.md
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def load_questions(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def run_one(ask, q: dict) -> dict:
    t0 = time.perf_counter()
    s = ask(q["question"], q.get("student_id"), q.get("as_of_date"))
    latency = int((time.perf_counter() - t0) * 1000)
    text = (s.get("answer", "") + " " + s.get("explanation", ""))
    cited = {c["doc_id"] for c in s.get("citations", [])}
    retrieved = {r["doc_id"] for r in s.get("sources_retrieved", [])}
    tools_ok = {t["tool"] for t in s.get("tools_invoked", []) if t["status"] == "ok"}
    expected_docs = set(q.get("expected_doc_ids", []))
    forbidden = set(q.get("expected_not_doc_ids", []))

    type_ok = s.get("answer_type") == q["expected_answer_type"]
    from app.rag.attribution import normalise_numbers
    values_ok = all(normalise_numbers(v).lower() in normalise_numbers(text).lower() for v in q.get("expected_values", []))
    answer_ok = type_ok and values_ok
    citation_ok = expected_docs <= cited and not (forbidden & cited) if (expected_docs or forbidden) else True
    for expected in q.get("expected_citations", []):
        citation_ok = citation_ok and any(
            citation["doc_id"] == expected["doc_id"] and
            (not expected.get("section_prefix") or str(citation.get("section") or "").startswith(expected["section_prefix"])) and
            (not expected.get("page") or citation.get("page") == expected["page"])
            for citation in s.get("citations", []))
    is_abstain_q = q["expected_answer_type"] == "not_found"
    abstention_ok = (s.get("answer_type") == "not_found") == is_abstain_q
    verdict_ok = s.get("verdict") == q.get("expected_verdict")
    tools_expected = set(q.get("expected_tools", []))
    tool_ok = tools_expected <= tools_ok and verdict_ok
    # Personal facts come directly from SQLite; rule citations need no vector lookup.
    retrieval_ok = expected_docs <= retrieved if expected_docs and s.get("query_type") != "personal" else None
    return {
        "id": q["id"], "category": q.get("category"), "answer_type": s.get("answer_type"),
        "expected_answer_type": q["expected_answer_type"], "answer_ok": answer_ok, "citation_ok": citation_ok,
        "abstention_ok": abstention_ok, "tool_ok": tool_ok, "retrieval_ok": retrieval_ok,
        "latency_ms": latency, "llm_calls": s.get("llm_calls", 0), "tokens": s.get("tokens", 0),
        "trace_id": s.get("trace_id"), "answer": s.get("answer", "")[:160],
        "cited": sorted(cited), "verdict": s.get("verdict"),
    }


def summarise(rows: list[dict]) -> dict:
    def rate(key, subset=None):
        xs = [r[key] for r in (subset or rows) if r[key] is not None]
        return (sum(1 for x in xs if x) / len(xs), len(xs)) if xs else (None, 0)

    lat = sorted(r["latency_ms"] for r in rows)
    p50 = statistics.median(lat)
    p95 = lat[min(len(lat) - 1, int(round(0.95 * len(lat))) - 1)] if len(lat) > 1 else lat[0]
    tool_q = [r for r in rows if r["expected_answer_type"] == "calculated"]
    return {
        "n": len(rows),
        "answer_correctness": rate("answer_ok"),
        "citation_accuracy": rate("citation_ok", [r for r in rows if r["cited"] or r["expected_answer_type"] in ("retrieved_fact", "conflict_flagged", "calculated")]),
        "abstention_accuracy": rate("abstention_ok"),
        "tool_result_correctness": rate("tool_ok", tool_q),
        "retrieval_hit_rate": rate("retrieval_ok"),
        "latency_p50_ms": p50, "latency_p95_ms": p95,
        "llm_calls_per_question": round(sum(r["llm_calls"] for r in rows) / len(rows), 2),
        "tokens_per_question": round(sum(r["tokens"] for r in rows) / len(rows), 1),
    }


def fmt_rate(v):
    r, n = v
    return "n/a" if r is None else f"{100 * r:.0f}% ({int(round(r * n))}/{n})"


def report_markdown(name: str, summary: dict, rows: list[dict], config: dict) -> str:
    lines = [f"### Configuration: {name}", "",
             "| Setting | Value |", "|---|---|"] + [f"| {k} | {v} |" for k, v in config.items()] + ["",
             "| Metric | Result |", "|---|---|",
             f"| Answer correctness | {fmt_rate(summary['answer_correctness'])} |",
             f"| Citation accuracy | {fmt_rate(summary['citation_accuracy'])} |",
             f"| Abstention accuracy | {fmt_rate(summary['abstention_accuracy'])} |",
             f"| Tool-result correctness | {fmt_rate(summary['tool_result_correctness'])} |",
             f"| Retrieval hit rate (top-k) | {fmt_rate(summary['retrieval_hit_rate'])} |",
             f"| Latency p50 / p95 | {summary['latency_p50_ms']} ms / {summary['latency_p95_ms']} ms |",
             f"| LLM calls / tokens per question | {summary['llm_calls_per_question']} / {summary['tokens_per_question']} |",
             "", "| id | expected | got | answer | cite | abstain | tool | retr | ms |", "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        tick = lambda v: "✓" if v else ("–" if v is None else "✗")  # noqa: E731
        lines.append(f"| {r['id']} | {r['expected_answer_type']} | {r['answer_type']} | {tick(r['answer_ok'])} | "
                     f"{tick(r['citation_ok'])} | {tick(r['abstention_ok'])} | {tick(r['tool_ok'])} | {tick(r['retrieval_ok'])} | {r['latency_ms']} |")
    failures = [r for r in rows if not (r["answer_ok"] and r["citation_ok"] and r["abstention_ok"])]
    if failures:
        lines += ["", "Failures:"] + [f"- **{r['id']}** got `{r['answer_type']}`, cited {r['cited']}: {r['answer']}" for r in failures]
    return "\n".join(lines) + "\n"


def make_ask(offline: bool):
    if offline:
        os.environ.update({"EMBEDDING_PROVIDER": "hash", "MOCK_LLM": "true", "RETRIEVAL_MAX_DISTANCE": "0.95",
                           "RETRIEVAL_TOP_K": os.environ.get("RETRIEVAL_TOP_K", "12"),
                           "SOURCE_REGISTER": str(ROOT / "data" / "source_register.csv"),
                           "DOCUMENTS_DIR": str(ROOT / "data" / "documents"),
                           "SYNTHETIC_DIR": str(ROOT / "data" / "synthetic"),
                           "SQLITE_PATH": str(ROOT / "tests" / "_tmp" / "evaluation.db"),
                           "AUDIT_DB_PATH": str(ROOT / "tests" / "_tmp" / "evaluation-audit.db")})
        import app.rag.store as store_mod
        from app.config import settings
        from app.db.database import LOAD_ORDER, load_csv_tables
        from tests.fake_store import FakeStore

        # fresh store for every configuration (chunk size may differ)
        load_csv_tables({t: settings.SYNTHETIC_DIR / f"{t}.csv" for t in LOAD_ORDER}, replace=True)
        settings.CHUNK_SIZE_CHARS = int(os.environ.get("CHUNK_SIZE_CHARS", settings.CHUNK_SIZE_CHARS))
        settings.RETRIEVAL_TOP_K = int(os.environ.get("RETRIEVAL_TOP_K", settings.RETRIEVAL_TOP_K))
        store_mod._store = FakeStore()
        from app.graph.workflow import run_query_without_langgraph
        return run_query_without_langgraph
    from app.config import settings
    from app.graph.workflow import run_query
    from app.rag.store import get_store
    from scripts.ingest_documents import ingest_from_register

    settings.CHUNK_SIZE_CHARS = int(os.environ.get("CHUNK_SIZE_CHARS", settings.CHUNK_SIZE_CHARS))
    settings.RETRIEVAL_TOP_K = int(os.environ.get("RETRIEVAL_TOP_K", settings.RETRIEVAL_TOP_K))
    if os.environ.get("EVAL_REINGEST") == "1":
        ingest_from_register(get_store(), reset=True)
    return run_query


CONFIGS = {
    "A: top_k=8, chunk=900 (default)": {"RETRIEVAL_TOP_K": "8", "CHUNK_SIZE_CHARS": "900"},
    "B: top_k=4, chunk=900": {"RETRIEVAL_TOP_K": "4", "CHUNK_SIZE_CHARS": "900"},
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", default=None, help="JSONL set (default: NSUT live set, or original fixtures with --offline)")
    ap.add_argument("--out", default=None, help="markdown report path")
    ap.add_argument("--compare", action="store_true", help="compare top-k 8 and 4 using the same persisted index")
    ap.add_argument("--offline", action="store_true", help="fake store + mock LLM (no Chroma/Ollama)")
    args = ap.parse_args()
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=True)

    question_path = Path(args.questions) if args.questions else ROOT / "data" / "evaluation" / (
        "questions.jsonl" if args.offline else "nsut_questions.jsonl")
    questions = load_questions(question_path)
    configs = CONFIGS if args.compare else {"current .env": {}}
    sections, summaries = [], {}
    for name, env in configs.items():
        os.environ.update(env)
        ask = make_ask(args.offline)
        rows = [run_one(ask, q) for q in questions]
        summaries[name] = summarise(rows)
        from app.config import settings
        from app.services.llm import get_llm
        config = {"llm": f"{get_llm().name}/{get_llm().model}", "embeddings": settings.EMBEDDING_PROVIDER,
                  "top_k": settings.RETRIEVAL_TOP_K, "chunk_chars": settings.CHUNK_SIZE_CHARS,
                  "evidence_max": settings.EVIDENCE_MAX_CHUNKS, "questions": len(rows)}
        sections.append(report_markdown(name, summaries[name], rows, config))
        print(f"[{name}] answer={fmt_rate(summaries[name]['answer_correctness'])} "
              f"citation={fmt_rate(summaries[name]['citation_accuracy'])} "
              f"abstain={fmt_rate(summaries[name]['abstention_accuracy'])} "
              f"tools={fmt_rate(summaries[name]['tool_result_correctness'])} "
              f"retrieval={fmt_rate(summaries[name]['retrieval_hit_rate'])} "
              f"p50={summaries[name]['latency_p50_ms']}ms p95={summaries[name]['latency_p95_ms']}ms")

    header = ["# Evaluation report", "",
              f"Generated by `scripts/evaluation.py` on {time.strftime('%Y-%m-%d %H:%M')} "
              f"({'OFFLINE: fake store + mock LLM' if args.offline else 'live stack'}).",
              "", "**Method.** Deterministic exact-match scoring, no LLM-as-judge: answer_type must match; every expected "
              "value (numbers, result codes) must appear in answer+explanation (number words zero–twenty are normalized); expected doc_ids must be cited and "
              "forbidden (superseded/expired) doc_ids must not be; eligibility verdicts must match the expected boolean; "
              "expected tools must have run with status ok. Retrieval hit rate is measured on the top-k chunks before "
              "precedence; tool-only personal questions are excluded from this retrieval metric. Latency is wall-clock "
              "per question; LLM calls and tokens come from the audit record. Questions with expected_citations also require "
              "the reviewed section prefix or PDF page. These checks do not prove every claim is correct; inspect the "
              "cited passages during review.", ""]
    if len(summaries) > 1:
        header += ["## Configuration comparison", "", "| Configuration | Answer | Citation | Abstention | Tools | Retrieval | p50 ms | p95 ms |",
                   "|---|---|---|---|---|---|---|---|"]
        for name, s in summaries.items():
            header.append(f"| {name} | {fmt_rate(s['answer_correctness'])} | {fmt_rate(s['citation_accuracy'])} | "
                          f"{fmt_rate(s['abstention_accuracy'])} | {fmt_rate(s['tool_result_correctness'])} | "
                          f"{fmt_rate(s['retrieval_hit_rate'])} | {s['latency_p50_ms']} | {s['latency_p95_ms']} |")
        header.append("")
    text = "\n".join(header) + "\n" + "\n".join(sections)
    if args.out:
        Path(args.out).write_text(text)
        print(f"report written to {args.out}")


if __name__ == "__main__":
    main()
