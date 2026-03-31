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

Make a detailed implementation plan and put it HERE.
