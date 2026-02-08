# `sedrila` use for course authors

Assumes Unix filenames, will not work properly on Windows.
On a Windows platform, use WSL.

A sedrila course consists of chapters, taskgroups, tasks, a glossary,
possibly .zip directories, and a config file.
Each chapter, taskgroup, or task (as well as the glossary) is represented
by a text file containing YAML metadata ("front matter") and a body
using Markdown markup (plus calls to various sedrila-specific macros, 
plus sometimes "replacement blocks").

The content below describes the details of these data (Section 1,
including advice about what content to put where in Section 1.2),
the markup mechanisms used for authoring (Section 2),
how to generate the course website from the source files (Section 3),
and how to make and maintain a fork of an existing sedrila course (Section 4).


## 1. Content structure of a sedrila course

### 1.0 Overview: What you provide as a course author

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
- A glossary file `glossary.md`, which defines common terms the tasks may refer to.
- Perhaps page format templates to be used for the rendered HTML pages
  (in [Jinja2](https://jinja.palletsprojects.com/en/3.1.x/) format). 
  Defaults are included with sedrila and are usually sufficient.
- Probably some CSS rules in `local.css` or a complete set of CSS rules in `sedrila.css`.
  A default `sedrila.css` is included and may be sufficient.

From these materials, sedrila generates two versions of the course website:
one for students, another for instructors.
The latter is identical to the student version except  
a) it includes the `[INSTRUCTOR]` parts of the tasks (which are missing in the student version) and  
b) it may include an `.htaccess` file for limiting access to the instructors.


### 1.1 `sedrila.yaml`: The global configuration file

This is best explained by example. Have a look at:

https://github.com/fubinf/propra-inf/blob/main/sedrila.yaml (content in German, but that should hardly matter)


#### 1.1.1 Entries for `sedrila author`

- `title`: Course title, can be chosen freely.
  This setting supports the expansion of environment variables using the `$MYVAR` or `${MYVAR}` syntax.
  A title exists at all levels (course, chapter, taskgroup, task).
  Titles are used for headings and for tooltips of links.
- `name`: Short title of the course to be used in the breadcrumb navigation.
  Supports the expansion of environment variables.
- `baseresourcedir` is optional and states where the few CSS and JavaScript files live. 
  Supports the expansion of environment variables.
  Not defining a `baseresourcedir` means to use the built-in default files.  
- `chapterdir`: Relative path of directory in which the course content lives.
  The names of directories below `chapterdir` are the names of chapters (level 1)
  and the names of taskgroups (level 2).
  Slugs are used for two purposes: as short names for identifying a part and
  for the filenames in the generated HTML directory.
  There are five part types: course, chapter, taskgroup, task, and glossary.
  For a task defined by file `abc.md`, the task name is `abc`.
- `altdir`: Relative path of the alternate chapterdir.
  The tree below `altdir` parallels that of `chapterdir`, but contains files
  only where needed.
  The purpose is to create the ability to have parts of the content
  (typically targeted at instructors) in a non-public repository although the course
  overall lives in a public repository.
  That non-public repository would then be included in the overall course's working directory
  by means of a git submodule and `altdir` would point there.
  See the `[INCLUDE]` macro for an explanation of how to use `altdir` content.
- `itreedir`: Relative path of the instructor tree directory.
  This must be a directory with a name ending in `.zip`, say, `itree.zip`. 
  Its contents will be packaged into a ZIP file, which will be placed in the
  instructor subdirectory of the generated website.
  See section "Confidential contents" below for details.
- `templatedir` is also optional and states where the Jinja2 templates for the overall page structures live. 
  Supports the expansion of environment variables.
  Not defining a `templatedir` means to use the built-in default files,  
  which is probably sufficient for most cases.
- `stages`: ordered list of allowed values for the 'stage:' metadata entry for tasks, taskgroups, and chapters.
  Meant to represent the development stage of a part, from a draft entry to a finished one.
  For instance, if stages are `['draft', 'alpha', 'beta']` (the recommended set) and sedrila is called with
  option `--include_stage alpha`, then parts with stage `alpha` or `beta` are used,
  as are those with no `stage:` entry, but parts with stage `draft` will be suppressed.
  No stage is the default and represents finished entries.
- `blockmacro_topmatter`: specifies fixed text that is inserted in the generated HTML files
  before the block content of a SECTION, HINT, NOTICE, WARNING, or INSTRUCTOR block macro call, see below.
  For SECTION, there are entries for each type (1st argument to the macro call) and
  further entries for each subtype (2nd argument).
  The text is HTML text. If the macro has parameters, they can be used by including
  `{arg1}` or `{arg2}` in the string.
  The generated HTML will also use corresponding CSS classes for each of those entire blocks.
  The best way to understand this is to just look at the generated HTML files.
  Special generation logic for SECTION and HINT is hardwired into sedrila,
  but WARNING, NOTICE, and INSTRUCTOR all follow the same logic and you can introduce further
  such macros if you want -- this is the reason why those three are all uppercase in sedrila.yaml.
- `htaccess_template`: In case you are using an Apache httpd webserver for serving
  the generated pages, sedrila can generate into the instructor part an `.htaccess` file
  that instructs Apache to serve those files to instructors only.
  If you do not need such a file, just include no `htaccess_template` entry in your `sedrila.yaml`
  file at all.
  If you want it, put its entire concent into the entry, with the actual instructor usernames
  replaced by one of the following:  
  `{userlist_commas}`: The list of usernames, separated by a comma.  
  `{userlist_spaces}`: The list of usernames, separated by a space.  
  `{userlist_quotes_spaces}`: The list of usernames, each enclosed in double quotes, separated by a space.


#### 1.1.2 Entries for `sedrila student`

- `student_yaml_attribute_prompts`: Optional dictionary of pairs of attribute name and prompt to be used
  for interactively populating the `student.yaml` student identification file 
  during the `sedrila student --init` command.
  The required attributes `course_url, student_name, student_id, student_gituser, partner_gituser`
  have default prompts, which you can overwrite here.
  (Exception: `course_url` cannot be overwritten, because the value is needed to make the customized prompts
  available in the first place.)
  You can add optional attributes.


#### 1.1.3 Entries for `sedrila instructor`

- `participants` (optional): If provided, will generate an encrypted participants list file,
  which is then used by the `instructor` command to emit a warning when examining a submission of 
  a student not on the participants list.
  Three keys need to be present:  
  `file`: name of the participants list input file, which must be a TAB-separated values text file
  with column headers.
  If this value is empty, the entire `participants` entry will be ignored.  
  Supports the expansion of environment variables.  
  `file_column`: name of the column in which the attribute is found by which a participant is identied.  
  `student_attribute`: name of the entry in the student's `student.yaml` file that identifies the student
  in the participants list file.


#### 1.1.4 Entries for both `sedrila instructor` and `sedrila student`

- `instructors`: The source of truth for who can give students credit
  for their work. A list of dictionaries, each of which has the following entries:
  `nameish`: the personal name or nickname of the instructor so students know who they can talk to,
  `email`: the email address of the instructor to which students send their submission requests,
  `gitaccount`: username on the git server that students must allow read/write access of their
  repository so the instructor can deposit their signed _"submission.yaml checked"_ commits
  of accepted submissions,
  `webaccount`: username on the webserver to which the webserver should grant access to the
  instructor part of the website,
  `keyfingerprint`: fingerprint of the GPG key by which the instructor will sign their commits,
  which shows up in git listings and is used by sedrila for signature validation,
  `pubkey`: The GPG public key used for validate instructor signatures as a PGP PUBLIC KEY BLOCK,
  `status` (optional): A brief message or detailed paragraph about the instructor's current availability
  (e.g., "on vacation" or a longer explanation). This is displayed to students when viewing instructors
  during submission. Supports multiline text using YAML multiline syntax (`|` or `>`).
- `former_instructors` (optional): a second list just like `instructors`,
  with the same structure and meaning of entries. 
  The only difference is that the `former_instructors` will not be mentioned in the list of 
  available instructors shown to students when they prepare a submission.
- `allowed_attempts`: Students have a maximum number of times they can present a task
  until it must be accepted by the instructor, called the `allowed_attempts` of that task.
  If the task gets rejected that many times, it will never be accepted later on, i.e.,
  sedrila will never count the timevalue of that task as work that has been done by the student.  
  `allowed_attempts` is a string of the strict form `n + x/h` with the following meaning:  
  Assume you have specified `allowed_attempts: 2 + 0.5/h`,  
  then tasks with a timevalue of 0.5, 1.0, 1.5, 2.0, 3.0, 4.0 hours will have  
  theoretical allowed attempts of 2.25, 2.5, 2.75, 3.0, 3.5, 4.0,
  and actual allowed attempts of 2, 2, 2, 3, 3, 4, respectively.
  Supports the expansion of environment variables.


#### 1.1.5 Entries for all sub-commands

- `chapters`: describes the course content at the chapter and taskgroup level by listing
  the directory name of each chapter and taskgroup.
  See the example linked above for how these entries have to look like.
  The individual tasks are found by inspecting all `*.md` files in a taskgroup directory,
  as described in the next section.


### 1.2 Three-level directory tree: chapters, taskgroups, tasks

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
glossary.md
index.md
```

Chapters and taskgroups are included (or not) in the actual generated
course by mentioning them in `sedrila.yaml`, which also defines their order.
All tasks within a taskgroup will be used,
their order is determined by a topological sort according to possible dependencies, see below.
Chapters and taskgroups group tasks according to topic area or some other kind of task type.

The names of all parts must be distinct (unique) throughout the course.
The top-level `index.md` file is the course's homepage (the landing page).
The `index.md` files at chapter level act as chapter landing pages,
those at taskgroup level act as task group landing pages.
The latter two types follow a similar technical format as described below for task files.


#### 1.2.1 sedrila principle 1: Opinionatedness

The sedrila tool is an opinionated framework: Many decisions regarding what makes a good
SeDriLa course are built into the framework to various degrees.

At the most fundamental level, this is reflected in architectural decisions, such as
the three-level structure described above or the split between a student version
and an instructor version of the generated websites.

At an intermediate level, many of the macros described further down reflect such decisions.
At the least technical level, the present document contains authoring advice at the level
of the natural language course content that is interwoven with how the remainder is designed. 


#### 1.2.2 The 4 factors writing style: Orientation, motivation, instruction, knowledge

The various pieces of writing in a SeDriLa course serve four different generic purposes.
Each purpose is mostly (if not exclusively) followed in certain places within the
technical structure:

- **Orientation:** What is this about?  
  This question is answered in the `index.md` files of chapters and taskgroups
  and in the `goal` sections of tasks.
  Keep those contents very concise.
- **Motivation:** Why should I (as a student) be interested in this?  
  This question is answered in the `background` sections of tasks.
  Keep those contents very concise.
  Move recurring parts to glossary entries.
- **Instruction:** What do I need to do?  
  This question is answered in the `instruction` and `submission` sections of tasks.
  Keep those contents concise and
  see the discussion of the `[EC]`, `[EQ]`, `[ER]`, `[EREFC]`, `[EREFQ]`, and `[EREFR]`
  macros further down for how to avoid redundancy between those two sections.
- **Knowledge** is any knowledge (as opposed to practical skills and experience) we would like 
  students to learn.
  Rather than adding respective information on the side in some task with a different purpose,
  introduce a separate task for which this knowledge is required for solving it;
  submission subtypes `reflection` and `information` are suitable for this purpose.


#### 1.2.3 Further principles: granularity, redundancy-avoidance, cross-referencing

Granularity: Keep tasks small, between 0.5 hours and 4 hours timevalue;
split tasks when they become too large.
Split tasks when they serve more than one or perhaps two purposes at once. 

Avoid duplicating information that is longer than a half-sentence.
Two techniques help in doing so:

- Put information in a glossary entry and refer to that.
- Create a separate task around that information and `assume` that task where needed
  or cross-reference it in another task's text.

Make generous use of cross-references from a task to related other tasks
in order to link tasks beyond the rigid chapter/taskgroup structure.
The global `explains`, `assumes`, and `requires` relationships can do much of that.
Add further cross-references in the text (via the `PARTREF` macros) whereever useful,
perhaps in a `NOTICE` block, often near the end of the `background` section.


### 1.3 Special sedrila markup

In addition to standard Markdown, sedrila provides several additional markup mechanisms:

- **Macros**: Special commands in `[UPPERCASE]` notation for structured content,
  cross-references, file inclusion, and more.
  See Sections 2.0 to 2.8 for details.
- **Replacement blocks**: `<replacement id="...">...</replacement>` tags that allow
  forked courses to substitute locale-specific content. 
  See Section 2.9 for details.
- **Checking specifications** such as `@PROT_SPEC` blocks that allow sedrila to perform
  useful checking for non-authors (instructors, maintainers).
  See Sections 2.10 to 2.12 for details.


### 1.4 Task files: YAML top matter

The meat of a SeDriLa course is in the individual task files.
A task file is a Markdown file in a particular format.
The basename of a task file determines the canonical name of a task.

A task file starts with metadata in YAML format, followed by Markdown with some extensions.

Here is a small example: 

```
title: Convention for Git commit messages for work time tracking
timevalue: 1.0
difficulty: 1
stage: alpha
explains: concept 1, other concept
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
  How this task will appear in long form (e.g. navigation menu tooltip, page title).
- `timevalue`: float, required.  
  The number of work hours of credit a student will receive when this task is submitted
  and is accepted by the instructor.
- `difficulty`: integer (1, 2, 3, or 4), required.  
  The difficulty level of the task. Will be shown as markup in the task's menu entry.
  Meaning: 1:very_simple, 2:simple, 3:medium, 4:difficult.
- `stage`: string, optional.  
  This can be any length, but only the first word is used semantically as the stage, 
  everything else is just comment.
  Tasks, task groups, or chapters marked with too-low a stage (according to the value
  supplied with the `--include_stage` options of the commandline sedrila call)
  will be left out of the generated web pages.
- `explains`: string, optional. Comma-separated list of terms defined in the glossary,
  meaning that the present task description offers relevant information about these terms.
  The task name will be listed among the "explained by" parts in the glossary entry.
- `assumes`: string (a comma-separated list of task or taskgroup names), optional.  
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
  If you provide names of taskgroups or chapters here, they are shown but will be ignored
  by the `instructor` command when checking actual preconditions.


### 1.5 Taskgroup `index.md` files and chapter `index.md` files

A **taskgroup** is described by an `index.md` file in the respective directory,
which consists of a YAML part and text part much like a task file.

The text part provides an idea of the taskgroup's topic area
and in particular motivates why that knowledge is helpful.

The YAML part can have only few entries:
- `title`, `stage`, `explains`: like for tasks.

Likewise, a **chapter** is described by an `index.md` file in the respective directory.
These files work like taskgroup `index.md` files, except that 
`explains` entries are not allowed.


### 1.6 The glossary: `glossary.md` in `chapterdir`

The glossary is a singleton living at the `chapterdir` top-level directory.
It is generated from a source file `glossary.md`.
The YAML topmatter has only one attribute: `title`.

The body of the file mostly consists of term definition blocks.
For the `[TERM]` and `[TERMREF]` macros used in glossary files, see Section 2.


### 1.7 `.zip` directories

At the level of a chapter or a taskgroup, you can place a subdirectory
with a name ending in `.zip`, say, `myarchive.zip`.

Sedrila will zip the contents of that directory into a zipfile of the same name
in the generated output.
The directory structure within that zipfile will reflect the directory structure
both above and below the zipdirectory, so if you have a file, say,
`chapterdir/mychapter/mytaskgroup/myarchive.zip/mysubdir/myfile.txt`,
the generated zipfile `myarchive.zip` will contain an entry
`myarchive/mysubdir/myfile.txt`.

This is useful for supplying learners with resources they can download easily
if multiple files are involved, and still keep those files in an easily editable form.
Use this for handsful of files. For large structures, apply separate repositories.


### 1.8 Other files and directories

Subdirectories at the chapter level or taskgroup level that are not
defined to be chapters or taskgroups in `sedrila.yaml` will simply be ignored.

Subdirectories within a taskgroup directory can be used for holding
INCLUDE files. Any file in them that is not used for `[INCLUDE]` will be ignored.

Files within a taskgroup directory that are not `*.md` files (such as images or 
ready-made `*.tar.gz` download files)
will be copied to the target directory verbatim and with the same name.
The target directory is a single, flat directory (with no subdirectories),
so the name of such a file must be globally unique.
It should therefore start with the taskgroup name or a task name.


### 1.9 Confidential contents: `altdir`, `itreedir`

The course for which sedrila was developed is an Open Educational Resource,
i.e., its sources are public.
This includes parts of the information targeted at instructors to be used for
checking student's submissions.
Some of that information, however, should still be treated as confidential
in order not to tempt students too much to simply look it up.

Two entries in the `sedrila.yaml` file support this:
First, `altdir` ("alternative directory") points to a directory tree of chapters and taskgroups 
similar to `chapterdir` where files can be placed that contain information to be 
made part of the `[INSTRUCTOR]` sections of tasks by means of `[INCLUDE]` and `[PROT]`.
Refer to sections 2.2, 2.6.1, 2.6.3 for explanations of these.
For instance task `<chapterdir>/mychapter/mygroup/mytask.md` may have 
`[INCLUDE::ALT:mytask.md]` as the body of its `[INSTRUCTOR]` block and that
file would then contain the confidential instructor information.
For a file named like the task file, you could even write `[INCLUDE::ALT:]` without any filename.

The confidentiality can be provided by making the `altdir` a git submodule of the
overall SeDriLa git repository and making the submodule repository non-public.
We recommend to keep the `altdir` tree sparse and create only those files and directories 
that are actually needed.

Second, `itreedir` ("instructor tree directory") is to be used where including 
the instructor information only on the website is inconvenient, 
because the instructor needs to process it as a standalone file (e.g. run it as a program).
The `itreedir` entry must point to a directory with a name ending with `.zip`
which would typically be held in the same submodule together with `altdir`.

In the generated website, the entire directory tree below `itreedir`
becomes a single, same-named ZIP file
which can be downloaded and unpacked by instructors in order to make use of the files
as needed.


### 1.10 Naming conventions

From the point of view of the `[PARTREF]` macro, the names of all parts
are in one single namespace, so they must all be unique.
These names are user-facing, so they should also be sort-of natural, not too ugly,
and sufficiently self-explanatory.
They must work nicely for URLs and as the names of files to be created
by students as solutions for these tasks.
The following rules are suggestions for how to achieve these properties.

- Names consist of letters, digits, dashes, and underscores.
  No other characters are allowed.
- In particular, names cannot contain spaces. _Take this one seriously._
- Chapter names should be short: single nouns, capitalized.
- Taskgroup names should be simple nouns or compound nouns.
  Compound names can be written in one word (e.g. in German) or
  with dashes.
- Generic names such as "Basics" are hardly ever a good idea: Basics _of what_?
- Task names are more flexible.  
  (1) For non-technical task names, prefer names that are natural and respect the language's capitalization rules,
  using dashes to separate words.  
  (2) For technical task names that serve as filenames of programming language files,
  obey the conventions of the respective language, at least when entire groups of such tasks occur.
  (3) For tasks that would have overly generic names (e.g. "Output"),
  use a suitable prefix, for instance
  the common programming language filename suffix (e.g. "py-Output" or "py_output")
  or the topic of the task group (e.g. "Unix-Output")
- Use underscores only where this is required or at least natural for technical reasons (e.g. because
  there will be program source files of this name and dashes are not allowed for them).
  Our usual task name word separator is the dash.
- Make sure tasknames are interpretable without seeing the name of the taskgroup
  they belong to. This will often imply using a fixed prefix or suffix for all tasks in a group.
- Consider using task names with different capizalization if that reflects the spelling 
  of an existing thing discussed in that Task (e.g. SQL-WHERE, JavaScript)
- If a task or taskgroup is split into a sequence of consecutive, strongly connected pieces,
  prefer a single appended digit if you want to make this visible.
- Do _not_ use prefixes to enforce a certain task ordering:
  Either the tasks have dependencies that create an ordering
  or the default alphabetical ordering ought to be fine.


## 2. Specialized sedrila markup: Macros, replacement blocks, checking specifications

### 2.0 Introduction to macros

Sedrila extends standard Markdown with macros and replacement blocks.
Macros are special commands written in `[UPPERCASE::parameters]` notation that provide:

- **Block macros** for content structure: `[SECTION]`, `[INSTRUCTOR]`, `[HINT]`, `[WARNING]`, etc.
- **Inline macros** for cross-references: `[PARTREF]`, `[TERMREF]`, `[HREF]`
- **Content inclusion**: `[INCLUDE]`, `[PROT]`, `[SNIPPET]`
- **Enumeration markers**: `[EC]`, `[EQ]`, `[ER]` for numbered instructions
- **Glossary definitions**: `[TERM]`, `[TERMREF]`
- **Utility macros**: `[TOC]`, `[DIFF]`, `[TREEREF]`

General things to know about macros:

- Macros have names in all UPPERCASE and each have 0, 1, or 2 formal parameters.
- Sedrila supplies a fixed set of macros, discussed in the following sections.
- Macro calls come in square brackets, parameters use a `::` as delimiter.    
  Examples: `[SOMEMACRONAME]`, `[OTHERMACRO::arg1]`, `[YETANOTHER::arg1::arg2]`.
- If a macro is not defined or has a different number of parameters than supplied in the call,
  sedrila will complain.
- A macro call cannot be split over multiple lines.
- Some macros serve as markup for entire blocks of text. These macros come in `X`/`ENDX` pairs:  
  ```
  [WARNING]
  body text, as many lines as needed
  [ENDWARNING]
  ```
- Due to the simplistic parser used, most `X`/`ENDX` blocks cannot be nested in another
  `X`/`ENDX` block and both macro calls must be alone on a line by themselves.
- Non-block macro calls can be mixed with other content on a line.


### 2.1 `[SECTION]`/`[ENDSECTION]` macros for content structure

It is useful for learners if tasks follow a recurring content structure,
possibly with corresponding visual structure.
The `[SECTION::sectiontype::sectionsubtype]` macro supports both.

Sections follow one after another; they are usually not nested.  
They are marked up for example like this:
```
[SECTION::goal::idea]
Understand section markup
[ENDSECTION]
```

Section types (like `goal` above) and subtypes (like `idea` above) 
come from a fixed list declared via the
`blockmacro_topmatter` part of `sedrila.yaml`.
Each type and subtype will use corresponding CSS styles in the generated output,
so that the visual appearance can be customized.

Although each sedrila course can hence decide its section structure itself,
sedrila comes with a recommendation:

#### 2.1.1 Recommendation for section usage and `[SECTION]` types

The entire body of a task description is divided into sections; 
the only extra text is possibly a number of `[INSTRUCTOR]`/`[ENDINSTRUCTOR]` blocks
before, between, or (most likely) after the sections.

In contrast, chapters' and taskgroups' `index.md` files can optionally use 
goal and background sections at their top, but then always
continue with section-free text for characterizing the content of the chapter or taskgroup.

The page title is a `<h1>` heading, `[SECTION::...]` macros by convention generate a `<h2>` heading.
Therefore, inside sections you should use (if needed) `### ` headings.

##### 2.1.1.1 `[SECTION::goal::...]`

Short definition what is to be learned (this is the prefered type) or 
achieved (if this is mostly a stepping stone for something else). 

The goal is always formulated in first-person perspective ("I").
It is either short or a bulleted list of short items.
Can be positioned first (this is the prefered structure) or 
nested inside the background section (using [INNERSECTION::goal::...]) or
after the entire background.

##### 2.1.1.2 `[SECTION::background::default]`  

Knowledge required for understanding the instructions and solving the task.

Only present if needed. Keep this short.  
If lots of background are needed, turn it into steps of the instructions.

##### 2.1.1.3 `[SECTION::instructions::...]`  

The main part of the task: Instructions what to do.

More strongly than for other sections, 
this section looks hugely different depending on difficulty level.
See the discussion of difficulty levels above and of instructions subtypes below.

##### 2.1.1.4 `[SECTION::submission::...]`  

Final part of the task: Description what to prepare for the instructor to check.

Characterizes 

- the format (eg. `.md` file or `.py` file or directory with several files),
- the content, 
- and perhaps quality criteria.


#### 2.1.2 Recommendation for section subtypes

##### 2.1.2.1 goal

- `[SECTION::goal::product]`:  
  A work product itself is the task's goal (because we want to have it or want to build on top of it).
  Usually difficulty 3 or 4.
- `[SECTION::goal::idea]`:  
  Understanding a concept or idea is the goal. Difficulty 1, 2, or 3.
- `[SECTION::goal::experience]`:  
  Accumulating experience from actual technical problem-solving is the task's goal.
  Difficulty 3 or 4.
- `[SECTION::goal::trial]`:  
  The task's goal is a mix of the types 'idea' (mostly) and 'experience' (smaller part). 
  Difficulty 1 to 3 (or perhaps 4).


##### 2.1.2.2 background

- `[SECTION::background::default]`:  
  There is only one type of background section.


##### 2.1.2.3 instructions

- `[SECTION::instructions::detailed]`:  
  The instructions are such that the student must merely follow them closely for 
  solving the task and hardly needs to do problem-solving themselves.
  These tasks are easy (difficulty 1 or 2) for the students but
  difficult for the authors, because we need to think of so many things.
- `[SECTION::instructions::loose]`:  
  The instructions are less complete; the student must fill instruction gaps of moderate size
  but we provide information where to look for the material to fill them.
  Difficulty 3 or 4.
- `[SECTION::instructions::tricky]`:  
  The instructions are of a general nature, far removed from the detail required for a solution.
  The student must not only determine many details, but must also make decisions that can
  easily go wrong, making a successful solution much harder.
  Difficulty 4.


##### 2.1.2.4 submission

- `[SECTION::submission::reflection]`:  
  Students submit a text containing their thoughts about something.
- `[SECTION::submission::information]`:  
  Students submit concrete information they found in an inquiry. 
- `[SECTION::submission::snippet]`:  
  Students submit a short snippet of program text, e.g. a shell command (or a few).
- `[SECTION::submission::trace]`:  
  Students submit a log of an interactive session or the output of a program run. 
- `[SECTION::submission::program]`:  
  Students submit an entire program with many moving parts.


#### 2.1.3 `[INNERSECTION]`/`[ENDINNERSECTION]`

If you insist on nesting some of your sections, use a maximum nesting depth of 1
and use the `[INNERSECTION]`/`[ENDINNERSECTION]` pair of macros for the nested section.
It works exactly like `[SECTION]` and the same types and subtypes apply.


### 2.2 Instructor-only information: The `[INSTRUCTOR]` block macro

- `[INSTRUCTOR::heading]`/`[ENDINSTRUCTOR]`:
  This macro creates a distinctly-formatted block of text with a variable heading
  that contains information to be used by the course instructors for deciding acceptance/rejection
  of task solutions submitted by students.  
  The macro has a special status within sedrila: sedrila generates a student version and an
  instructor version of the course and the contents of `[INSTRUCTOR]` blocks will be misssing 
  from the student version.


### 2.3 Other block macros: `[NOTICE]`, `[WARNING]`, `[HINT]`, `[FOLDOUT]`

- `[NOTICE]`/`[ENDNOTICE]`:    
  A semi-important note with potentially different formatting than normal text.
- `[WARNING]`/`[ENDWARNING]`:    
  A warning of a pitfall to be avoided.
  Will render as an eye-catching text box.
- `[HINT::title text]`/`[ENDHINT]`:  
  Information, typically in the instructions section, that is helpful for solving the task
  but that students are intended to find out themselves.
  Therefore, the body text of the hint is not visible initially, only the title text is.
  Students can fold out the hint body when they recognize they need more help.
  Use this in particular for making sure a task that is intended to be
  difficulty 3 does not end up being difficulty 4.
  Use it also to make it likely that a task at difficulty 2 is interesting enough for
  somebody who would rather do difficulty 3.
- `[FOLDOUT::title text]`/`[ENDFOLDOUT]`:  
  Just like `[HINT]`, but without the marker that it is a hint.
  To be used for materials that is lengthy but not important for a first overview of the task,
  often listings.

Of these, only `HINT` and `FOLDOUT` are built into sedrila, 
whereas `NOTICE` and `WARNING` (as well as `INSTRUCTOR` above) are in fact
defined by `sedrila.yaml` and `sedrila.css` only 
and you can define further macros like them if needed.


### 2.4 Macros for hyperlinks: `[HREF]`, `[PARTREF]`, `[PARTREFTITLE]`, `[PARTREFMANUAL]`, `[TERMREF]`

- `[HREF::url]`: Equivalent to the plain Markdown markup `[url](url)`, but avoids the repetition
  of the often-lengthy URL.
- `[PARTREF::partname]`: 
  Create a hyperlink to the part description file for task, taskgroup, chapter, or zipfile `partname`,
  using the partname as the link text.
- `[PARTREFTITLE::partname]`: 
  Ditto, but using the part's title as the link text. Not recommended.
- `[PARTREFMANUAL::partname::link text]`: 
  Ditto, but using the given link text.
- `[TERMREF::term]`:
  Create a hyperlink to the glossary entry `term`; see under glossary below.
- `[TERMREF2::term::shown form]`:
  Create a hyperlink to the glossary entry `term` that is rendered as `shown form`.
  If `shown form` starts with a dash, it will be appended to `term` instead of replacing it.
  This is useful for plural forms: `[TERMREF2::file::-s]` renders as `files`, but refers to `file`.


### 2.5 Macros for instruction enumerations: `[EC]`, `[EQ]`, `[ER]`, `[EREFC]`, `[EREFQ]`, `[EREFR]`

The split between `[SECTION::instructions::...]` and `[SECTION::submission::...]` is often inconvenient
both for authors and students: The instructions may contain, say, 17 steps, and 5 of those
produce some part of what is to be submitted in the end.
Having to refer to those 5 in the `submission` section manually is laborious and error-prone.

The macros `[EC]`, `[EQ]`, `[ER]` all generate a highlighted label containing a number
that counts upwards in each call within each task.
In the macro names, E stands for enumeration,
C stands for command, Q for question, R for requirement.
By having three separate counters, one can have tasks
that mix up to three different submission parts of different character, 
e.g. a protocol file create by the `script` command for commands,
a markdown file written manually for questions,
a python file implementing requirements, etc.

The content of `[SECTION::submission::...]` can then often be a fixed boilerplate text module
for each submission type, which can nicely be reproduced identically via the 
`[INCLUDE]` macro (see below).

In `[INSTRUCTOR]`, one may want to refer to some of those pieces with like markup.
This can be created using the `EREFx` macros (for "reference").
E.g. `[EREFC::3]` would refer to the third call of the commands enumeration.

Sedrila does not implement a full cross-reference mechanism with labels and label references,
because of the strong within-task locality that the cross-references will usually have,
which makes manual cross-referencing the simpler approach.

### 2.6 Macros for file inclusion: `[INCLUDE]`, `[SNIPPET]`, `[PROT]`

#### 2.6.1 `[INCLUDE]`

`[INCLUDE::filename]`: inserts the entire contents of file `filename` verbatim
into the Markdown input stream at this point.

- `filename` is a path relative to the directory of the file containing the `INCLUDE` call.
- Useful for having small Python programs (etc.) as separate files during development,
  so they can be executed and tested.
  The students copy/paste the file from within the page in the web browser.  
  We recommend to put include files relevant for a single task or task group into the task group directory.
- You can also use absolute paths: `[INCLUDE::/_include/some-blurb.md]` will include a blurb used in
  many places that lives in a directory (in this case called `_include`) directly below the 
  configuration setting `chapterdir`.

`[INCLUDE]` pathnames can use the prefixes `ALT:` or `ITREE:` to refer to other
base directories (see Section 1.9 "Confidential contents"):
- `[INCLUDE::ALT:filename]` includes from the `altdir` tree
- `[INCLUDE::ITREE:filename]` includes from the `itreedir` tree


#### 2.6.2 `[SNIPPET]`

`[SNIPPET::filespec::snippetname]` is a cousin of `[INCLUDE]`;
it serves to include _parts of_ a file.
As with `[INCLUDE]`, `filespec` accepts absolute or relative paths and the `ALT:` and `ITREE:` prefixes.
`snippetname` must be a conventional identifier (letters, digits, underscores only).  
The purpose is inserting code snippets from entire solution files, which avoids
textual duplication (and hence the problems that would come with it):

```markdown
[SNIPPET::ALT::mysnippet]                              <!-- mirrors current task filename under altdir -->
[SNIPPET::include/demo.py::mysnippet]                  <!-- relative path -->
[SNIPPET::/Basis/IDE/include/demo.py::mysnippet]       <!-- absolute path -->
[SNIPPET::ITREE:demo.py::mysnippet]                    <!-- relative path with ITREE -->
[SNIPPET::ITREE:/Basis/IDE/demo.py::mysnippet]         <!-- absolute path with ITREE -->
```

Mark snippets inside solution files with single-line comments whose contents are `SNIPPET::name` and `ENDSNIPPET`
(optionally `ENDSNIPPET::name`). 
Supported comment syntaxes include the usual one-line markers of many languages 
(`#`, `//`, `--`, `;`, `!`, `'`, …) as well as HTML comments `<!-- -->` for Markdown files. 
Examples:

```python
# SNIPPET::mysnippet
def helper():
    return 42
# ENDSNIPPET
```

```c
// SNIPPET::loop_example
for (int i = 0; i < n; ++i) {
    printf("%d\n", i);
}
// ENDSNIPPET
```

Snippet content (excluding marker lines) is inserted verbatim, preserving formatting.
It is an error if no snippet of that name exists.
Snippet validation occurs automatically during task file builds, like `[INCLUDE]` file references.


#### 2.6.3 `[PROT]`

Include a rendered command protocol.
`[PROT::filename.prot]`: works much like `[INCLUDE]` and obeys the same rules for the filenames.
The difference is in file contents: With `[INCLUDE]`, contents are treated as markdown.
If you want to include source code of some sort, you can put the `[INCLUDE]` in a
triple-quote source code block and get the expected results.

With `[PROT]`, in contrast, a sedrila-specific rendering is applied.
This rendering assumes the file contains content copy/pasted from a terminal session
in a shell window.
The shell prompt must be a two-line prompt using the following structure:  

```
export PS1="\u@\h \w \t \!\n\$ "
```

You can add coloring with ANSI sequences thusly:
```
export PS1="\[\e[1;33m\]\u\[\e[1;31m\]@\h \[\e[0;32m\]\w \[\e[0;37m\]\t \[\e[44m\] \! \[\e[40m\]\n\$ "
```

The `[PROT]` macro will spot lines that have the structure of that prompt
and format them in multiple colors.
It will assume the next line is the actual command and format that in a single color.
It will assume everything beyond (up to the next prompt) is command output and format that
in yet another manner, all based on CSS classes which you can look up in the output
in order to define suitable formatting.
Line structure and spaces are preserved.


### 2.7 Glossary macros: `[TERM]`, `[TERM0]`, `[TERMREF]`

Term definition blocks in the glossary file look like this:
```
[TERM::myterm|otherform|yet another]
As much markdown text as required for defining the term.
- may have itemized lists 
- and other markup
- in particular calls to the [TERMREF]/[TERMREF2] macros described above
[ENDTERM]
```
This defines a term that shows up in the glossary as `myterm`,
but can be referenced by any of 
`[TERMREF::myterm]`, `[TERMREF::otherform]`, or `[TERMREF::yet another]`. 

Use `[TERM0]` in case no definition of the term is needed because the automatically added
cross-references to parts mentioning and (in particular) explaining it suffice.


### 2.8 Other macros
#### 2.8.1 `[TOC]`, `[DIFF]`

- `[TOC]`: Generates a table of contents from the Markdown headings present in the file.
  For the glossary, ignores headings and instead makes an alphabetical list of all term entries 
  (main terms and synonyms).
- `[DIFF::level]` generates the task difficulty mark for the given level, from 1 (very simple) to 4 (difficult).


#### 2.8.2 `[TREEREF]`

`[INSTRUCTOR]` blocks in tasks can refer to files in the `itreedir` by mentioning their path
in a call to macro `[TREEREF]`.

`[TREEREF::mytask.py]`, when called in `<chapterdir>/mychapter/mygroup/mytask.md`,
refers to the file `<itreedir>/mychapter/mygroup/mytask.py` and will render as
`<span class="treeref-prefix"></span><span class="treeref">mychapter/mygroup/mytask.py</span><span class="treeref-suffix"></span>`
which can be formatted with appropriate CSS.  
Just like with `[INCLUDE]`, pathnames can be relative or absolute, so 
`[TREEREF::/mychapter/mygroup/mytask.py]` is equivalent to the above,
which is useful for trees that pertain to several tasks.


### 2.9 Replacement blocks: `<replacement>...</replacement>`

A replacement block looks like this:
```
some text <replacement id="someId">text to be replaced</replacement> some more text.
```
The idea is that the text to be replaced is somehow location-dependent
(such as the URL of a server of the local university)
and other universities using the same ProPra should be able to replace it
with their own local version in a simple manner.
Simple means they can fork the ProPra repository but need hardly ever make
any change to the actual task files, only to a single, central _replacements file_.

The replacements file is `replacements.md` in the top level of the ProPra repo.
It contains simply a list of replacement blocks:

```
<replacement id="someId">
our adapted local text (could also be on a single line instead of three)
</replacement>


<replacement id="otherId">
This is a longer replacement that can continue for multiple paragraphs.

Replacements can use _any_ **markup**, including macro calls,
only excluding other replacements.
[WARNING]
Beware of the dog!
[ENDWARNING]

## Next heading
And so on.  
</replacement>
```

Sedrila will replace the `text to be replaced` with its counterpart from the replacement file
exactly as written and will remove the `<replacement id="someId">` and `</replacement>` pseudo tags.
The `id` should start with the respective task, taskgroup, or chapter name.




### 2.10 Checking specification for command protocols: `@PROT_SPEC`

Author protocol files (`.prot`) can include `@PROT_SPEC` blocks that specify validation rules
for comparing student submissions with author solutions.
For actual comparison of student protocols during instructor checking, see `instructors.md` section 2.3.

This function supports different entries:

Single-line entries:

- `command_re=regex`: Command must contain a match for the regex (search mode). Use `^` and `$` anchors if you need full-line matching.
- `output_re=regex`: Output must contain a match for the regex (search mode)
- `skip=1`: Skip checking entirely (always passes, no manual review needed)

Multi-line entries (continuation lines indented by 4 spaces):

- `manual=text`: Manual review information
- `extra=text`: Additional information
- `comment=text`: Comment text

Example with command_re and output_re:
```
@PROT_SPEC
command_re=^ls -la$
output_re=\btotal\b
user@host /path 10:00:00 1
$ ls -la
total 16
-rw-r--r-- 1 user user 0 Jan 1 12:00 file.txt
```

Example with command_re and output_re + extra + comment:
```
@PROT_SPEC
command_re=^ls -la$
output_re=\btotal\b
extra=I am Extra
  Still Extra
comment=I am comment
user@host /path 10:00:00 1
$ ls -la
total 16
-rw-r--r-- 1 user user 0 Jan 1 12:00 file.txt
```

Example only with manual instruction:
```
@PROT_SPEC
manual=Make sure there are **at least 10 files**.
    If there are fewer, command 4 will not work as intended.
user@host /tmp 10:00:00 1
$ ls -a
.bashrc  .profile  file1.txt
```

Example with command_re + output_re + manual + extra + comment instruction:
```
@PROT_SPEC
command_re=^ls -a$
output_re=\b\.bashrc\b
manual=Additional check details.
    This can be used with any mode.
extra=I am Extra
comment=I am comment
user@host /tmp 10:00:00 1
$ ls -a
.bashrc  .profile  file1.txt
```

Example with skip:
```
@PROT_SPEC
skip=1
user@host /tmp 10:00:00 1
$ ls -a
.bashrc  .profile  file1.txt
```

Visual display in the sedrila author course build:

Each command entry is color-coded in the rendered protocol:

- Green (`prot-ok-color`): Automated checks passed
- Red (`prot-alert-color`): Automated checks failed
- Yellow (`prot-manual-color`): Only manual review requested (no automated checks)
- Grey (`prot-skip-color`): Entry marked with `skip=1`, or entry has no spec

Notes:

- Validates regex syntax for `command_re` and `output_re`
- Rejects mixing `skip=1` with others (`command_re`, `output_re`, or `manual`)
- Warns if `manual=` lacks inline text
- Reports errors when specs lack all of `command_re`, `output_re`, `manual`, and `skip` (requires at least one)
- Validates all tasks but respects `--include_stage` for error reporting:

    - Tasks matching the stage filter: **errors**
    - Tasks excluded by the stage filter: **warnings**
- Runs incrementally: triggers only when `.prot` files change
- A command without `@PROT_SPEC` block at all is equivalent to a command that has a `skip=1` entry. 
- A `@PROT_SPEC` block must contain at least one directive (`command_re`, `output_re`, `skip`, or `manual`)
- Automated checks only occur if `command_re` or `output_re` are specified:

  - Both `command_re` and `output_re` use search mode (match anywhere in the string)
  - Use regex anchors (`^` for start, `$` for end) when you need exact matching
- `manual=` can be used independently or together with regex checks to request instructor review
- When `command_re=` and/or `output_re=` are present, the color is determined solely by the automated check result (green for pass, red for fail). `manual=` in this case is supplementary information for the instructor, not affecting the color.
- Use `skip=1` for commands with no meaningful output (e.g., `cd`)
- Use `manual=` for commands requiring instructor judgment (e.g., variable output, timestamps)
- `@PROT_SPEC` blocks are filtered out when rendering protocols for students
- Only `.prot` files referenced by `[PROT::]` macros in markdown are registered for encryption.
- During the build, referenced `.prot` files are automatically encrypted (using instructor public keys from `sedrila.yaml`)
  and saved as `.prot.crypt` in the student output directory. This prevents students from viewing comparison results;
  only instructors with the corresponding private key can decrypt and see whether a student's protocol matches the reference.
- **GPG password management**: sedrila delegates all password handling to GPG and `gpg-agent`. When the webapp starts,
  it attempts to decrypt a test protocol file, which triggers GPG to request the passphrase (via `pinentry`) if needed.
  The password is then cached by `gpg-agent` for the session (typically 1 hour), so subsequent operations don't require re-entering it.
  WSL users should install `pinentry-tty` (`sudo apt-get install pinentry-tty`; WSL's default pinentry-curses cannot communicate with TTY)
  and configure `~/.gnupg/gpg-agent.conf` with `pinentry-program /usr/bin/pinentry-tty` for proper password prompting.
- Instructors can point to the output folder of a local `sedrila author` build using a `file://` URL in their student.yaml
  configuration (e.g., `course_url: file:///home/author/my-course/out/`). The webapp will then load and decrypt the `.prot.crypt`
  files directly from the local build output, enabling protocol comparison without requiring a web server.
- When instructors use `sedrila instructor` to check student submissions with a course accessible via `https://` URL,
  the webapp automatically downloads the encrypted `.prot.crypt` files from the course website, decrypts them locally,
  and displays the comparison. This allows instructors to access protocol specifications without needing a local course copy.
  The download happens transparently when an instructor views a student's protocol file and possesses the GPG private key
  needed for decryption.


### 2.11 Checking specification for program tests: `@TEST_SPEC`

See in [Maintainers documentation](maintainers.md).


### 2.12 Checking specification for external links: `@LINK_SPEC`

See in [Maintainers documentation](maintainers.md).


## 3. Calling `sedrila`

### 3.1 Default behavior

The standard call for generating the HTML website from a sedrila course is
`sedrila author outputdir`.
This will create the student version of the website at location `outputdir`
and the instructor version at `outputdir/instructor`.
Both versions will by default exclude all tasks, taskgroups, and chapters that have a
`stage:` entry in their metadata.

### 3.2 Options

- To include parts with `stage:` entry, add option `--include_stage minstage` where `minstage`
  is the lowest stage that should be included; all higher ones will be included as well.  
- To obtain less detailed console output during the generation, use `--log WARNING`.  
- The first run creates and fills the cache (which is stored in the instructor directory) 
  and subsequent runs will usually run _much_ faster.
  If you want another full build for some reason, use `--clean`.
- To use an alternative configuration file, use something like `--config myconfig.yaml`.  
- Option `--sums` generates reports about the volume of tasks per chapter,
  per difficulty, and per stage.
- Option `--rename old_partname new_partname` shortcuts normal operation and only performs a
  rename refactoring of the course content.
  It requires passing a dummy `targetdir` commandline argument which is not actually used.
  It will rename files or directories as appropriate (and occasionally beyond).
  It will replace references in markdown files: 
  `assumes:` and `requires:` headers as well as `PARTREF`, `INCLUDE`, `PROT`, and `TREEREF`
  macro calls.
  It will heuristically replace occurrences of `old_partname` in `new_partname.prot` files.
  Practical tips:

    - False positives are possible; make sure you inspect the protocol output on the terminal.
    - False negatives are likely, because other file types (such as program source files) are not modified.
      Perform a full-text search in your IDE after the rename operation to find them.
    - Start from a clean git state, so you can reset easily if things work out badly.
    - Do not interrupt a rename operation. A wrong, but complete rename is often easy to revert;
      a half-done one is probably not.
    - Make sure you adjust your config file if chapter/taskgroup directories were renamed.
    - After a rename, perform a build to check validity.

### 3.3 Automatic validation during builds

The `sedrila author` command validates course content incrementally during each build.
Validation runs only when relevant files change and respects the `--include_stage` setting.
There are three types of validation:

- Validation of implicit constraints, e.g., that `[INCLUDE::myfile]` requires `myfile` to exist,
  and that `[SNIPPET::filespec::snippetname]` requires the snippet to exist in the specified file.
- Validation of constraints formulated by `sedrila.yaml` config settings, e.g.,
  that a `stage: x` entry in a task file needs a corresponding stage declaration in `stages`.
- Validation of explicit constraints formulated in checking specifications, e.g., `@PROT_SPEC` entries.

Invalid content is reported as detailed error messages.

### 3.4 Copying the build output

If you are using an Apache webserver and have provided a suitable `htaccess_template`
in your config, you could copy the entire output directory as-is to a place where the
webserver will find it, because the `instructor` subdirectory is protected from student
access by the automatically generated `.htaccess` file it contains (unless your Apache base config
has turned this function off, which would be unusual).

In a more refined approach, you should exclude the cache file or files from copying:
`instructor/.sedrila-cache.*`.
These one or two files are used by `sedrila author` only, they are not part of the generated website.

If have no Apache webserver, you would exclude the `instructor` subdirectory when copying
the student website (i.e., copy `*.*`: `instructor` is the only entry that has no dot in its name)
to a public place and then copy the visible contents of `instructor` to an access-protected place
(the cache files are the only ones whose names start with a dot).

### 3.5 Working with a development setup of sedrila

If you use a development setup with a source installation of sedrila,
use a shell alias such as 
`alias sedrila='python /my/work/dir/sedrila/py/sedrila.py'`.

## 4. Customization of a sedrila course

### 4.1 Forking an existing course

One design goal of sedrila is that course authors should be able to fork an existing ("upstream")
sedrila course authored by people from a different university and adapt the fork to their needs,
but still be able to receive (and integrate automatically, simply by a git merge) almost all 
later changes those other authors may be making.

The support for this has the following components:

- Modifying the overall layout of the overall course website by modifying HTML templates
- Modifying appearance by modifying CSS styles
- Patching parts of task files that talk about university-specific things by
  replacing those parts without modifying the respective file.

These mechanisms are described in the next three subsections. 

### 4.2 Templates for HTML layout

The format of the resulting HTML files is determined per page type by the Jinja2 templates
in directory `templates`.
For examples, see https://github.com/fubinf/propra-inf/tree/main/templates

### 4.3 Modifying the CSS

By convention, the Jinja2 templates of a course should always include exactly two
CSS files: `sedrila.css` and `local.css`.
In the source tree, they both live in the `baseresourcedir` directory defined in
`sedrila.yaml`.

By convention, the original course puts all its styles into `sedrila.css` and
the fork can overwrite some of them in its `local.css`.
In the original course, `local.css` is empty and never changes.

### 4.4 The `<replacement>` mechanism

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

### 4.5 `altdir` and private repos

The `altdir` and `[INCLUDE::ALT:file]` mechanisms are meant for keeping parts of the
instructor information in a non-public repository.
If initially you do not have access to that repository that is not a big problem,
because `[INCLUDE::ALT:file]` on a non-existing `file` will only result in a warning,
not an error, and will simply include nothing.
Set `--log-level ERROR` if you do not want to see the warnings.

If you do have access to the private repo: That repo is used as a submodule in the
top-level course repo. Be sure to initialize that submodule initially and
update it regularly. 
Use git's `--recurse-submodules` option or `submodule.recurse=true` config setting as appropriate.
Working with submodules is generally not fun, so use it only to the degree necessary
and be prepared for the dreaded error message 
_"fatal: cannot rebase with locally recorded submodule modifications"_
by reading https://stackoverflow.com/questions/54215983.

The second repo for `altdir` will often also include the `itree.zip` tree.
Alternatively, especially if its contents are bulky, the latter could reside in a third repo.

### 4.6 Translating into English

If you want an English version of a German-language SeDriLa course,
the following approach works fairly well: Use ChatGPT 3.5, use the prompt given below.
After the prompt, paste one complete Markdown file at a time.

The prompt:

_Please translate the following text from German to English. 
It starts with YAML front matter, which should be kept as is. 
It uses Markdown markup, which should be kept as is. 
It also uses additional markup of the form [SECTION::some::stuff] or [ENDSECTION] or [HINT::some stuff] etc. 
This should also be kept as is. Here is the text:_

In a first try in 2024-06, this attempted to translate the task names mentioned
(which are technical identifiers), even in the case `[PARTREF::Pythonpraxis]`,
which should rather be done by hand. 
But other than that, the translation looked technically usable.
In terms of language, it was reasonable, often even good, but not very good.
