[![Documentation Status](https://readthedocs.org/projects/sedrila/badge/?version=latest)](https://sedrila.readthedocs.io/en/latest/?badge=latest)

# `sedrila`: Tool infrastructure for building and running "self-driven lab" courses

A "self-driven lab" (SeDriLa) course is one where students select freely 
a subset from a large set of tasks.
The tasks are described with sufficient detail that no guidance from an instructor
is needed most of the time.

sedrila is a command-line tool supporting course authors for authoring a course
and then course instructors and students for executing it.

Find the [documentation at readthedocs](https://sedrila.readthedocs.io).


## 1. Ideas for future versions


### 1.1 A currently needed refactoring: Target directory structure

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

These changes require a lot of changes of import statements.
For instance, the current module `base` will become `sedrila.base`
and `sdrl.course` will become `sedrila.course`.
The logic for computing `sedrila_libdir` in `courses.py` must be adapted.
The files lists in `pyproject.toml` must be corrected.


### 1.2 `instructor`: Handling instructors' trees of student repos

- Process `SEDRILA_INSTRUCTOR_COURSE_URLS` as described in the instructor documentation.
- `sedrila instructor` should keep a JSON file `student_course_urls.json` that maps student usernames
  to the course URL first seen for that student, because if a student ever changed
  the URL in the `student.yaml`, prior signed commits of instructors might become 
  invalid semantically if the new course has a different set of tasks.  
  The map is added to when a `student.yaml` is first seen
  and checked against at each later time.  
  Note that a student taking part a second time, with a fresh repo,
  might require manual editing of that JSON file to remove that entry.
- Better yet, there could be an option `sedrial instructor --allow-repo2` that 
  performs that editing automatically
  and also checks that the new repo contains no instructor-signed commits.
- Command `sedrila instructor --clean-up-repos-home`
  to clean up instructor work directory trees-of-trees
  by deleting all level-1 subtrees in which the `student.yaml`
  has a `course_url` that is not mentioned in the 
  `SEDRILA_INSTRUCTOR_COURSE_URLS`environment variable.
  This option should ask a safety question before starting to work.
- Add `sedrila instructor --http` which presents the local directory tree to localhost as follows:
    - Show directory, each file is a hyperlink, including `..` (except in the starting directory)
    - *.md files get rendered as Markdown
    - *.txt files get shown verbatim
    - *.py file contents are Markdown-rendered as a Python code block. Ditto for other languages.


### 1.3 `author`: Architecture for a fully caching build

How to implement a complete build process that caches all previous results:

- We modify the output directory instead of re-creating it completely.
  `out.bak` no longer exists.
- We need to keep cached the parts that go into each template and render a target file again
  (only) if any of those parts has changed according to a single 'previous rendering time'.
- These are: {homepage,chapter,taskgroup}-content and *-toc, glossary-content,
  task-{linkslist-top,linkslist-bottom,content}.
  They could all be stored in a dbm file.
- Beyond the tocs, we need the list of include files for each part to re-render them
  if an include changed (which will happen for altdir).
- Moving (without renaming) a task or taskgroup still impacts the tocs.
  Moving and renaming is best handled as delete+insert.
- We must delete superfluous files in the output at the end.
- sedrila could then run through the file tree (chapterdir, altdir, itreedir), 
  collecting the files that are newer than the previous rendering time
  or entirely new or deleted
  and rebuild the files suggested by that list plus the known dependencies.
- Dependencies are:
    - All tocs depend on chapter names
    - Chapter tocs depend on taskgroup names
    - Taskgroup tocs depend on task names, assumes, requires, assumed-by, required-by, timevalue, difficulty.
    - Home, chapter, taskgroup, task, glossary contents depend on the respective md file, template, includes.
    - ZIP files depend on all files in their tree
- Should we rebuild zip files from scratch or replace modified files in them?
  Will mostly be relevant for itree.zip only, the others are small and hardly problematic.


## 2. Development process: TODO-handling during development

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
