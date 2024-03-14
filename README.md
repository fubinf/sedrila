[![Documentation Status](https://readthedocs.org/projects/sedrila/badge/?version=latest)](https://sedrila.readthedocs.io/en/latest/?badge=latest)

# `sedrila`: Tool infrastructure for building and running "self-driven lab" courses

A "self-driven lab" (SeDriLa) course is one where students select freely 
a subset from a large set of tasks.
The tasks are described with sufficient detail that no guidance from an instructor
is needed most of the time.

sedrila is a command-line tool supporting course authors for authoring a course
and then course instructors and students for executing it.

Find the [documentation at readthedocs](https://sedrila.readthedocs.io).


## Development process: TODO-handling during development

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


## A currently needed refactoring: Target directory structure

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
