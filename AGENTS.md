# AGENTS.md

This file provides guidance to coding agents when working with code in this repository.

## Project Overview

`sedrila` is a command-line tool for building and running "self-driven lab" (SeDriLa) university courses. 
In these courses, students freely select tasks from a large set, work on them independently, 
commit their work to git repositories, and request evaluation from instructors. 
The tool supports three main roles: authors (who create courses), students (who complete tasks), and instructors (who evaluate submissions).
There are auxiliary roles as well: maintainers (who find broken spots in courses and repair them),
evaluators (who analyze the progression of a cohort through a course instance), and
server (which is just a webserver, not a human being; used by authors for looking at the rendered course locally).

Support for authors is mostly about describing tasks (in Markdown plus extensions) and rendering
them into HTML efficiently (incremental build).

Support for students and instructors revolves around submitting task solutions for inspection (students)
and accepting/rejecting such solutions (instructors). 
Acceptance/rejection is recorded in the student's git repository used for creating and submitting solutions
by means of signed commits (involving GPG).


## Development Commands

### Building and Testing

```bash
# Run all tests
pytest

# Check the module layering (configured in pyproject.toml)
uv run lint-imports

# Build package
uv build

# Install dependencies
uv sync
```

### Running the Tool

```bash
# Author mode: Build a course website with incremental build
sedrila author build --config sedrila.yaml --include_stage alpha --log DEBUG targetdir
sedrila author build outputdir  # using sedrila.yaml by default and only mature tasks

# Student mode: View progress and prepare submissions
sedrila student init  # Initialize student.yaml (interactive)
sedrila student import-keys  # teach GPG about the instructors
sedrila student menu  # Select tasks for submission and submit them

# Instructor mode: Evaluate student submissions
sedrila instructor status studentrepo/  # Show summary of previously accepted/rejected submissions
sedrila instructor menu  # TUI for calling webapp for accepting/rejecting and for commit+push 
```

### Renaming Parts

```bash
# Rename a task/taskgroup/chapter across all files
sedrila author rename OldTaskName NewTaskName
```

## Architecture

### Three-Phase Content Model

1. **Source representation** (author mode): Extended Markdown files with YAML metadata headers in a hierarchical directory structure
2. **Website generation**: Static HTML with minimal JavaScript, plus `course.json` metadata
3. **Student/instructor workflows**: Git-based submission and evaluation using cryptographically signed commits

### Hierarchical Structure

```
Course
└── Chapter (rendered to chapter-*.html)
    └── Taskgroup (from subdirectory)
        └── Task (*.md files, rendered to *.html)
```

Each level has:
- An `index.md` file with YAML metadata header
- Optional `stage:` attribute for phased content release
- Tasks have: `timevalue` (expected hours), `difficulty` (1-4), `assumes`/`requires` (dependencies)

### Incremental Build System

The author command uses a sophisticated caching mechanism:
- **`sedrila/base/cache.py`**: Core cache implementation tracking file dependencies and modification times
- **`sedrila/framework/elements.py`**: Defines Element types (inputs, outputs, intermediate products)
- **`sedrila/framework/directory.py`**: Orchestrates build by processing Element types in dependency order
- **`sedrila/course/course.py`**: Defines Course, Chapter, Taskgroup, Task classes with builder variants

Builder classes (e.g., `Coursebuilder`, `Taskbuilder`) are used in author mode and inherit from corresponding base classes used in student/instructor modes.

### Markdown Extensions ("Macros")

Custom macros provide enhanced functionality, e.g.:
- `[PARTREF::taskname]` - Links to tasks/chapters/taskgroups
- `[TERMREF::term]` - Glossary term references
- `[INSTRUCTOR]...[ENDINSTRUCTOR]` - Instructor-only content
- `[HINT::...]...[ENDHINT]` - Collapsible hints
- `[SECTION::...]` - Structured task sections (background, goal, instructions, submission)

### Student Workflow

Students commit work with prescribed commit message format `"%TaskName 1:10h"` for time tracking. 
Student webapp creates `submission.yaml` listing completed tasks with `CHECK` marks.
It also shows their progress (accepted/rejected tasks and their timevalue sum).

### Instructor Workflow

`sedrila instructor menu studentrepo/` does this:
1. Pulls the repo.
2. Validates `submission.yaml` entries against `course.json` and history
2. Presents tasks in a webapp for review
3. Updates `submission.yaml` with `ACCEPT`/`REJECTOID`/`REJECT` marks
4. Creates cryptographically signed commit

Progresses through states: FRESH → CHECKING → CHECKED (defined in `sedrila/base2/constants.py`).

## Code Style

- Follow PEP 8 with soft limit 100 chars, hard limit 120 chars per line
- Import modules globally, not individual names (use abbreviations like `import sedrila.base.base as b`)
- Prefer few larger modules over many small ones
- Use block comments ending in colons for structure: `# ----- section name:`
- Write helpful comments, avoid stating the obvious
- Emulate existing code style consistently

## TODO Priority Convention

The project uses numbered TODO markers:
- `TODO 1:` - Complete within days
- `TODO 2:` - Complete within days/weeks after prio 1
- `TODO 3:` - Nice-to-have features, complete later or possibly never

## Important Files

- `pyproject.toml` - uv/hatchling package configuration
- `sedrila.yaml` - Course configuration (for author mode)
- `course.json` - Generated metadata (used by student/instructor modes)
- `student.yaml` - Student identification (in student repos)
- `submission.yaml` - Task submission and evaluation tracking (in student repos)

## Status / Next step

...