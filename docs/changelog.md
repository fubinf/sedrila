# sedrila CHANGELOG


## Version 2.12.0 (upcoming)
- `student`, `instructor`: Webapp now suppresses the meaningless `TimeoutError` stacktraces
- `student`, `instructor`: Display a student work summary report before entering command loop 
- ...


## Version 2.11.1 (2025-11-19)
- `student`, `instructor`: Webapp now renders source code files properly again.

## Version 2.11.0 (2025-11-19)
- `author`, `student`: add field `instructor.status` in `sedrila.yaml`. Show it when students submit.
- `student`, `instructor`: the webapp no longer uses sedrila-style markdown rendering, so no longer
  gets irritated when something accidentally looks like a sedrila macro call
- make file reading robust against files not using the prescribed UTF-8 encoding


## Version 2.10.2 (2025-10-23)
- `student`, `instructor`: new webapp, #14: better ordering of tasks
- `student`, `instructor`: new webapp, #19: fixed issue with CSS mimetype
- `student`, `instructor`: new webapp, #25: fixed issue with Umlauts in filenames
- `student`, `instructor`: new webapp, #26: reduced duration of the occasional unwanted service pauses
- `student`, `instructor`: new webapp: fixed crash when webapp was started a second time
- `student`, `instructor`: new webapp, #14: tasks with no worktime entry are now shown correctly


## Version 2.10.1 (2025-10-14)
- fixed crucial typo in `pyproject.toml`


## Version 2.10.0 (2025-10-13)
- `author`: support `ITREE` prefix in [INCLUDE::ITREE:somefile]`
- `author`: introduced `participants` config setting (not actually used yet!) 
- `author`: support environment variable expansion in some config file settings
- `author`, `instructor`: introduced `former_instructors` config setting 
  (like `instructors`, but not suggested to students upon submission preparation)
- `student`, `instructor`: totally revamped and much better webapp 


## Version 2.9.0 (2025-08-19)
- `author`: taskgroup-level non-md files are now copied to targetdir verbatim (for images, downloads, etc.)
- `instructor`, `student`: Defend against dangerous paths and control chars in student metadata 


## Version 2.8.1 (2025-08-15)
- `instructor`: pull repo whenever workdir is clean
- docs: Instructor documentation now explains when and how to import the other instructors' public keys.


## Version 2.8.0 (2025-08-07)
- `server`: small new command: A trivial personal webserver to be used by course authors
  for viewing the current rendered version of the course.


## Version 2.7.0 (2025-07-07)
- `author`: In the glossary, `[TOC]` ignores headings and instead makes an alphabetical list of 
  all term entries (main terms and synonyms).


## Version 2.6.4 (2025-04-29)
- FIX: `pyproject.toml` must declare `numpy<2`, although `pandas` (who needs this) correctly declares it.
  Reason unclear.


## Version 2.6.3 (2025-04-29)
- `instructor`/`student`: FIX: accept signatures with unknown validity


## Version 2.6.2 (2025-04-14)
- `author`: add `--rename old_partname new_partname` refactoring function.
- `student`: FIX: sedrila student failed to read the commit history when submission.yaml was empty


## Version 2.6.1 (2025-04-08)
- `student`: refuse to run if the work directory given does not contain a `.git` subdir.
- `student`: if `student.yaml` is missing, mention `--init`.


## Version 2.6.0 (2025-02-10)
- `instructor1` removed.
- `viewer` removed. This functionality is now covered by the 'webapp' function of
  `student` and `instructor`.
- `student`: completely rewritten. Except for `--init` and `--import-keys`, the usual form of use is now
  menu-driven, with operations 'prepare', 'webapp', 'edit', 'commit', and 'push'.
  The webapp also shows a) a list of tasks (based on contents of 'submission.yaml' and commit messages)
  and allows selecting/unselecting them for submission, and b) the report on work done so far.  
  The previous terminal-based task selection and work report were removed.
- `instructor`: rewritten, to make it analogous to `student`.  
  Here, the webapp allows clicking on usernames near files or tasks in order to accept/reject/keepneutral
  the corresponding task. Each such change is reflected in `submission.yaml` immediately.  
  The work report is available here as well.


## Version 2.5.0 beta (2025-01-28)
- `viewer`: completely new viewer that can browse several directory trees at once and will
  mark most files that pertain to some task given in `submission.yaml`.
- `student`: Five fields are now mandatory in `student.yaml` (in order to support `viewer` and `instructor`):
  `course_url`, `student_fullname`, `student_id`, `student_gituser`, `partner_gituser`; 
  the latter (and only the latter) may be empty. 
- `instructor1`: is what `instructor` was formerly, while `instructor` is being re-designed.
- `instructor`: is now a menu-driven interactive command and can also work on several student workdirs at once.
  So far, it can only perform pull, viewer, and commit&push, but has no actual task-marking functionality.
  INCOMPLETE.
- `student` and `instructor1` are prone to have defects, but `viewer` is useful.
- Documentation "General ideas" now describes the four different directory hierarchies involved.
- Documentation "Architecture" now specifies module layers.
- Ctrl-C now always terminates without a stack trace.


## Version 2.4.0 (2025-01-13)
- `author`: Remove the ToC at bottom of homepages of course, chapter, or taskgroup
- `viewer`: Ctrl-C now only prints a nice exit message.
- `viewer`: Show all files named like submitted entries (in any directory) together
- `viewer`: Provide favicon


## Version 2.3.0 (2024-10-10)
- `author`: FIX: generate .htaccess again (was missing since 2.0.0)
- `viewer`: make shellprompt recognition more liberal
- `viewer`: allow .prot files to lie in subdirectories rather than at top level


## Version 2.2.1 (2024-08-27)
- `instructor`: forgotten FIX: ignore Taskgroups in `require` when checking


## Version 2.2.0 (2024-08-26)
- `viewer`: add link to show `*.html` as a page instead of its source
- `student`: FIX: ignore Taskgroups in `require` when checking


## Version 2.1.2 (2024-08-20)
- `student`: FIX: repair broken get_metadata() that led to a crash


## Version 2.1.1 (2024-08-20)
- `author`: add the forgotten documentation for the new `[PROT]` macro.
- `author`: HTML now uses more semantic markup: `<nav>`, `<main>`, `<section>`, `<aside>`,
  `role=`
- (all): FIX: repair search for `pyproject.toml`, which is broken in the wheel version of the PyPI package


## Version 2.1.0 (2024-08-19)
- `author`: make `[TERMREF2::class::--like]` work correctly.
- `author`: suppress info line on instructor file x when there was one on student file x
- `viewer`: (new role): special-purpose webserver for browsing a student repo


## Version 2.0.0 beta (2024-08-02) 
- `author` optimization: sedrila now uses an incremental build, supported by a cache.
  Build time reduces tenfold in typical cases.
  The previous simplistic cache and its `--cache` option were removed.
  The code base has been greatly reorganized accordingly and is now cleaner and clearer.
  Use `--clean` to start with an empty cache if desired (there is rarely a need for it).
  Output now reports which files are built; use `--log WARNING` to silence this.
- `author` harmonization: in `sedrila.yaml`, 'slug' and 'breadcrumb_title' are renamed into 'name'.
  (In the resulting `course.json`, 'slug' is deprecated, but still available for the time being,
  so that students/instructors can continue to use sedrila 1.3 when authors start using sedrila 2.0.
  Version mixing is not well tested, though.)
- `author` simplification: `assumes` and `requires` now allow any type of part.
  The `minimum` attribute in taskgroup files is no longer supported.
  The (undocumented) `todo` attribute in taskgroup files is no longer supported.
- `author` feature: sedrila now also supports table syntax in Markdown.
- `author`: FIX: added missing documentation for macro `[TERMREF2]`.
- `author`: FIX: the reported number of errors is no longer inflated.
- `instructor`: can now change previous accept/reject decisions``


## Version 1.3.2 (2024-06-13) 
- increase inter-version compatibility between authors and recipients (students/instructors)
- `author`: documentation describes how to get an English translation using ChatGPT.


## Version 1.3.1 (2024-06-07) 
- `author`: FIX: generated `course.json` now includes the required attribute `altdir`


## Version 1.3.0 (2024-06-03) 
- `author`: introduce `itreedir` and `[TREEREF]` for stand-alone instructor support files


## Version 1.2.1 (2024-05-31) 
- `author`: allow task names containing a dot


## Version 1.2.0 (2024-05-17)
- `author`: table of contents for glossary now is chapters-only
- `author`: warn about unterminated INSTRUCTOR blocks (that would show up in student version)
- `author`: warn about macro calls with empty arg1
- `student --submission`: FIX: solve terminal-size-dependent crash
- `student`: FIX: work around surprising limitation in `rich` library to produce the work table again


## Version 1.1.0 (2024-04-23) 

- `student`/`instructor`: remove lots of spurious error messages
- `student`/`instructor`: improved several prompts and messages


## Version 1.0.0 beta (2024-04-21)

- removed support for 'profiles' metadatum in tasks; it is superfluous
- `author`: ZIP files no longer contain inner path parts chapter/taskgroup/task/ 
- `author`: Introduced `altdir`, `[INCLUDE::ALT:...]`, and  `[INCLUDE::/...]`


## Version 0.7.0 alpha (2024-04-02)

- `author`: add [FOLDOUT] macro
- `instructor`: improvements of interactive mode
- `instructor`: instructor subdirectory now simply named "instructor"
- change from `_sedrila.yaml` to `sedrila.yaml` in the generated website
- introduce naming conventions for chapters, taskgroups, tasks


## Version 0.6.0 alpha (2024-03-26)

- `author --cache` added which greatly (if very inflexibly) speeds up the processing of small changes
- `author` now leaves empty taskgroups and chapters out from TOCs
- `author` added linkslists of subsequent (assumed by, required by) tasks at bottom of task pages
- `author` generates .htaccess file in instructor website
- `student --init`: generate `student.yaml` from interactive prompts 
- `student --submission`: interactive task selection dialog 
- `instructor`: interactive task accept/reject dialog


## Version 0.5.0 alpha (2024-02-24)

- near-complete functionality for `author`
- very basic functionality for `student` and `instructor`
