"""Derive fictional NSUT demo records from the original synthetic kit; no network access."""
from __future__ import annotations

import csv
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm-names", action="store_true", help="generate and validate fictional names with the local LLM")
    parser.add_argument("--replay", type=Path, help="validate saved model outputs without another model call")
    args = parser.parse_args()
    target = ROOT / "data" / "nsut" / "synthetic"
    target.mkdir(parents=True, exist_ok=True)
    names = None
    if args.llm_names or args.replay:
        from pydantic import BaseModel, Field
        from app.services.llm import get_llm
        class Names(BaseModel):
            names: list[str] = Field(min_length=32, max_length=32)
        system = "Generate fictional Indian-style student names for a software test fixture. Do not use real student rosters or external personal data. Return ONLY a JSON object with a names array of exactly 32 distinct full names."
        user = "Generate 32 distinct fictional full names, each at least 3 characters long. No IDs, numbers, prose or markdown. These will label entirely synthetic NSUT demo records."
        saved = json.loads(args.replay.read_text()) if args.replay else None
        runs = saved["runs"] if saved else []
        for attempt in range(len(runs) if saved else 3):
            if saved:
                text = runs[attempt]["output"]
            else:
                response = get_llm().complete(system, user, max_tokens=650, temperature=0.4)
                text = response.text
                runs.append({"model": f"{response.provider}:{response.model}", "tokens": response.tokens, "output": text})
            try:
                text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text.strip())
                raw = json.loads(text)
                parsed = Names.model_validate({"names": raw} if isinstance(raw, list) else raw)
                if len(set(parsed.names)) != 32 or any(len(name.strip()) < 3 for name in parsed.names):
                    raise ValueError("Names must be distinct and nonempty")
                names = parsed.names
                break
            except ValueError as error:
                runs[attempt]["validation_error"] = str(error)
        assembly = "single validated response"
        if names is None:
            unique = []
            for run in runs:
                try:
                    raw = json.loads(re.sub(r'^```(?:json)?\s*|\s*```$', '', run["output"].strip()))
                    for name in raw if isinstance(raw, list) else raw.get("names", []):
                        if isinstance(name, str) and len(name.strip()) >= 3 and name.strip() not in unique:
                            unique.append(name.strip())
                except (ValueError, AttributeError):
                    continue
            if len(unique) >= 32:
                names = Names(names=unique[:32]).names
                assembly = "32 distinct model-generated names assembled from validated partial responses"
        (target / "generation_run.json").write_text(json.dumps({"system_prompt": system, "user_prompt": user,
            "temperature": 0.4, "calls": len(runs), "runs": runs, "valid": names is not None,
            "assembly": assembly,
            "normalization": "Markdown fences removed; a top-level JSON names array is wrapped in the required object before schema validation."}, indent=2))
        (target / "prompts.md").write_text(f"# Verbatim NSUT synthetic-name generation prompts\n\n## System\n\n{system}\n\n## User\n\n{user}\n\nTemperature: 0.4. Exact model, call count, outputs and validation are in generation_run.json. Numerical records and edge cases are assigned by code.\n")
        if names is None:
            raise RuntimeError("The model did not return 32 valid fictional names; existing kit was preserved")
    attendance_edges = {"S1005": 75, "S1006": 74, "S1007": 65, "S1008": 60}
    for name in ("students", "courses", "attendance", "results"):
        with (ROOT / "data" / "synthetic" / f"{name}.csv").open() as source:
            reader = csv.DictReader(source)
            columns, records = reader.fieldnames, list(reader)
        for row in records:
            if name == "students" and names:
                row["full_name"] = names[int(row["student_id"][1:]) - 1001]
            if name == "attendance" and row["course_code"] == "CS301" and row["student_id"] in attendance_edges:
                row["classes_held"] = "100"
                row["classes_attended"] = str(attendance_edges[row["student_id"]])
            if name == "results":
                if row["exam_type"] == "SUPPLEMENTARY":
                    row["exam_type"] = "REGULAR"  # A fictional repeat-course exam.
                if row["result"] == "FAIL" and int(row["external_marks"]) >= 18:
                    row["external_marks"] = "17"
                    row["total_marks"] = str(int(row["internal_marks"]) + 17)
        with (target / f"{name}.csv").open("w", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=columns)
            writer.writeheader()
            writer.writerows(records)
    shutil.copyfile(ROOT / "data" / "nsut" / "rule_registry.csv", target / "rule_registry.csv")
    print(f"Prepared fictional records in {target}")


if __name__ == "__main__":
    main()
