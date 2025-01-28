# Internal technical notes

## Requirements-level design decisions

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


## Student work bookkeeping architecture

In a nutshell, the bookkeeping of _actual_ work hours worked by a student 
and of _"earned value"_ effort hours (called "timevalue") certified by an instructor
is based on the following ideas:

- When students commit a partial or completed task XYZ, they use a prescribed format 
  for the commit message as described on the [students page](docs/students.md).
- A script can collect, accumulate, and tabulate these _actual_ work times for the student's information
  and show them side-by-side with the timevalues (_expected_ work times).
  The information is also useful for evidence-based improvement of the course contents.
- When students want to show a set of solutions for tasks to an instructor,
  they write the task names to a file `submission.yaml`
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
    - extract the list of accepted tasks from them, and
    - tabulate those tasks and compute the sum of their timevalues (taken from `course.json`).
- That script can also tabulate what the instructor did not accept, which makes practical
  a rule that says a task will only count if it gets accepted no later than upon second (or third?) try.
  No such mechanism is implemented so far, though.


## Incremental build architecture

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


## Layering

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

TODO 3: use deply for actual checks of correct layering
