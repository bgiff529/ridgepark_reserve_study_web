# Ridge Park Reserve Study OO

Class-based rewrite of the Ridge Park reserve study workflow. The code is
organized around components, dated expenditure/collection schedules, and reserve
studies. It reads scenario data by path, runs the study with typed domain
objects, writes outputs into a parallel run directory, and can generate
LaTeX/PDF reports, plots, and optimized collection schedules.

Scenario folders live at the project root, for example
`2026_brendan_plan/source_data`. The analysis year is read from
`source_data/assumptions.csv` (`Analysis Date`); scripts do not hard-code the
study year.

The main API is intentionally small:

```python
from reserve_study import ReserveStudy

study = ReserveStudy.from_directory("2026_brendan_plan")
result = study.run()
result.write_outputs()
result.build_plots()
result.build_report(compile_pdf=False)
```

```bash
python scripts/run_study.py 2026_brendan_plan
python scripts/build_report.py 2026_brendan_plan --compile-pdf
python scripts/build_plots.py 2026_brendan_plan
python scripts/optimize_study.py 2026_brendan_plan
```

Each command writes to `runs/<variant>/`. Use `--legacy-root` only when you want
to read a scenario from another project directory instead of the local copy.
Lower-level path and repository helpers still exist internally, but ordinary
usage should go through `ReserveStudy` and `StudyResult`.

PDF compilation uses a local TeX installation. The report builder looks for
`latexmk` first and then `pdflatex`, including the MacTeX path
`/Library/TeX/texbin`. If no compiler is available, TeX generation still works
and PDF compilation fails with setup guidance.

The `examples/` directory contains notebooks for the main workflows:

- `01_run_study.ipynb`: load and run a scenario.
- `02_schedules.ipynb`: inspect components and dated schedules.
- `03_reports_and_plots.ipynb`: generate CSVs, plots, TeX, and PDF when TeX is installed.
- `04_optimize_collections.ipynb`: optimize the collection schedule.
