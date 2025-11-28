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

- Documented in `maintainers.md`, Section 2.
- Implemented in `linkchecker.py`
- Validated by `linkchecker_test.py`
- Discussed in https://github.com/fubinf/sedrila/issues/30


## 2. Validating command protocols

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

- Documented in `authors.md` Section 2.3.2,
  `instructors.md` Section 2.3, and
  `internal_notes.md` Section 4.
- Implemented in `linkchecker.py`
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

- Documented in `maintainers.md`, Section ???.
- Implemented in `???.py`
- Validated by `???_test.py`
- Discussed in https://github.com/fubinf/sedrila/issues/29


## 4. Avoiding redundancy for program snippets

Tasks will often show snippets from programs for various purposes.
Insofar as the same snippet is contained in the exemplary solution that is made available to the instructors,
it would be nice to avoid duplicating the snippet because that is error-prone (at least when
later changes to the program occur).

So we provide a `[SNIPPET::...]` macro (akin to the `[INCLUDE::...]` macro) for
extracting from another file snippets to be shown on a task webpage. 

- Documented in `authors.md` Section 2.3.1
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