2026-02-22: course volume discounting logic for gamification/anti-procrastination

## Goal

We want to add a mechanism by which students can obtain some hours of timevalue by 
making steady progress in the course overall rather than by solving individual tasks.

## Requirements

Introduce additional entries in sedrila.yaml (given with example values here):

```
student_yaml_attribute_prompts:  # exists already
    course_size_hours: "Size of your course in hours [one ECTS equals 30 hours]: "  # name chosen freely
startdate: 2025-04-15  # first day of the course
enddate: 2026-03-31  # last day of the course
discountrules:
    student_yaml_attribute: course_size_hours
    discountperiod_type: month  # "week"/"month" for calendar week or calendar month
    discountperiods: 9  # how many periods (counting from the first) are eligible for a discount
    discount_threshold_percent: 11  # what fraction of course_size_hours must be done to get the discount for period
    discount_size_percent: 2  # what fraction of course_size_hours is deducted for each discount
```

Consistency checks of these: `startdate` before `enddate`; `discountperiods * discount_threshold_percent <= 100`;
course length (`enddate` minus `startdate`) has at least `discountperiods` periods.
Stop with a specific error message if any of these is violated.

With the above settings, only calendar months 1 to 9 can produce a discount (April to December 2025).
Period `p` (in range 1..9) gets a discount if one of the following two criteria is fulfilled:
1. sum of accepted task timevalue obtained in this period is greater-or-equal `course_size_hours*11/100`
2. sum of accepted task timevalue obtained in total until the end of this period is 
   greater-or-equal `course_size_hours*p*11/100`.

In other words: if the discount criterion is fulfilled in this period or on average over all periods so far.

Add a line to each `si_volume_report` (`report.py`) just before the total indicating the total discount obtained.
Add a similar line to the `work_report` (`webapp.py`).
Add an additional page (and link to it) in the webapp that explains the discount situation:
Explain discount rules.
Provide legend for the short table titles used below.
Table with all eligible discount periods (including those in the future).
Each row states 
- period number
- period name (for month) or end date (for week)
- how much work was performed in that period (hours, percent of course size)
- how much work was performed overall up to that period (hours, percent of course size)
- how much discount this implies (hours)

The final row provides the total as seen in the `work_report`.
Zeros are not shown; leave the cell empty instead.


## Implementation ideas

- Add `Task.accept_date: datetime|None`. Turn `Task.is_accepted` into a `@property`: `accept_date is not None`.
- Add discount computation to `course_si.CourseSI`


## Task

- Check the above for ambiguity. Consult me for all you find.
- Make a step-by-step implementation plan and add it below

## Clarifications obtained

- "discount" renamed to "bonus" throughout (config keys, UI text, variable names)
- accept_date: use date of last accept event (override-reject then re-accept updates it)
- bonusrules optional: if absent, no bonus logic at all
- startdate/enddate are required fields in sedrila.yaml schema
- week = ISO calendar week (Monday–Sunday), counted from the week containing startdate
- bonus is per-student (each has their own course_size_hours from student.yaml)
- bonus line in si_volume_report: just total bonus hours before the total row
- bonus row in webapp work_report: one additional row for all students together
- period 1 = calendar month/week containing startdate (may be shorter than others)
- zeros not shown: applies to all three numerical columns (hours, percent, bonus)
- webapp bonus detail page: shows columns per student like work_report does
- course_size_hours from student.yaml will be a string, must convert to number

## Implementation Plan

### Step 1: Add `Task.accept_date` and make `is_accepted` a property

**File: `py/sdrl/course.py`**
- Add `import datetime as dt`
- Replace field `is_accepted: bool = False` with `accept_date: dt.datetime | None = None`
- Add property: `@property def is_accepted(self) -> bool: return self.accept_date is not None`
- `time_earned` property continues to work unchanged (uses `self.is_accepted`)

### Step 2: Update `repo.py` to set `accept_date` instead of `is_accepted`

**File: `py/sdrl/repo.py`**
- In `_accumulate_timevalues_and_attempts()`:
  - Line 252: `task.is_accepted = True` → `task.accept_date = check.commit.author_date`
  - Line 257: `task.is_accepted = False` → `task.accept_date = None`

### Step 3: Add schema entries for new config fields

**File: `py/sdrl/schema/sedrila-yaml.schema.json`**
- Add `startdate` (type: string, format: date) to `required` array and `properties`
- Add `enddate` (type: string, format: date) to `required` array and `properties`
- Add `bonusrules` as optional property with sub-object:
  - `required`: all five sub-properties
  - `additionalProperties: false`
  - `student_yaml_attribute` (string)
  - `bonusperiod_type` (enum: ["week", "month"])
  - `bonusperiods` (integer, minimum: 1)
  - `bonus_threshold_percent` (integer, minimum: 1, maximum: 100)
  - `bonus_size_percent` (integer, minimum: 1, maximum: 100)

### Step 4: Add config reading and validation in `Course`

**File: `py/sdrl/course.py`**
- Add `import datetime as dt` (already done in step 1)
- Add class attributes to `Course`:
  - `startdate: dt.date | None = None`
  - `enddate: dt.date | None = None`
  - `bonusrules: b.StrAnyDict | None = None`
- Add `startdate, enddate` to `mustcopy_attrs` in `_read_config()` (they are required)
- Add `bonusrules` to `cancopy_attrs` in `_read_config()`
- After `_read_config()` in `__init__()`, parse `startdate`/`enddate` strings into `dt.date` objects
- Add `_validate_bonusrules()` method, called from `__init__()` only if `bonusrules is not None`:
  - `startdate < enddate`
  - `bonusperiods * bonus_threshold_percent <= 100`
  - Number of calendar months/weeks from startdate to enddate >= bonusperiods
  - `bonusrules['student_yaml_attribute']` is a key in `student_yaml_attribute_prompts`
  - Each check produces a specific error message via `b.critical()`

### Step 5: Pass bonus config through to course.json metadata

**File: `py/sdrl/coursebuilder.py`**
- In `Coursebuilder.as_json()`, add to result dict:
  - `startdate=str(self.startdate)` (ISO format)
  - `enddate=str(self.enddate)` (ISO format)
  - `bonusrules=self.bonusrules` (if not None; it's already a plain dict)

### Step 6: Store custom student attributes in `Student`

**File: `py/sdrl/participant.py`**
- In `Student.__init__()`, after `data = b.slurp_yaml(self.participantfile_path)`, add:
  `self.participant_data = data`
- This makes `course_size_hours` (as a string!) accessible via `student.participant_data['course_size_hours']`

### Step 7: Add bonus computation to `CourseSI`

**File: `py/sdrl/course_si.py`**

Add at module top level:
```python
@dataclasses.dataclass
class BonusPeriodResult:
    period_num: int           # 1-based
    label: str                # "April 2025" or "2025-04-20" (week end date)
    period_hours: float       # timevalue earned in this period
    period_percent: float     # period_hours as % of course_size_hours
    cumulative_hours: float   # total earned up to end of this period
    cumulative_percent: float # cumulative_hours as % of course_size_hours
    bonus_hours: float        # bonus for this period (0 if criterion not met)
```

Add methods to `CourseSI`:
- `bonus_period_ranges() -> list[tuple[dt.date, dt.date]]`:
  Computes (start, end) date ranges for each eligible period.
  For month: period 1 starts at `startdate`, ends at last day of that calendar month.
  Period 2 starts first of next month, ends last of that month. Etc.
  For week: period 1 starts at `startdate`, ends at Sunday of that ISO week. Etc.

- `bonus_period_label(start, end) -> str`:
  For month: "April 2025" etc. For week: end.strftime("%Y-%m-%d").

- `compute_bonus(course_size_hours: float) -> list[BonusPeriodResult]`:
  For each period, sums `task.timevalue` for tasks where `task.accept_date` falls within
  that period's date range. Computes cumulative totals. Applies bonus criteria:
  1. period_hours >= course_size_hours * threshold_percent / 100, OR
  2. cumulative_hours >= course_size_hours * p * threshold_percent / 100
  If either criterion met, bonus_hours = course_size_hours * bonus_size_percent / 100, else 0.

- `total_bonus(results: list[BonusPeriodResult]) -> float`:
  Static method, returns sum of bonus_hours across all results.

### Step 8: Refactor report printing; add bonus line to SI report

**File: `py/sdrl/report.py`**
- Rename `_print_si_volume_report` → `print_si_volume_report` (make public)
- Rename `_print_author_volume_report` → `print_author_volume_report` (make public)
- Remove `print_volume_report()` (the dispatch function)
- Change `print_si_volume_report` signature to accept a `Student` parameter:
  `def print_si_volume_report(student: 'sdrl.participant.Student'):`
  - It obtains `course` from `student.course_with_work` internally
  - After computing totals, if `course.bonusrules` is not None:
    - Get `course_size_hours = float(student.participant_data[course.bonusrules['student_yaml_attribute']])`
    - Call `course.compute_bonus(course_size_hours)`
    - Add a "Bonus" row before the TOTAL row showing total bonus hours (in the Accept column)
  - Adjust the TOTAL row to include bonus in the accept total

**File: `py/sdrl/subcmd/student.py`**
- Change line 65: `sdrl.report.print_volume_report(context.course, author_mode=False)`
  → `sdrl.report.print_si_volume_report(context.studentlist[0])`
  (Import `sdrl.report` if not already imported)

**File: `py/sdrl/subcmd/instructor.py`**
- Change line 55: `sdrl.report.print_volume_report(stud.course, author_mode=False)`
  → `sdrl.report.print_si_volume_report(stud)`

**File: `py/sdrl/subcmd/author.py`**
- Change line 84: `sdrl.report.print_volume_report(the_course, author_mode=True)`
  → `sdrl.report.print_author_volume_report(the_course)`

### Step 9: Add bonus row to webapp `work_report`

**File: `py/sdrl/webapp.py`**
- In `html_for_work_report_section()`:
  - After the totals row, add a "Bonus" row (only if `ctx.course.bonusrules` is not None)
  - For each student `s`:
    - `course_size_hours = float(s.participant_data[s.course.bonusrules['student_yaml_attribute']])`
    - Compute bonus via `s.course_with_work.compute_bonus(course_size_hours)`
    - Show `total_bonus` in the bonus row cell (empty string if 0)
  - Note: `s.course_with_work` is already populated by this point (via `submissions` property)

### Step 10: Add bonus detail page to webapp

**File: `py/sdrl/webapp.py`**
- Add constant: `BONUS_REPORT_URL = "/bonus.report"`
- Add route: `@bottle.route(BONUS_REPORT_URL)` → `serve_bonus_report()`
- Implement `html_for_bonus_report(ctx: Context) -> str`:
  - Text section explaining bonus rules (period type, threshold %, bonus size %, from course config)
  - Legend for column abbreviations: p# (period number), period (name/date),
    ph (period hours), p% (period percent), ch (cumulative hours), c% (cumulative percent), bh (bonus hours)
  - Table: header row with column labels, then per student columns (like work_report pattern)
  - For each eligible period (1..bonusperiods):
    - Period#, label, then per-student: ph, p%, ch, c%, bh
    - All zeros shown as empty cells
  - Final "Total" row with sum of bonus_hours per student
  - Wrap in `html_for_layout()`

### Step 11: Link to bonus page from webapp index

**File: `py/sdrl/webapp.py`**
- In `serve_index()`, add a link to `BONUS_REPORT_URL` near the work report section
  (only if `ctx.course.bonusrules is not None`)

### Step 12: Tests

**New file: `py/sdrl/tests/test_bonus.py`**
- Test `CourseSI.bonus_period_ranges()` for month type (including partial first month)
- Test `CourseSI.bonus_period_ranges()` for week type (including partial first week)
- Test `CourseSI.compute_bonus()` with known inputs:
  - Case where period criterion met
  - Case where cumulative criterion met
  - Case where neither met
  - Case with course_size_hours as various values
- Test `Course._validate_bonusrules()`:
  - startdate >= enddate → error
  - periods * threshold > 100 → error
  - not enough periods in date range → error
- Test that `Task.is_accepted` property works with `accept_date`