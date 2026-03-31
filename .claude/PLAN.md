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


## 3. Design decisions

((Put the decisions resulting from step 1 here.))


## 4. Implementation planning

Make a detailed implementation plan and put it Section 5.


## 5. Implementation plan

((here))
