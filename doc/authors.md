# `sedrila` use for course authors

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


# 1. Content structure of a sedrila course

## 1.1 `sedrila.yaml`: The global configuration file  # TODO 2: add the missing parts

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


## 1.2 Three-level directory tree: chapters, taskgroups, tasks

The main part of a sedrila course directory tree is the subtree below
the `chapterdir`. It contains the course content and has a structure like this:

```
mychapter1
    index.md
    myfirsttaskgroup
        index.md
        MyFirstTask.md
        MyOtherTask.md
        MyFurtherTask.md
    mysuperinterestingothertaskgroup
        index.md
        MyInterestingTask1.md
        MyInterestingTask2.md
        MyInterestingTask2.md
        MyEvenMoreInterestingTask.md
    mytaskgroup3
        ...
mynextchapter
    ... 
index.md
```

Chapters and taskgroups are included (or not) in the actual generated
course by mentioning them in `sedrila.yaml`, which also defines their order.
All tasks within a taskgroup will be used,
their order is determined by a topological sort according to possible dependencies, see below.

The directory names of chapters and taskgroups must be unique throughout the course.
The file names of tasks must be unique throughout the course.
By convention, chapter and taskgroup names use lowercase, task names use CamelCase.

The top-level `index.md` file is the course's homepage (the landing page).
The `index.md` files at chapter level act as chapter landing pages,
those at taskgroup level act as task group landing pages.
The latter two types follow a similar technical format as described below for task files.


## 1.3 Task files: YAML top matter

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
[SECTION::background::default]
Many teams introduce syntactical conventions to be used for commit messages,
in order to obtain additional value from them.

For instance, many teams add the number of a defect tracker entry when the
commit solves that entry or contributes to it.
This may look as follows:
...
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
- `assumes`: string (a comma-separated list of task or taskgroup names), optional.  
  The present task assumes that the student already possesses the knowledge that can be learned from 
  those tasks, but the student can decide whether they want to do the tasks or have the knowledge
  even without doing them.
  The list will be shown as tooltip-based markup in the task's menu entry.
  If the list is empty, leave out the entry.
- `requires`: string (a comma-separated list of task or taskgroup names), optional.  
  Like assumes, but actually doing those other tasks is strictly required so that
  a student cannot get credit for the present task without having (or getting at the same time)
  credit for the required ones.
  The list will be shown as tooltip-based markup in the task's menu entry.
  If the list is empty, leave out the entry.


## 1.4 Task files: markdown macros for content structure  TODO 2

((Currently described in file `how-to.md` in the sister repo `propra-inf`))


## 1.5 Taskgroup `index.md` files

A taskgroup is described by an `index.md` file in the respective directory,
which consists of a YAML part and text part much like a task file.

The text part provides an idea of the taskgroup's topic area
and in particular motivates why that knowledge is helpful.

The YAML part can have only few entries:
- `description`: Like for tasks.
- `minimum`: integer, optional.  
  The minimum number of tasks that must be done in this taskgroup for the taskgroup
  to be considered done if it appears in a task's `assumes` or `requires` list.
  If no `minimum` entry exists, it means all tasks of the taskgroup must be done.
- `status`: Like for tasks.

## 1.6 Chapter `index.md` files

Just like taskgroup `index.md` files, except that `minimum` entries are not allowed.


# 2. Calling `sedrila`  TODO 2: describe sedrila author calls

The typical call for generating the HTML website from a sedrila course is
`sedrila author outputdir`.
This will create the student version of the website at location `outputdir`
and the instructor version at `outputdir/cino2r2s2tu`.
Both versions will exclude all tasks, taskgroups, and chapters marked as
`status: incomplete` in their metadata.

To include those as well, add option `--incomplete`.  
To obtain more detailed console output during the generation, use `--log INFO`.  
To use an alternative configuration file, use something like `--config myconfig.yaml`.  
If you use a development setup with a source installation of sedrila,
use a shell alias such as 
`alias sedrila='python /my/work/dir/sedrila/py/sedrila.py'`.


# 3. Customization of a sedrila course

## 3.1 Forking an existing course

One design goal of sedrila is that course authors should be able to fork an existing ("upstream")
sedrila course authored by people from a different university and adapt the fork to their needs,
but still be able to receive (and integrate automatically, simply by a git merge) almost all 
of the later changes those other authors may be making.

The support for this has the following components:
- Modifying the overall layout of the overall course website by modifying HTML templates
- Modifying appearance by modifying CSS styles
- Patching parts of task files that talk about university-specific things by
  replacing those parts without modifying the respective file.

These mechanisms are described in the next three subsections. 

## 3.2 Templates for HTML layout

The format of the resulting HTML files is determined per page type by the Jinja2 templates
in directory `templates`.
For examples, see https://github.com/fubinf/propra-inf/tree/main/templates

## 3.3 Modifying the CSS

By convention, the Jinja2 templates of a course should always include exactly two
CSS files: `sedrila.css` and `local.css`.
In the source tree, they both live in the `baseresourcedir` directory defined in
`sedrila.yaml`.

By convention, the original course puts all its styles into `sedrila.css` and
the fork can overwrite some of them in its `local.css`.
In the original course, `local.css` is empty and never changes.

## 3.4 The `<replacement>` mechanism

The authors of the original course identify all parts in their text that refer
to local entities, for instance department names, server URLs, or local rules
for obtaining the credits assigned to the course.

Such text must then be enclosed in a `<replacement></replacement` tag.
Favor fewer, longer replacements over more, shorter ones, to give the authors
of forks more flexibility and to keep the overall number of replacements low.

Here is an example for what course authors might write:

    In the next step, you will create a Git repository, which you will later use
    for submitting solutions to an instructor.

    <replacement id="CreateGitRepo">
    Use your ZeDat credentials to log into [git.imp.fu-berlin.de](https://git.imp.fu-berlin.de),
    the department's GitLab server.
    Create a fresh repository.
    Name it `propra-12345678`, but replace `12345678` by your student ID number.
    </replacement>
    Look up the list of instructors in the file [course.json](course.json)
    and assign commit rights for your repository to each of them.

Fork authors will then create a file `replacements.md`
which consists of only such `<replacement id="...">...</replacement>` blocks,
one after another, separated by whitespace.
One such block must exist for each `id` given in any `<replacement>` tag in the course.

When the course is rendered, sedrila will replace the original replacement blocks
in the markdown source files with the content of the corresponding pair of 
`<replacement id="...">...</replacement>` tags from `replacements.md`,
removing the tags themselves.

As a result, the locale-specific information from the original course will
be replaced by appropriate alternative content when rendering the fork.
As the original course's authors never touch `replacements.md`, 
the fork authors can modify it freely without conflict.
