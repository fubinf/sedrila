# sedrila CHANGELOG


## Version 2.3.1 (upcoming)
- `viewer`: Ctrl-C now only prints a nice exit message.
- ...


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
