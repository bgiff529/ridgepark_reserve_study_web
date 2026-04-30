from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from reserve_study import ReserveStudy


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a reserve study scenario using the OO package")
    parser.add_argument("variant", nargs="?", default="2026_brendan_plan")
    parser.add_argument("--legacy-root", default=None, help="Optional external project root. Defaults to this OO project.")
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--projection-years", type=int, default=30)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    study = ReserveStudy.from_variant(args.variant, scenario_root=args.legacy_root, output_root=args.output_root)
    results = study.run(projection_years=args.projection_years)
    output_root = results.write_outputs()
    print(f"Wrote study outputs to {output_root}")


if __name__ == "__main__":
    main()
