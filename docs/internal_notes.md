# Internal technical notes

## 0. Veeery high-level overview

There are three main roles in sedrila,
each with a corresponding CLI subcommand `author`, `student`, `instructor`. 

- Authors work on the source representation of a course and generate the course website.
- Students visit the website, work on tasks, commit results to a git repo, and request
  judgment from an instructor.
  Students describe themselves in a file `student.yaml` once and 
  describe each submission (list of task names) in a file `submission.yaml`.
  Students give instructors commit rights on their repo.
- Instructors pull a student repo, review the submission via a built-in webapp, mark tasks
  as accepted or rejected in `submission.yaml` and record this in the student's repo via
  a signed commit.


### 0.1 `sedrila author`: Source representation

```
MyChapter/MyTaskGroup/MyTask.md  # extended Markdown, YAML metadata header
...
sedrila.yaml  # course configuration file, e.g. instructors and their public keys
```


### 0.2 Website

```
MyTask.html  # rendered task
...
course.json  # course metadata from sedrila.yaml and tasks
```


### 0.3 `sedrila student`: Student git repo

```
student.yaml:
    course_url: https://www.inf.fu-berlin.de/inst/ag-se/teaching/K-ProPra-2025-04
    student_gituser: abc715
    student_id: '557890'
    student_name: J.R. Student
submission.yaml:
    MyTask: CHECK
MyChapter/MyTaskGroup/MyTask.md
MyChapter/MyTaskGroup/MyTask.prot
MyChapter/MyTaskGroup/MyTask.py
```

commit messages:

- _"%MyTask 1:10h"_ for a task result
- _"submission.yaml"_ for a submission


### 0.4 `sedrila instructor`: Instructor commit contents

The `sedrila instructor` command reads `student.yaml`, retrieves `course.json` from `course_url`,
identifies valid task names, intersects them with `submission.yaml` contents,
and offers those tasks for review in the webapp. 
When a task is accepted or rejected, the `CHECK` entry in `submission.yaml` gets replaced:

```
submission.yaml:
    MyTask: ACCEPT
```

commit message (signed commit):

- _"submission.yaml checked"_

Next time a student visits the webapp, it will show a table of not only the student worktimes
invested into tasks, but also their acceptance status and the timevalue of accepted tasks.


## 1. Requirements-level design decisions

- We use YAML for handwritten structured data and JSON for machine-generated structured data.
- We use Markdown as the main source language to keep authoring simple.
- Course-level metadata (chapters and taskgroups) and course configuration data is stored in 
  a single YAML file for an easy overview.
- Task-level metadata is stored in YAML format at the top of each task Markdown file
  to obtain locality and to make it easier to randomize task selection when
  creating a course instance.
- We use a various custom Markdown extensions ("macros") for
    - file-local table of contents;
    - value-added integrity-checked links to tasks, taskgroups, chapters,
      and glossary entries;
    - embedding instructor-only content to be used for the instructor version of the webpages;
    - embedding highlighted optional hints (with fold/unfold functionality);
    - other preconfigured formatting, in particular for structuring the content of task descriptions
      into background, goal, instruction, and deliverables ("submission") parts.
- We use plain, mostly passive HTML for the generated course webpage, 
  with almost no JavaScript.
- We support localizing a fork of a sedrila course in a manner that can avoid most
  merge conflicts with later improvements of the original course.
- We use a student git repository for all solution transportation and bookkeeping.


## 2. Student work bookkeeping architecture

In a nutshell, the bookkeeping of _actual_ work hours worked by a student 
and of _"earned value"_ effort hours (called "timevalue") certified by an instructor
is based on the following ideas:

- When students commit a partial or completed task XYZ, they use a prescribed format 
  for the commit message as described on the [students page](docs/students.md).
- A script can collect, accumulate, and tabulate these _actual_ work times for the student's information
  and show them side-by-side with the timevalues (_expected_ work times).
  The information is also useful for evidence-based improvement of the course contents.
- When students want to show a set of solutions for tasks to an instructor,
  they write the task names to a file `submission.yaml`.
- The instructor checks those tasks, adds checking results into that file,
  and commits it. This commmit is cryptographcally signed.
- `course.json` is published along with the webpages.
  It provides course metadata that is needed for operations in the
  "student" and "instructor" parts of sedrila, such as
  the list of all tasks with their dependencies and timevalues,
  the list of all instructors and their public key fingerprints,
  and a few others.
- The script that computes the "value earned" effort hours 
    - finds all `submission.yaml checked` commits that were made by an instructor
    - extracts the list of accepted tasks from them, and
    - tabulates those tasks and computes the sum of their timevalues (taken from `course.json`).
- That script can also tabulate what the instructor did not accept, which makes practical
  a rule that says a task will only count if it gets accepted no later than upon second (or third?) try.


## 3. Task solution state lifecycle

The basic idea of sedrila is: a student works on a task, submits it.
An instructor accepts it. Or an instructor rejects it and the student resubmits later.
The process must be immune against whatever the student writes into `submission.yaml`
and must process only the sensible entries.

A task is **submittable** if it exists AND is not in state `ACCEPT` AND has `remaining_attempts > 0`.


### LC1: `sedrila student` prepares list of submittable tasks

The `sedrila student` submission command (see `subcmd/student.py:cmd_prepare`):
- determines each task's state from the commit history,
- finds all worktime entries in the commit history,
- reads the existing `submission.yaml`, ignoring entries for non-submittable tasks
  and entries whose mark is not `CHECK` or `NOCHECK`,
- adds `NOCHECK` for all further submittable tasks that have a worktime entry,
- persists `submission.yaml`.

Implementation: existing `CHECK` entries for submittable tasks are kept; all others are deleted
and re-added as `NOCHECK` if eligible. Non-submittable tasks are also removed by
`filter_submission()` (called from `Student.__init__`).


### LC2: student selects tasks for submission

sedrila then starts the webapp in which the student can toggle submittable tasks between
`CHECK` and `NONCHECK` (see `subcmd/student.py:cmd_webapp`), each time persisting `submission.yaml`.
The student commits the resulting `submission.yaml`.
Note that sedrila cannot keep the student from modifying `submission.yaml` arbitrarily before the commit.


### LC3: `sedrila instructor` cleans up `submission.yaml`

`sedrila instructor` (see `subcmd/instructor.py:prepare_workdir`) treats `submission.yaml`
as untrusted when in state `SUBMISSION_STATE_FRESH` (i.e. the most recent commit that touches
`submission.yaml` used the message `"submission.yaml"`, meaning it is a student submission commit).
In this state, sedrila removes all entries with a mark other than `CHECK` and persists the result,
transitioning to `SUBMISSION_STATE_CHECKING`.

In addition, `filter_submission()` (called from `Student.__init__`) removes entries for
non-submittable tasks regardless of state, ensuring rejected-for-good tasks never appear.

The four repo-level process states (see `sdrl.constants`) are:
- **SUBMISSION_STATE_FRESH**: untrusted student submission commit — filter before use.
- **SUBMISSION_STATE_CHECKING**: `submission.yaml` is git-modified (filtered but not yet committed).
  Entries are trusted. Initially only `CHECK` entries; later turned into `ACCEPT`/`REJECT`/`REJECTOID`.
- **SUBMISSION_STATE_CHECKED**: deposited in an instructor-signed commit. Push completes the round.
- **SUBMISSION_STATE_OTHER**: none of the above; `sedrila instructor` prints a warning.


### LC4: instructor checks submission

sedrila starts the webapp, allowing the instructor to toggle tasks between
`ACCEPT`, `REJECT`/`REJECTOID`, and `CHECK` (see `participant.py:set_state`),
each time persisting `submission.yaml`.

A `REJECT` action writes `REJECTOID` to `submission.yaml` if the task has `remaining_attempts > 0`
after the action (i.e. the student can resubmit), and `REJECT` if it has not (final rejection).
`REJECTOID` is stored in `submission.yaml`; it is not merely a display state.
Both `REJECT` and `REJECTOID` increment `task.rejections` when the commit is processed by `repo.py`
(both strings start with `"REJECT"`, which is how `_accumulate_timevalues_and_attempts()` detects them).


### LC5: instructor commits

When the instructor commits the prepared `submission.yaml` as an instructor-signed commit
(message `"submission.yaml checked"`), the acceptances and rejections become part of the
validated repo version history and show up in timevalue reports.

A possible complication: if students send their work to multiple instructors and two or more check it,
the later instructor may find the repo in state `SUBMISSION_STATE_CHECKED` after pull,
or may run into a conflict when pushing. The simplest approach is to discard the second instructor commit.


## 4. Incremental build architecture

The authoring system of sedrila implements a fine-grained incremental build:
By means of a persistent cache, only those work steps will be performed upon a new call to
`sedrila author` that are needed to update the existing build output.

The basic cache mechanism is implemented in `cache.py`.

The items ("Elements") involved in the build as inputs, outputs or intermediate products are
defined in `elements.py` and `course.py`. The latter contains those items that are part of
the overall sedrila content model: Course, Chapter, Taskgroup, Task.

The orchestration of the build is then very simple and is implemented in `directory.py`.
Its basic idea is that there is an ordering of the Element types such that all depends-on
edges in the dependency graph will point towards Elements that are earlier in that ordering,
so that the build can proceed type-by-type forwards through that ordering.
`directory.py` therefore maintains a directory of all entries accessible separately for each type.

The method-level design of the build is documented at the top of `elements.py`.

The `Step` class (also in `elements.py`) is used for intermediate build products 
(e.g., `MetadataDerivation`). Steps declare dependencies on sources
and participate in incremental builds by checking if their dependencies have changed.


## 5. Layering

Import dependencies between modules should obey the following layering, 
from lowest to highest:

- Layer 0 (basic modules): `base`
- Layer 1 (domain-independent modules): `cache`, `git`
- Layer 2 (domain model):
    - 2.1 basic parts: `sdrl.constants`, `sdrl.html`
    - 2.2 technology-centric parts: `sdrl.repo`, `sdrl.interactive`, `sdrl.macros`, `sdrl.markdown`, `sdrl.argparser`
    - 2.3 authoring: `sdrl.macroexpanders`, `sdrl.replacements`, `sdrl.glossary`
    - 2.4 build mechanism: `sdrl.elements`, `sdrl.directory`, `sdrl.partbuilder`
- Layer 3 (integration layer): `sdrl.course`, `sdrl.participant`
- Layer 4 (control layer, main business logic): `sdrl.subcmd.*`


## 6. Simplicity principles, style

`sedrila` strives for simplicity in many ways.
Here are some design rules that should be followed in this spirit:

- Avoid introducing highly specialized functionality.
  All features of `sedrila` should be used regularly.
- Simple package structure: Since `sedrila` is not very large,
  we prefer having a few larger modules (hundreds of lines) in a fairly flat structure
  over scattering the functionality over many small modules in a deeply nested structure.
- Do imports globally (at the top of the file, not in a function)
  unless there are technical needs to do otherwise.
- Import modules (entire files), not individual names from modules.
  Whenever full module names become too cumbersome, introduce mnemonic abbreviations.
  Reuse existing abbreviations consistently (e.g. `import datetime as dt`).
- Emulate the style of existing code. 
  We follow [PEP 8](https://peps.python.org/pep-0008/) in many, but not all respects.
  For line length, use a soft limit of 100, hard limit of 120.
  Strive to follow [PEP 20](https://peps.python.org/pep-0020/).
- Write helpful comments; avoid comments stating only the obvious.
- If you need a visual block structure in a long function, introduce blocks by a comment
  ending in a colon, not by an empty line.
  Existing code often uses the forms `# ----- abc:` for level 1 and `# --- defghi:` for lower levels.

