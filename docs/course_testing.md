# `sedrila` test framework for SeDriLa courses

**This is work-in-progress. Inofficial. Changing heavily. Partly broken. Do not rely on anything here yet.**

A SeDriLa course may deteriorate over time. Or be broken by a change to a task.
A new task can be broken right from the start.

`sedrila author` already provides support for detecting defects in the _formal structure_
of the course: Illegal metadata, broken task/file/glossary references, etc.

The purpose of the present document is to support the process for developing
further automated testing support of various sorts.


## 1. Link checking

Check whether hyperlinks to external resources (given in tasks) work as expected and report deviations.

- Documented in `maintainers.md`, Section 1-4.
- Implemented in `linkchecker.py`
- Validated by `linkchecker_test.py`
- Discussed in https://github.com/fubinf/sedrila/issues/30


## 2. Validating command protocols

### 2.1 Overview

We annotate the for-instructors command protocol with specifications
what each command should look like (if we have a fixed expectation for that),
what each command output should look like (if we have a fixed expectation for that),
what the instructor should check manually about this command,
whether the instructor can skip this command when checking (because if it's wrong,
a later command is going to show that).

Upon `author` build, we check that the for-instructors command protocol obeys these specifications
and weave them nicely into the rendered version of the command protocol.

Upon `instructor` webapp runs, we check that the students' command protocols obey these specifications
and weave the results nicely into the rendered versions of the command protocols.


### 2.2 Behavior specification: `@PROT_SPEC`

The specification can involve long regexps and even longer Markdown text, so it must be 
multiple lines long. It consists of entire lines.
The specification starts when encountering a line that contains only `@PROT_SPEC`.
It ends when the next line is a valid sedrila-style command prompt.

All lines of the specification are suppressed (not shown as such) when rendering the `.prot` file.

There are four possible single-line spec entries (`command_re=`, `output_re=`, `skip=`, `manual=`)
and two multiline spec entries (`text=`, `comment=`).
A spec entry must start at the beginning of a line.

`command_re=` is followed by a regular expression. 
The command below the specification must match this regular expression for the check to succeed.

`output_re=` is followed by a regular expression. 
The output following the command below the specification must match this regular expression for the check to succeed.

`skip=` must be followed by `1`: `skip=1`. This means the command below the specification will be considered
correct without any checking.
`skip` must not be used together with `command_re`, `output_re`, or `manual`.

`manual=` is followed by `1`: `manual=1`. This says nothing about the success of automated checking,
but indicates the instructor should apply manual checking.
A warning will be issued if a command with `manual=1` does not also have a `text=` entry.
`manual` can be used together with `command_re` or `output_re`.

`manual=` is followed by one or several lines of Markdown text that will be rendered
and shown in between the command prompt and the command itself.
This says nothing about the success of automated checking,
but indicates the instructor should apply manual checking.
The body will explain what to check manually.  
The lines below the `manual=` line must be indented by at least 4 spaces.
4 characters will be cut away from the left of each before rendering, 
so that the entire Markdown block can be indented visually without changing its meaning.

`extra=` works just like `manual=`, except that it does not suggest manual checking,
but rather provides other kinds of extra information.
If there is no `command_re`, `output_re`, `skip`, or `manual` entry,
a warning will be produced.

A command with no specification at all is equivalent to a command that has a `manual=` entry only. 

Example:
```
@PROT_SPEC
command_re=^ls -a$
output_re=\b\.bashrc\b
manual=Make sure there are **at least 10 files**.
    If there are fewer, command 4 is not going to work as intended.
```

### 2.3 Rendering a `.prot` on the instructor course website

The big step number in front of each command is shown depending on the status of that entry:
Green background (CSS class `prot-ok-color`) means an automated check has occured and was successful;
red (`prot-alert-color`) mean it failed;
yellow (`prot-manual-color`) means instructors must check manually;
grey (`prot-skip-color`) indicates skipped entries with neither automatic nor manual checks.

If the spec contained `manual=`, the Markdown markup is rendered as plain markdown (without the
sedrila extensions) and the result inserted in between the prompt and the command
as a `<div class='prot-spec-manual'></div>`.

Likewise for `extra=`: rendered below the `manual=` part
as a `<div class='prot-spec-extra'></div>`.

If automated checks found problems, these are shown just below these two blocks like this:  
`<div class='prot-spec-error'><pre>output_re=\b\.bashrc\b</pre> did not match</div>`.  
We use zero to two such blocks as needed.


### 2.4 Rendering a `.prot` in the instructor webapp (when checking a student submission)

This works almost identically to 2.3, except that the `.prot` to be rendered and the `.prot`
containing the behavior specification are now two separate files.

If a student has a command to many or too few at some point, all automated checks beyond that point
will very likely also fail.
We do not consider this a problem.

In a later iteration (please skip this initially), we may want to show the instructor the (or a) 
correct command or output in case of a failed automatic check.


### 2.5 Implementation considerations

The specification is contained in a `.prot` file that is available to authors at build time.
It is not directly available to instructors at submission checking time (it must not be required 
for instructors to have access to the source file tree; this would result
in an inconvenient and fragile construction, produce SeDriLa course versioning problems, etc.)

The `.prot` file could be included in the instructor website, but accessing that would require
that the webapp performs authentication when retrieving data from the SeDriLa course website.
There is no mechanism that would make this easy _while maintaining proper security of
the instructor's password_.

So the solution is to include the `.prot` file in the public student part of the SeDriLa course
as `mytaskname.prot.crypt`and encrypt it such that only instuctors can read it.
Such functionality is already provided in `mycrypt.py` and used in 
`Coursebuilder._transform_participantslist()` and `test_sedrila_author()`.
(Notes: (1) Yes, unfortunately that makes things a lot more complicated.
(2) The participantslist-checking functionality is currently unfinished)

The implementation will have to be called in the `expand_prot()` macroexpander.
Funneling the `.prot` data to that point for the webapp case needs to be done via the
`course` object.
Please make sure, though, that most of the implementation logic remains in 
`protocolchecker.py`.


### 2.6 Usability testing and iterating

It is unlikely that this specification describes _exactly_ what will be most useful.

To refine the functionality, please coordinate with Sven Wegner, who currently reviews
instructor information blocks in general for patterns of problems and possible improvements,
and with the current instructors (see `sedrila.yaml`) who have experience with real checking
of `.prot` files. 
Listen to them and refine the functionality such that it becomes handy and useful. 
Record enough about the process so that you can document and analyze it in your thesis.


### 2.7 Cross references

- Documented in `authors.md` Section 2.3.2,
  `instructors.md` Section 2.3, and
  `internal_notes.md` Section 4.
- Implemented in 
    - `Protocolchecker.py`
    - `course.py`: `class ProtocolValidation` (incremental build)
    - `elements.py`: comments of inheritance hierarchy
    - `marcoexpanders.py`: non-rendering markup function `filter_prot_check_annotations` imported
    - `directory.py`: incremental build registration
    - `instructor.py`: `def check_protocol_files`
- Validated by `protocolchecker_test.py`
- Discussed in https://github.com/fubinf/sedrila/issues/27


## 3. Validating programs

In many cases, the command log will show executions of some program that has fully or
partly been built by the student during that task.
Then the SeDriLa course will usually contain an exemplary version of that (or such a) program.

Ensuring consistency of the SeDriLa means

- Making sure the exemplary program can still be run.
  This is difficult because there may be required preparatory steps in this task
  or preceeding tasks (`requires`), such as installing a runtime system or some library
  (or potentially many other types).
- Making sure the program still produces the (or an) expected command log.
  This is also difficult, for similar reasons than above.

- Documented in `maintainers.md`, Section 1-3 and 5.
- Implemented in 
    - `Programchecker.py`
    - `maintainer.py`: `check_programs_command`
- Validated by `Programchecker_test.py`
- Discussed in https://github.com/fubinf/sedrila/issues/29


## 4. Avoiding redundancy for program snippets

Tasks will often show snippets from programs for various purposes.
Insofar as the same snippet is contained in the exemplary solution that is made available to the instructors,
it would be nice to avoid duplicating the snippet because that is error-prone (at least when
later changes to the program occur).

So we provide a `[SNIPPET::...]` macro (akin to the `[INCLUDE::...]` macro) for
extracting from another file snippets to be shown on a task webpage. 

- Documented in `authors.md` Section 2.3.1 and
  `internal_notes.md` Section 4.
- Implemented in 
    - `snippetchecker.py`
    - `course.py`: `class SnippetValidation` (incremental build)
    - `elements.py`: comments of inheritance hierarchy
    - `directory.py`: incremental build registration
    - `macroexpanders.py`: SNIPPET macro registration
- Validated by `snippetchecker_test.py`
- Discussed in https://github.com/fubinf/sedrila/issues/28


## 5. Other

The above ideas are not readily applicable to all kinds of tasks, for instance

- when a program's (or command's) effect is not expressed as text output;
- when students are given artistic freedom in what to build;
- and probably a number of other cases.

If we stumble over ideas how to cover some of these that are easy to implement,
we may do it.
But more likely we should apply YAGNI here ("you ain't gonna need it")
and not solve problems of which we have not seen any instance.


## 6. Birds-eye view: Recurring issues

So our goal is to find good solutions for the following problems
(in various contexts and forms):

- How to specify the expectation?
- How to realize the technical preconditions for running whatever there is to be run?
- How to cope with unexpected behaviors?
- How to report behaviors and test outcomes in an easy-to-digest manner?
- How and where to wire all this into `sedrila`?