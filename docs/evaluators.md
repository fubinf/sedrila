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
- Call `sedrila evaluator --start YYYY-MM-DD -o outputdir` where the date is the first course day.
- Open `outputdir/index.html` in your browser.
- The generated page starts with an overview list and then shows all evaluations as one long report.
- Each evaluation section contains the chart(s), one short interpretation paragraph, and a second
  paragraph with design rationale/tradeoff notes.

## 2. Options

- `--nopull`:
  skip pulling repositories before analysis (faster when repos are already up to date).

That's all.


## Plan for future functionality


### What to use for the functionality

#### Inputs

The functionality will make use of these parts:
- The current state of each student's working directory, in particular `student.yaml`
- Each student's git history, in particular the revisions of `submission.yaml`

#### Outputs

The output will be a single long HTML document (with images).
It should contain the following elements:
- A table of contents to sections and subsections along the lines of the ideas below.
- Various types of plot, e.g. distribution plots, stacked or unstacked bar plots, perhaps pie charts,
  multiple box plots, line plots for time series, perhaps scatter plots (perhaps with regression lines or loess lines).
- Tables (espectially for modest numbers of multi-attribute data)
- Bulleted lists (of students, pairs, or partnames)


### Functionality ideas

Currently mostly a list of questions describing issues that the report should help us understand.

General ideas:
- As a rule of thumb, we want each bin from which we compute a value to contain at least five elements;
  exceptions (to be marked as such in the report) are permitted where needed.
- To view how something complex (such as a distribution) changes over time,
  we compare n equal-sized fractions of the course-time-so-far (e.g. the course's front/middle/hind third).
  This can the n separate plots or preferably n complex plot elements in a single one (e.g. lines or boxplots).
- Each plot should have a concise caption explaining its meaning (in complex cases also a legend).
- Some evaluations reflect rules that, strictly speaking, are course-specific.
  If a course had a different rule, that evaluation might become meaningless; we accept this.
- Tables of tasks should include task timevalue, task difficulty and the number of cases reflected in the row.
- Relative worktime of a task is student reported worktime divided by task timevalue (in percent).
- Boxplots should show 10,25,50,75,90-percentiles and average (median as a fat dot, average as an "M")
  and also show the jittered raw data points.

#### Regarding the students

- Plot: Distribution of time invested per week and timevalue earned per week over the cohort
  and how this changes over time.  
  Table: highest-intensity participants.
- Plot: Distribution of task-rejection (versus acceptance) fraction over the cohort and how this changes over time.  
  Table: Most rejection-intense participants.

#### Regarding the pairs

- What fraction of students does not name a partner?
- Of those with a partner, what fraction does not submit in sync (within a few hours, 90%-identical sets of tasks) with them?
- Of those that submit in sync, what fraction has identical `.prot` files (this is not allowed in most courses) 
  in their submitted tasks sometimes?
  Tabulate the top k cases.
- What fraction has identical `.md` files (this is not allowed in most courses) 
  in their submitted tasks ever?
  Tabulate the top k cases.
- What fraction has different acceptance (vs. rejection) success for more than 10% of their submitted tasks 
  in their submitted tasks ever?
  Tabulate the top k cases.

#### Regarding the instructors

- Plot: How loaded is each instructor (submission volume in tasks or taskvalue to be checked) in each week?
- Plot: What is the m-week trailing median and average submission batch size at each instructor in each week?
- Plot: What is the task-rejection rate of each (m-week trailing moving average)?

#### Regarding the course content

- List the k most popular task groups and how this changes over time.
  Exclude excepted chapters and task groups.
- Tabulate the k tasks with the highest rejection rate.
- Tabulate the k tasks with the lowest 20-percentile of relative worktime.  
  Tabulate the k tasks with the highest 80-percentile of relative worktime.  


### Implementation instructions

- make sure to build reusable infrastructure for similar types of plot or table
- Use minimal Javascript to make each plot, table, or list collapsible (default: expanded)
- Build a YAML configuration file for customizable settings (e.g. n, k, m, excluded parts above)