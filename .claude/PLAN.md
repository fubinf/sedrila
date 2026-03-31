2026-03-31 MANUAL bookkeeping

## 1. Goal

Have `book_command()` in `instructor.py` provides a well-defined form of timevalue records
for which the timevalue is set manually (as opposed to timevalue attached to a task).
These records must now 
a) be shown individually in the webapp work report or command line status report and
a) be counted towards the overall student timevalue


## 2. Design discussion

Cleanup of `repo.py`: Which of the operations are not called from outside the module and should
hence start with an underscore and be put at the back of the module?
Which of the rest are main entry points and should thus be put first in the module?
Which of these are missing a mission description in a doc comment?

Propose how the existing data classes and the main entry points should be extended for 
collecting the manual booking data.

Propose how `Course` or `CourseSI` should be extended for representing and accessing these data.
Which of the two is the right home and why?

Propose a report format each for the overall work report, status report, and the separate
manual bookings report page in `reports.py`.

If there are multiple sensible ways of solving each of these, explain them and let me decide between them.


## 3. Design stage

### 3.1 Extending manual_command()

Add an option `--task` with a string parameter that must be a taskname.
Validate it against the `CourseSI` object.
If it is no task, produce an error message and fail.
Otherwise, use the task name as the manual booking reason type in line 1 of the commit message.

We call entries with a valid taskname "task-specific", the others "global".


### 3.2 Extending data classes and entry points for manual booking data

The `book_command()` creates signed empty commits with line-1 message format:
`MANUAL <timevalue>  <reason type>`

These may or may not be task-specific and adjust the student's overall timevalue sum.

#### New data class: `ManualEntry`

```python
class ManualEntry(tg.NamedTuple):
    commit: sgit.Commit
    timevalue: float
    reason: str  # taskname or other rest of line 1 of commit message after "MANUAL <timevalue>  "
```

#### New parsing function: `_parse_manual_booking`

Parses a commit message starting with `MANUAL_BOOKING_MARKER`, extracts timevalue and reason.
Returns `ManualEntry` or `None`.

#### New collection function: `manual_entries_from_commits`

Analogous to `work_entries_from_commits` — iterates signed instructor commits, 
filters for MANUAL prefix, returns `list[ManualEntry]`.

Manual booking commits must be **instructor-signed** (they are created with `signed=True` 
in `book_command`), so they should be filtered to have `MANUAL_BOOKING_MARKER` prefix AND 
valid instructor signature.


#### Extending `compute_student_work_so_far`

Add a step that:
1. Scans commits for instructor-signed MANUAL commits
2. Collects `ManualEntry` objects
3. Stores them in `course.manual_bookings` and computes `course.manual_timevalue`

#### Extending `student_work_so_far`

The returned tuple currently is `(list[ReportEntry], workhours_total, timevalue_total)`.
Manual bookings should be added to `timevalue_total`.

**Alternative A**: Add manual_timevalue to the existing timevalue_total. Simple, 
but callers can't distinguish task-earned from manually-booked timevalue.

#### Extending `event_list`

Add ET.manual events from manual booking commits. 
The `taskname` field should be empty and `timevalue` is the booking amount.
Add a comment to the taskname field "empty for ET.manual".


### 3.3 Where to store manual booking data: Course or CourseSI?

`Course` is the common superclass of `Coursebuilder` (author context) and
`CourseSI` (student and instructor contexts, also evaluator context).
`repo.py` currently talks about `Course`, but should talk about `CourseSI`.
Some current attributes of `Course` hence belong into `CourseSI`.

Refactor `repo.py`, `Course`, and `CourseSI` accordingly.
Add attribute `manual_bookings: list[ManualEntry]`.


### 3.4 Report formats

#### 3.4.1 Webapp work report (html_for_work_report_section in webapp/reports.py)

The following is described for a single student, but must work accordingly when the
webapp is started for multiple students.

Currently shows per-task rows with w/v/e columns, then optional bonus row, then totals.
Add a fourth value column `m` ("MANUAL entries") that is empty unless one or more 
manual entries exist for the respective task (and then show their timevalues sum).

For the global (non-task-specific) manual entries, add a
"other manual bookings" summary row (like the bonus row), between bonus and totals
that has a value only in column `m`.

In the totals row, leave column `m` empty and add what would be its value to column `v`.

Additionally, make the words "manual bookings" in the "other manual bookings" summary row
a link to a separate detail page (`/manual.bookings`, aking to `/bonus.report`), showing individual bookings,
both task-specific and global, in chronological order with the following columns:
Reason, Date (ISO datestamp of commit), commit (length-10 hash), timevalue (in decimal hours).
If Reason is a taskname, prefix it with "T::".

#### 3.4.2 CLI status report (print_si_volume_report in report.py)

Currently shows per-chapter and per-difficulty tables with Worktime/Accept/Reject columns.
Add another column "Manual" with the sum of the task-specific manual entries that pertain
to the tasks represented by this line.
Add another line "other manual bookings" just before the "=TOTAL" row,
with an entry only in the "Manual" column
that is the sum of the global manual bookings (or 0 if there are none).

Extend the "=TOTAL" row by that "Manual" column as well.

Print a new, separate line after the last of the tables stating
"Grand total course work timevalue: <sum>h"
where the sum is the sum of the "Accept" and "Manual" totals.


## 4. Implementation plan

### Step 1: Add `--task` option to `book_command()` in `subcmd/instructor.py`

- Add `@click.option("--task", ...)` to `book_command()`.
- After option parsing, if `--task` is given:
  - Instantiate a `CourseSI` from `c.METADATA_FILE` to validate the taskname.
  - If `course.task(taskname)` returns `None`, print error and `return`.
  - Otherwise, use the taskname as the reason type in the commit message prefix.
- Requires reading `c.METADATA_FILE` in the cwd; 
  use `sdrl.participant.Student('.', is_instructor=True).course` for validation,
  same pattern as `prepare_workdir()`.

### Step 2: Add `ManualEntry` class and parsing in `repo.py`

- Add `ManualEntry(tg.NamedTuple)` with fields: `commit`, `timevalue`, `reason`.
- Add `_parse_manual_booking(commit_msg: str) -> tg.Optional[tg.Tuple[float, str]]`:
  - Match against `^MANUAL\s+(-?\d+(\.\d+)?)\s\s(.+)` (the MANUAL prefix, timevalue, double-space, reason).
  - Return `(timevalue, reason)` or `None`.
- Add `manual_entries_from_commits(instructors, commits) -> list[ManualEntry]`:
  - Filter commits to those that are instructor-signed (reuse fingerprint logic from
    `submission_checked_commits`) AND whose subject starts with `MANUAL_BOOKING_MARKER`.
  - Parse each with `_parse_manual_booking`, collect `ManualEntry` objects.

### Step 3: Add `manual_bookings` attribute to `CourseSI`

- Add `manual_bookings: list[ManualEntry] = []` in `CourseSI.__init__` 
  (not in `Course`, since only student/instructor contexts need it).
- Add `manual_timevalue: float = 0.0` likewise.
- These are populated by `compute_student_work_so_far`.

### Step 4: Extend `compute_student_work_so_far` in `repo.py`

- Change parameter type from `Course` to `CourseSI` (import `sdrl.course_si`).
- After the existing worktime and taskcheck accumulation, add:
  - Call `manual_entries_from_commits(all_instructors, commits)`.
  - Store result in `course.manual_bookings`.
  - Compute `course.manual_timevalue = sum(e.timevalue for e in course.manual_bookings)`.
- Also compute per-task manual sums: for each `ManualEntry` whose `reason` is a valid
  taskname (`reason in course.taskdict`), accumulate into a new `Task` attribute 
  `manual_timevalue: float = 0.0` (added to `Task` in `course.py`).

### Step 5: Add `Task.manual_timevalue` attribute in `course.py`

- Add `manual_timevalue: float = 0.0` to `Task`.
- This accumulates the sum of task-specific manual bookings for this task.

### Step 6: Extend `student_work_so_far` in `repo.py`

- Add `course.manual_timevalue` to `timevalue_total` before returning.
- This ensures manual bookings (both task-specific and global) count toward the overall total.

### Step 7: Extend `event_list` in `repo.py`

- After the existing work-entry loop, add a loop over manual entries 
  (using `manual_entries_from_commits`):
  - Create `Event(ET.manual, student_username, commit.author_email, commit.author_date, "", entry.timevalue)`.
  - The `taskname` field is empty string (as per design: "empty for ET.manual").

### Step 8: Extend CLI report (`print_si_volume_report` in `report.py`)

- Extend `_si_volume_report` to return a 5th column "Manual":
  - For each row (chapter or difficulty group), sum `task.manual_timevalue` for matching tasks.
  - Change `Volumereport.columnheads` to include "Manual".
- In `print_si_volume_report`:
  - Add an "other manual bookings" row before "=TOTAL":
    compute global manual sum = `course.manual_timevalue - sum(t.manual_timevalue for all tasks)`.
  - Extend "=TOTAL" row with the Manual column total.
  - After the last table, print `"Grand total course work timevalue: <sum>h"` where sum = 
    Accept total + Manual total (+ Bonus if applicable).

### Step 9: Extend webapp work report (`html_for_work_report_section` in `webapp/reports.py`)

- Add a 4th value column `m` in the header row per student: `<th>w</th><th>v</th><th>e</th><th>m</th>`.
- In `html_for_students(task)`: for each student, show `task.manual_timevalue` in column `m`
  (empty if zero).
- Add an "other manual bookings" summary row between bonus and totals:
  - Compute global manual = `course.manual_timevalue - sum(t.manual_timevalue for tasks)`.
  - Show this value only in column `m`.
  - Make "manual bookings" a link to `/manual.bookings`.
- In the totals row, leave `m` empty; add the manual total to column `v` (earned).

### Step 10: Add manual bookings detail page in `webapp/reports.py`

- Add `MANUAL_BOOKINGS_URL = "/manual.bookings"` to `webapp/resources.py`.
- Add a new `@bottle.route(MANUAL_BOOKINGS_URL)` handler `serve_manual_bookings()`.
- Add `html_for_manual_bookings(ctx)`:
  - For each student, collect `course.manual_bookings` sorted by commit date.
  - Render a table with columns: Reason (prefix tasknames with "T::"), Date (ISO), 
    Commit (10-char hash), Timevalue (decimal hours).
  - Pattern after `html_for_bonus_report`.

### Step 11: Refactor `repo.py` type annotations

- Where `repo.py` functions receive `course: sdrl.course.Course` but actually need 
  `CourseSI`-specific attributes (like `manual_bookings`), change the type to `CourseSI`.
- Specifically: `compute_student_work_so_far` should take `CourseSI`.
- Functions that genuinely work with any `Course` (like `event_list`, `student_work_so_far`) 
  can keep `Course` as their type. If they access `manual_bookings`, change to `CourseSI`.

### Implementation order

Execute steps 2, 5 first (new data structures), then 3, 4, 6, 7 (core logic), 
then 1 (CLI extension), then 8, 9, 10 (reports), then 11 (cleanup).
Run `python -m pytest py/` after each major step.
