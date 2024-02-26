# `sedrila`: Tool infrastructure for building and running "self-driven lab" courses

# 1. Overview

## 1.1 What is a self-driven lab course (here known as "a SeDriLa")?

- There is a large number of small tasks, each worth a certain number of work hours
- Within loose constraints, students can pick which tasks they want to work on
- Each task results in a commit (or several) in that student's git repository
- At certain times, students can submit a batch of finished tasks to an instructor or teaching assistant
- The instructor checks some of the task's solution commits and then
  either accepts or rejects the entire batch.
- If accepted, the timevalue assigned to those tasks is booked onto the student's timevalue account,
  which is also represented by a series of commits in the student's git repository.
- When enough hours have accumulated there, that student has successfully finished the course.

Instructor commits are signed such that they cannot be forged.


## 1.2 `sedrila` is opinionated

- It assumes that the course content is so useful and motivating for the students
  that they are unlikely to cheat.
- It assumes that SeDriLas are (or could become) Open Educational Resources.
  This means that all information that is accessible to the teaching assistants 
  is also accessible to the students.
- It takes a low-tech approach and assumes that content has a simple structure
  because the tasks rely heavily on _external_ materials available on the web.
  The SeDriLa itself has a simple text layout, few images of its own,
  and no local videos or high-tech active content.  
  The idea behind this is to make it realistic to keep the SeDriLa fresh and up-to-date over time.
- SeDriLas are pass/fail, they are not graded, because that would be incompatible
  with the above goals.


## 1.3 What does the `sedrila` tool do?

The tool serves three target audiences: 
first course authors, then students, and finally instructors. 
Correspondingly, it basically has three functions:

- `author` generates a SeDriLa instance from a SeDriLa template.  
  - The template is a directory tree 
    (maintained in a git repository and developed much like software by the course owners)
    with a prescribed structure that contains all the task descriptions, written in Markdown.
  - The instance is a directory of static HTML pages.
  - The generation is controlled by a configuration file.
- `student` tells the students how many hours are on their timevalue account so far
  and helps them prepare a submission to an instructor.
- `instructor` supports instructors when evaluating student solutions:
  retrieving student repos, validating their submission file, 
  recording the instructor's feedback.


# 2. How to use `sedrila`

## 2.1 User installation

Get [pipx](https://pipx.pypa.io/stable/installation/) and then do

```
pipx install sedrila
```


## 2.2 Usage instructions

There are separate instructions for each user group:

- [Course authors](doc/authors.md) 
  who formulate tasks and decide their timevalues before a SeDriLa course starts.
- [Students](doc/students.md) 
  who take the course.
- [Instructors](doc/instructors.md)
  who check solutions of tasks when students submit them.


## 2.3 Developer installation

In case you want to make changes to sedrila yourself,
this is how to set up development:
Get [poetry](https://python-poetry.org/docs/) and then do

```
git clone git@github.com:fubinf/sedrila.git
cd sedrila
poetry install
alias act_poetry="source $(poetry env info --path)/bin/activate"
act_poetry
alias sedrila="python `pwd`/py/sedrila.py"
sedrila --help
```

`poetry install` creates a venv and installs all dependencies into it.  
Put the `act_poetry` alias in your `.bashrc` and use it each time you want to work
on a poetry-based developer install like this.  
As usual, use `deactivate` to deactivate the poetry-generated venv when needed.  
Put the `sedrila` alias in your `.bashrc` and use it each time you want to call
sedrila conveniently; replace the ``pwd`` with the sedrila directory.
(This alias will soon be replaced by a sedrila executable in the venv.)


# 3. Internal technical notes

## 3.1 Some design decisions

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
  with only very little JavaScript.
- We support localizing a fork of a sedrila course in a manner that can avoid most
  merge conflicts with later improvements of the original course.
- We use a student git repository for all solution transportation and bookkeeping.


## 3.2 Bookkeeping architecture

In a nutshell, the bookkeeping of _actual_ work hours worked by a student 
and of _"earned value"_ effort hours (called "timevalue") certified by an instructor
is based on the following ideas:

- When students commit a partial or completed task XYZ, they use a prescribed format 
  for the commit message as described on the [students page](doc/students.md).
- A script can collect, accumulate, and tabulate these _actual_ work times for the student's information
  and show them side-by-side with the timevalues (_expected_ work times).
  The information is also useful for evidence-based improvement of the course contents.
- When students want to show a set of solutions for tasks to an instructor,
  they write the task names to a file `submission.yaml`
- The instructor checks those tasks, adds checking results into that file,
  and commits it. This commmit is cryptographcally signed.
- `course.json` is published along with the webpages.
  It lists all tasks with their dependencies and timevalues
  and all instructors and their public key fingerprints.
- The script that computes the "value earned" effort hours uses `course.json` to
  - find all `submission.yaml checked` commits that were made by an instructor
  - extract the list of accepted tasks from them, and
  - tabulate those tasks and compute the sum of their timevalues.
- That script can also tabulate what the instructor did not accept, which makes practical
  a rule that says a task will only count if it gets accepted no later than upon second (or third?) try.
  No such mechanism is implemented so far, though.


## 3.3 TODO-handling during development

We use this convention for the development of `sedrila`.
It may also be helpful for course authors if the team is small enough.

If something is incomplete, add a TODO marker with a priorization digit:
- `TODO 1`: to be completed soon (within a few days)
- `TODO 2`: to be completed once the prio 1 things are done (within days or a few weeks)
- `TODO 3`: to be completed at some later time (usually several weeks or more into the future,
  because it is big) or never (because it is not-so-important: "nice-to-have features")

Add a short description of what needs to be done. Examples:
- `TODO 1: find proper formulation`
- `TODO 2: restructure to use ACME lib`
- `TODO 3: add automatic grammar correction`

If you intend to do it yourself, add your name in parens:  
`TODO 1: find proper formulation (Lutz)`

Then use the IDE global search to work through these layer-by-layer.
Demote items to a lower priority when they become stale or remove them.
Kick out prio 3 items when they become unlikely.


## 3.4 Target directory structure

The current layout of the source tree is wrong.
Currently, the `templates` and `baseresources` directories will end up 
as top-level directories when the package is installed,
which means they will clash with any top-level modules of that name
anywhere in our dependencies.

We need to perform the following refactorings to arrive at a proper structure:

- `py` --> `sedrila`: This will be the top level directory that gets installed.
- `sedrila/sdrl/*` --> `sedrila/*`: We remove the now-intermediate namespace.
  This implies joining the current `sdrl/tests` into `sedrila/tests`.
- `templates` --> `sedrila/templates`: The HTML templates simply become part of the
  tree to be installed.
- `baseresources` --> `sedrila/baseresources`: Ditto.
- `doc` --> `docs`: This is the more common name. 
  Requires fixing some links in the markdown.

These changes require a lot of changes of import statements.
For instance, the current module `base` will become `sedrila.base`
and `sdrl.course` will become `sedrila.course`.
The logic for computing `sedrila_libdir` in `courses.py` must be adapted.
The files lists in `pyproject.toml` must be corrected.
