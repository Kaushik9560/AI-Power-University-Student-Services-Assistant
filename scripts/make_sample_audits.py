"""
Produce the three sample audit records required by the deliverables checklist
(docs/sample_audits/*.json): one retrieved_fact, one calculated, one not_found (plus conflict_flagged).

    python scripts/make_sample_audits.py            # live stack
    python scripts/make_sample_audits.py --offline  # fake store + mock LLM
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SAMPLES = [
    ("retrieved_fact", "What is the minimum attendance required to appear for end-semester exams?", None, "2026-10-06"),
    ("calculated", "If I attend the next 4 classes, will I be eligible for the end-semester exam in DBMS?", "S1006", "2026-10-06"),
    ("not_found", "What is the scholarship for studying in Antarctica?", None, "2026-10-06"),
    ("conflict_flagged", "What is the minimum attendance required to appear for end-semester exams?", None, "2026-11-01"),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "docs" / "sample_audits"))
    args = ap.parse_args()
    load_dotenv(ROOT / ".env", override=True)
    if args.offline:
        from scripts.evaluation import make_ask
        ask = make_ask(True)
        from app.audit.store import read_audit
        samples = [
            ("retrieved_fact", SAMPLES[0][1], None, "2026-10-06"),
            ("calculated", "What is my attendance in DBMS?", "S1001", "2026-10-06"),
            SAMPLES[2],
            ("conflict_flagged", "What time do the hostel gates close?", None, "2026-10-06"),
        ]
    else:
        samples = SAMPLES
    base = os.environ.get("API_BASE_URL", "http://localhost:8000").rstrip("/")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, q, sid, as_of in samples:
        if args.offline:
            s = ask(q, sid, as_of)
            rec = read_audit(s["trace_id"])
        else:
            response = requests.post(f"{base}/ask", json={"question": q, "as_of_date": as_of},
                                     headers={"X-Student-Id": sid} if sid else {}, timeout=180)
            response.raise_for_status()
            s = response.json()
            response = requests.get(f"{base}/audit/{s['trace_id']}", timeout=30)
            response.raise_for_status()
            rec = response.json()
        if s["answer_type"] != name:
            raise RuntimeError(f"Expected {name}, got {s['answer_type']}; review the evidence before saving")
        rec["_response"] = {k: s.get(k) for k in ("answer", "answer_type", "citations", "applied_rules", "verdict")}
        (out / f"{name}.json").write_text(json.dumps(rec, indent=2, default=str))
        print(f"{name:<16} trace={s['trace_id']} answer_type={s['answer_type']}")


if __name__ == "__main__":
    main()
