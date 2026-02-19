# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
by means of signed commits.


## Development Commands

### Building and Testing

```bash
# Run all tests
pytest

# Run tests from specific module (tests are in py/tests/ and py/sdrl/tests/)
pytest py/tests/base_test.py
pytest py/sdrl/tests/macros_test.py

# Run with specific Python path (configured in pyproject.toml)
PYTHONPATH=py pytest

# Build package
poetry build

# Install dependencies
poetry install
```

### Running the Tool

```bash
# Author mode: Build a course website
sedrila author --config sedrila.yaml --log DEBUG targetdir

# Author mode with incremental build (default)
sedrila author sedrila.yaml outputdir

# Clean build (purge cache)
sedrila author --clean sedrila.yaml outputdir

# Include stages in build
sedrila author --include_stage alpha sedrila.yaml outputdir

# Student mode: View progress and prepare submissions
sedrila student [workdir]
sedrila student --init  # Initialize student.yaml

# Instructor mode: Evaluate student submissions
sedrila instructor studentrepo/
sedrila instructor --check-protocols student.prot author.prot
```

### Renaming Parts

```bash
# Rename a task/taskgroup/chapter across all files
sedrila author --rename OldTaskName NewTaskName sedrila.yaml outputdir
```

## Architecture

### Three-Phase Content Model

1. **Source representation** (author mode): Extended Markdown files with YAML metadata headers in a hierarchical directory structure
2. **Website generation**: Static HTML with minimal JavaScript, plus `course.json` metadata
3. **Student/instructor workflows**: Git-based submission and evaluation using cryptographically signed commits

### Hierarchical Structure

```
Course
└── Chapter (chapter-*.html)
    └── Taskgroup (subdirectory)
        └── Task (*.md files, rendered to *.html)
```

Each level has:
- An `index.md` file with YAML metadata header
- Optional `stage:` attribute for phased content release
- Tasks have: `timevalue` (expected hours), `difficulty` (1-5), `assumes`/`requires` (dependencies)

### Incremental Build System

The author command uses a sophisticated caching mechanism:
- **`cache.py`**: Core cache implementation tracking file dependencies and modification times
- **`sdrl/elements.py`**: Defines Element types (inputs, outputs, intermediate products)
- **`sdrl/directory.py`**: Orchestrates build by processing Element types in dependency order
- **`sdrl/course.py`**: Defines Course, Chapter, Taskgroup, Task classes with builder variants

Builder classes (e.g., `Coursebuilder`, `Taskbuilder`) are used in author mode and inherit from corresponding base classes used in student/instructor modes.

### Module Layering

The codebase follows strict layering (enforced by convention):

- **Layer 0**: `base` - Basic utilities
- **Layer 1**: `cache`, `sgit` - Domain-independent modules
- **Layer 2**: Domain model
  - 2.1: `sdrl.constants`, `sdrl.html`
  - 2.2: `sdrl.repo`, `sdrl.macros`, `sdrl.markdown`, `sdrl.argparser`
  - 2.3: `sdrl.macroexpanders`, `sdrl.replacements`, `sdrl.glossary`
  - 2.4: `sdrl.elements`, `sdrl.directory`, `sdrl.partbuilder`
- **Layer 3**: `sdrl.course`, `sdrl.participant`
- **Layer 4**: `sdrl.subcmd.*` (author, student, instructor, maintainer, evaluator)

### Markdown Extensions ("Macros")

Custom macros provide enhanced functionality:
- `[PARTREF::taskname]` - Links to tasks/chapters/taskgroups
- `[TERMREF::term]` - Glossary term references
- `[TOC]` - Table of contents
- `[INSTRUCTOR]...[ENDINSTRUCTOR]` - Instructor-only content
- `[HINT::...]...[ENDHINT]` - Collapsible hints
- `[SECTION::...]` - Structured task sections (background, goal, instructions, submission)

### Student Workflow

Students commit work with prescribed commit message format (e.g., `"%TaskName 1:10h"` for time tracking). They create `submission.yaml` listing completed tasks with `CHECK` marks. The `sedrila student` command provides a webapp showing progress and timevalue earned.

### Instructor Workflow

Instructors pull student repos and run `sedrila instructor studentrepo/`. The tool:
1. Validates `submission.yaml` entries against `course.json`
2. Presents tasks in a webapp for review
3. Updates `submission.yaml` with `ACCEPT`/`REJECT` marks
4. Creates cryptographically signed commits

The workflow progresses through states: FRESH → CHECKING → CHECKED (defined in `sdrl/constants.py`).

## Code Style

- Follow PEP 8 with soft limit 100 chars, hard limit 120 chars per line
- Import modules globally, not individual names (use abbreviations like `import base as b`)
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

- `pyproject.toml` - Poetry package configuration
- `sedrila.yaml` - Course configuration (for author mode)
- `course.json` - Generated metadata (used by student/instructor modes)
- `student.yaml` - Student identification (in student repos)
- `submission.yaml` - Task submission and evaluation tracking

## Known Issues / Planned Refactoring

There is a documented need to restructure directories (see README.md):
- `py` → `sedrila`
- `sedrila/sdrl/*` → `sedrila/*`
- `templates` → `sedrila/templates`
- `baseresources` → `sedrila/baseresources`

This refactoring will affect import statements throughout the codebase.
