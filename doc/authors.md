## `sedrila` use for course authors

What you need to provide as a course author:
- One plain text file per potential task.  
  That file contains metadata (at the top of the file in Yaml format) and
  the task description offered to the students (including
  the instructions for the instructor, all in Markdown format).
- Tasks are arranged in groups in two levels.
  You need to provide an `index.md` file for each group.
  These are structured like the task files, but with fewer metadata.
  - 'chapters' (typically 3 to 6) form the top level
  - 'taskgroups' (typically 2 to 6 per chapter) form a second level below that
- A central configuration file `sedrila.yaml`, which contains global configuration data,
  global metadata and most metadata for chapters and taskgroups.
- Page format templates to be used for the rendered HTML pages
  (in [Jinja2](https://jinja.palletsprojects.com/en/3.1.x/) format, 
  defaults are included and are usually sufficient).
- A CSS file (a simple default is included and is often sufficient).


### 3.1 `sedrila.yaml`: The global configuration file

This is best explained by example:

https://github.com/fubinf/propra-inf/blob/main/sedrila.yaml

About the entries:

- `title` and `shorttitle`: can be chosen freely at all levels (course,
  chapters, taskgroups).
  Titles are used for headings and full menus and links, 
  shortitles for breadcrumb navigation or shorter links.
- `baseresourcedir`, `chapterdir`, `templatedir`:
  purely internal names of interest to course authors only.
  They describe the directory structure.
  The names of directories below `chapterdir` are the slugs of chapters (level 1)
  and the slugs of taskgroups (level 2).
  Slugs are used for the filenames in the generated HTML directory.
- `instructors`: The source of truth for who can give students credit 
  for their work. 
  When they accept or reject student work in a _"submission.yaml checked"_ commit,
  instructors must sign that commit. 
  The `instructors.fingerprint` entries (of GnuPG GPG key fingerprints) determine,
  which signatures `sedrila` will consider valid.
- `chapters`: describes the course content at the chapter and taskgroup level.
  The individual tasks are found by inspecting all `*.md` files in a taskgroup directory.


### 3.2 `index.md` files for chapters and taskgroups

Each chapter has its own 2-level directory tree.  
Each taskgroup within a chapter has its own directory, containing the task files.

The top-level directory of any chapter and the directory of a taskgroup must contain
a file `index.md`.
It follows the same format conventions as described below for task files.
The only metadata attributes valid in index files, however, are
`description` and `status`.


### 3.3 Task files

The meat of a SeDriLa course is in the individual task files.
A task file is a Markdown file in a particular format.
The basename of a task file determines the slug and shorttitle for that task.
In contrast to chapter and taskgroup slugs, which are all lowercase,
task slugs (aka tasknames) use CamelCase: A mix of uppercase and lowercase characters
starting with uppercase. No underscores.

A task file starts with metadata in YAML format, followed by Markdown with some extensions.

Here is a small example: 

```
title: Convention for Git commit messages for work time tracking
description: |
  With very little effort we add super useful metadata to our commit messages
  which later allow understanding how much effort something has consumed.
timevalue: 1
difficulty: 1
status: incomplete
assumes: Git101
requires: CreateRepo
---
Many teams introduce syntactical conventions to be used for commit messages,
in order to obtain additional value from them.

For instance, many teams add the number of a defect tracker entry when the
commit solves that entry or contributes to it.
This may look as follows:
```

The YAML attributes have the following meaning:
- `title`: string, required.    
  How this task will appear in the navigation menu.
- `description`: string (often a few lines long), required.  
  How this task will appear in a tooltip when hovering over a title.
  Often a rationale for the task or something to pique the students' curiosity.
- `timevalue`: integer, required.  
  The number of work hours of credit a student will receive when this task is submitted
  and is accepted by the instructor.
- `difficulty`: integer (1, 2, 3, or 4), required.  
  The difficulty level of the task. Will be shown as markup in the task's menu entry.
  Meaning: 1:very_simple, 2:simple, 3:medium, 4:difficult.
- `status`: string, optional.  
  This can be any length, but only the first word is used semantically as the status, 
  everything else is just comment.
  Currently, the only first word allowed is "incomplete".
  Tasks, task groups, or chapters marked as incomplete will be left out of the generated
  web pages, unless a flag is provided in the sedrila call to include them as well.
- `assumes`: string (a comma-separated list of task names), optional.  
  The present task assumes that the student already possesses the knowledge that can be learned from 
  those tasks, but the student can decide whether they want to do the tasks or have the knowledge
  even without doing them.
  The list will be shown as tooltip-based markup in the task's menu entry.
  If the list is empty, leave out the entry.
- `requires`: string (a comma-separated list of task names), optional.  
  Like assumes, but actually doing those other tasks is strictly required so that
  a student cannot get credit for the present task without having (or getting at the same time)
  credit for the required ones.
  The list will be shown as tooltip-based markup in the task's menu entry.
  If the list is empty, leave out the entry.

TODO 2: describe markdown extensions to be used in task files etc.


### 3.4 Calling `sedrila`  TODO 2: describe sedrila author calls

...


### 3.5 Templates for HTML layout

The format of the resulting HTML files is determined per page type by the Jinja2 templates
in directory `templates`.
For examples, see https://github.com/fubinf/propra-inf/tree/main/templates

