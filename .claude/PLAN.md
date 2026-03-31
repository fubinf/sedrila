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


## 3. Design proposals

### 3.1 repo.py cleanup

#### Functions that should be private (add underscore, move to back of module)

These are only called from within repo.py (test calls don't count as "external"):
- `is_allowed_signer` (line 157) — only called at line 123
- `is_accepted` (line 208) — only called at lines 83, 225
- `is_rejected` (line 212) — only called at line 228

Already properly prefixed: `_accumulate_timevalues_and_attempts`, `_accumulate_student_workhours_per_task`, `_parse_taskname_workhours`.

#### Main entry points (should be first in module, after classes)

These are the public API, called from outside repo.py:
1. `compute_student_work_so_far(course, commits)` — from participant.py:247
2. `student_work_so_far(course)` — report data extraction
3. `event_list(course, student_username, commits)` — from evaluator.py:304
4. `submission_state(workdir, instructor_fingerprints)` — from instructor.py:206,213
5. `import_gpg_keys(instructors)` — from student.py:194,205

Secondary public functions (used externally but more specialized):
6. `submission_checked_commits(instructors, commits)` — from evaluator and internally
7. `taskcheck_entries_from_commits(instructor_commits)` — from tests and internally
8. `work_entries_from_commits(commits)` — used in event_list

#### Missing docstrings

These public/secondary functions lack docstrings:
- `import_gpg_keys` — what it does with GPG keys and why
- `event_list` — what the event list represents and what it's used for

The private helpers `is_allowed_signer`, `is_accepted`, `is_rejected` are self-explanatory 
and don't need docstrings.


### 3.2 Extending data classes and entry points for manual booking data

The `book_command()` creates signed empty commits with message format:
`MANUAL <timevalue>  <reason text across multiple lines>`

These are NOT task-specific — they adjust the student's overall timevalue sum.

#### New data class: `ManualEntry`

```python
class ManualEntry(tg.NamedTuple):
    commit: sgit.Commit
    timevalue: float
    reason: str  # rest of commit message after "MANUAL <timevalue>"
```

#### New parsing function: `_parse_manual_booking`

Parses a commit message starting with `MANUAL_BOOKING_MARKER`, extracts timevalue and reason.
Returns `ManualEntry` or `None`.

#### New collection function: `manual_entries_from_commits`

Analogous to `work_entries_from_commits` — iterates signed instructor commits, 
filters for MANUAL prefix, returns `list[ManualEntry]`.

Note: Manual booking commits must be **instructor-signed** (they are created with `signed=True` 
in `book_command`), so they should be filtered through `submission_checked_commits` or 
equivalent signature verification. However, unlike "submission.yaml checked" commits, 
their subject does NOT match `SUBMISSION_CHECKED_COMMIT_MSG`. 

**Alternative A**: Add a second filter path in the commit-scanning that checks for 
`MANUAL_BOOKING_MARKER` prefix AND valid instructor signature independently.

**Alternative B**: Generalize `submission_checked_commits` to also return MANUAL commits 
(rename to `instructor_signed_commits` or similar, return all properly-signed instructor commits, 
then let callers filter by subject).

I recommend **Alternative A** because the two commit types serve different purposes 
and have different message formats. Keeping them separate is cleaner.

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

**Alternative B**: Return a 4-tuple: `(entries, workhours_total, timevalue_total, manual_timevalue)`. 
Callers get both components and can show them separately.

**Alternative C**: Return manual entries as a separate list in the tuple.

I recommend **Alternative B** — it's minimal change, keeps backward compatibility easy, 
and callers can display manual_timevalue separately.

#### Extending `event_list`

Add ET.manual events from manual booking commits. The `taskname` field would be empty or 
a marker like `"MANUAL"`, and `timevalue` is the booking amount.


### 3.3 Where to store manual booking data: Course or CourseSI?

**Option A: Course** (recommended)
- Add `manual_bookings: list = []` and `manual_timevalue: float = 0.0` as attributes
- Pro: Follows existing pattern — `compute_student_work_so_far` already modifies Course 
  in-place to set `task.workhours`, `task.accept_date`, `task.rejections`
- Pro: `student_work_so_far` already reads from Course, so it naturally picks up manual data
- Pro: `event_list` also operates on Course
- Con: Adds attributes irrelevant to author mode (but `workhours`, `accept_date`, `rejections` 
  are already like that)

**Option B: CourseSI**
- Pro: Manual bookings only exist in student/instructor context
- Con: `compute_student_work_so_far` and `student_work_so_far` take `Course`, not `CourseSI` — 
  would need type changes or casting
- Con: Breaks the current clean pattern where repo.py only knows about Course

I recommend **Option A (Course)** because the existing `workhours`/`accept_date`/`rejections` 
attributes already live on Course (specifically on Task, but Course is the container). 
Manual bookings are course-level rather than task-level, but the principle is the same: 
data computed from git commits and stored for reporting.

Concretely, add to `Course`:
```python
manual_bookings: list = []    # list of ManualEntry, set by compute_student_work_so_far
manual_timevalue: float = 0.0  # sum of manual booking timevalues
```


### 3.4 Report formats

#### 3.4.1 Webapp work report (html_for_work_report_section in webapp/reports.py)

Currently shows per-task rows with w/v/e columns, then optional bonus row, then totals.

Proposal: Add a "Manual bookings" summary row (like the bonus row), between bonus and totals:
```
Manual bookings    |  | <total_manual> |
```
And include `manual_timevalue` in the earned total.

Additionally, make "Manual bookings" a link to a separate detail page (like bonus has its 
own page), showing individual bookings.

#### 3.4.2 CLI status report (print_si_volume_report in report.py)

Currently shows per-chapter and per-difficulty tables with Worktime/Accept/Reject columns.

Proposal: After the existing tables, if manual_timevalue != 0, print a line:
```
Manual bookings: +2.5h (or -1.0h)
```
And include it in the TOTAL row's Accept column.

**Alternative**: Add a "Manual" row to the table itself. But since manual bookings aren't 
chapter- or difficulty-specific, a separate line after the table is cleaner.

#### 3.4.3 Separate manual bookings detail page (new in webapp/reports.py)

A new route (e.g., `/manual-bookings`) showing a table of individual manual bookings:

| Date | Timevalue | Reason |
|------|-----------|--------|
| 2026-03-15 | +2.5 | Late submission exception |
| 2026-03-20 | -1.0 | Penalty for academic dishonesty |
| **Total** | **+1.5** | |

Per student (same multi-student layout as other reports).


## 4. Implementation planning

Make a detailed implementation plan and put it Section 5.


## 5. Implementation plan

((here))
