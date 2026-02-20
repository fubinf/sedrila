# `sedrila evaluator`: statistically assess the behavior of one full cohort of SeDriLa students

**All functionality described herein is in alpha development stage and is subject to change!**

`sedrila evaluator` is a data extraction and statistical evaluation tailored to `sedrila`.
Its main purpose is helping course organizers and developers understand 
student progress as the course unfolds and
what tasks came out how in actual course practice after the course ends
(done how often, with which success, taking how much time).

It is currently a highly **experimental function**, is under heavy (if slooooow) development, 
and might change abruptly.
Do not rely on anything here yet.

## 1. Basic use

- Go to an instructor directory under which the individual student course directories (with repos)
  reside.
- Call `sedrila evaluator YYYY-MM-DD outputdir` where the date is the first course day.
- Open `outputdir/index.html` in your browser.
- The generated page starts with an overview list and then shows all evaluations as one long report.
- Each evaluation section contains the chart(s), one short interpretation paragraph, and a second
  paragraph with design rationale/tradeoff notes.

## 2. Options

- `--nopull`:
  skip pulling repositories before analysis (faster when repos are already up to date).
- `--log LEVEL`:
  set logging verbosity (`DEBUG`, `INFO`, ...).

That's all.
