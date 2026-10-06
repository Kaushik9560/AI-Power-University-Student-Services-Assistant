"""
Load Annex C CSVs into SQLite (guide §4.2 "loader"). Judges will run this with their own data.

    python scripts/load_students.py                       # data/synthetic (full reset)
    python scripts/load_students.py --dir test_students/  # add/overwrite judges' students (upsert)
    python scripts/load_students.py --dir X --replace     # wipe tables first

Loads whichever of students.csv, courses.csv, attendance.csv, results.csv, rule_registry.csv exist
in the directory. Validation (scripts/validate_students.py) runs first and refuses invalid data
unless --force is given.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.db.database import load_csv_tables, table_counts  # noqa: E402
from scripts.validate_students import validate  # noqa: E402

ORDER = ("courses", "students", "attendance", "results", "rule_registry")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=None)
    ap.add_argument("--rules", default=None, help="rule registry CSV (overrides the configured/default registry)")
    ap.add_argument("--replace", action="store_true", help="delete existing rows of each loaded table first")
    ap.add_argument("--force", action="store_true", help="load even if validation reports violations")
    args = ap.parse_args()
    d = Path(args.dir) if args.dir else settings.SYNTHETIC_DIR
    if (d / "students.csv").exists():
        errors, _ = validate(d)
        if errors and not args.force:
            print(f"Refusing to load: {len(errors)} validation violation(s). First: {errors[0]} (use --force to override)")
            sys.exit(1)
    paths = {table: d / f"{table}.csv" for table in ORDER if (d / f"{table}.csv").exists()}
    rule_path = Path(args.rules) if args.rules else (d / "rule_registry.csv" if args.dir else settings.RULE_REGISTRY_PATH)
    if rule_path.exists():
        paths["rule_registry"] = rule_path
    elif args.rules or not args.dir:
        raise FileNotFoundError(f"Configured rule registry does not exist: {rule_path}")
    loaded = load_csv_tables(paths, replace=args.replace)
    for table, n in loaded.items():
        print(f"  {table:<14} {n:>5} rows from {paths[table]}")
    print("table counts:", table_counts())


if __name__ == "__main__":
    main()
