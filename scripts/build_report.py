from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from reserve_study import ReserveStudy


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a reserve study report using the OO package")
    parser.add_argument("variant", nargs="?", default="2026_brendan_plan")
    parser.add_argument("--legacy-root", default=None, help="Optional external project root. Defaults to this OO project.")
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--projection-years", type=int, default=30)
    parser.add_argument("--compile-pdf", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    study = ReserveStudy.from_variant(args.variant, scenario_root=args.legacy_root, output_root=args.output_root)
    results = study.run(projection_years=args.projection_years)
    results.write_outputs()
    try:
        report_path = results.build_report(compile_pdf=args.compile_pdf)
    except OSError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    if args.compile_pdf:
        print(f"Wrote PDF report to {report_path}")
    else:
        print(f"Wrote TeX report to {report_path}")


if __name__ == "__main__":
    main()
