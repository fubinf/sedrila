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


### 3.2 Task files

The meat of a SeDriLa course is in the individual task files.
A task file is a Markdown file in a particular format.
The basename of a task file determines the slug and shorttitle for that task.
In contrast to chapter and taskgroup slugs, which are all lowercase,
task slugs (aka tasknames) use CamelCase: A mix of uppercase and lowercase characters
starting with uppercase. No underscores.

A task file starts with metadata in YAML format, followed by Markdown with some extensions.

Here is a small example:  TODO 2: Add taskfile example: metadata, markdown extensions

...


### 3.3 Calling `sedrila`  TODO 2: describe sedrila author calls

...


### 3.4 Templates for HTML layout

The format of the resulting HTML files is determined per page type by the Jinja2 templates
in directory `templates`.
For examples, see https://github.com/fubinf/propra-inf/tree/main/templates

