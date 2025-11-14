# `sedrila` test framework for SeDriLa courses

**This is work-in-progress. Inofficial. Changing heavily. Partly broken. Do not rely on anything here yet.**

A SeDriLa course may deteriorate over time. Or be broken by a change to a task.
A new task can be broken right from the start.

`sedrila author` already provides support for detecting defects in the _formal structure_
of the course: Illegal metadata, broken task/file/glossary references, etc.
But what about the actual task _content_?

`sedrila` should support detecting defects there as well: 
It would be nice to have a framework for automated testing
of a SeDriLa course that can detect at least _some_ types of problem.

The purpose of the present document is currently to support the design process for developing
such automated testing.
(Later on, it may be converted into some kind of user documentation or be removed.)


## 1. Link checking

One aspect of SeDriLa content checking is making sure that any hyperlinks to external resources
work as expected.

- Link checking needs to follow redirects.
- Not all links that work alright also result in HTTP 200 status.
  `sedrila` should probably allow specifying a different (specifically expected for this particular link)
  status code.
- Not all links that work from a technical point of view will also still contain the
  content the task designer expected it to contain.
  `sedrila` should probably allow specifying a key text snipped that must be present in the response?
  Or even require it?

### Implementation for now

To avoid errors caused by redundant content, please read `maintainers.md` section 1 - 4.

## 2. Program testing

Due to `sedrila`'s reliance on `git`, most SeDriLa courses will likely be programming-related
in one way or another. If so, most tasks will involve something that can be executed
and in most cases the task will then specify (precisely or loosely) an expected behavior of that thing.


### 2.1 Command protocols

The first SeDriLa course, `propra-inf`, makes heavy use of command logs ("Kommandoprotokoll"):

- Students submit a `mytaskname.prot` text file that results from running several commands in a command line shell.
- Task authors provide an example `mytaskname.prot` that instructors use for comparison.

`sedrila instructor` should support instructors in this comparison work:

- Require exact commands
- Allow for modest variation in commands (regexp?)
- Allow for large differences in commands? (multiple command variants?)
- Skip checking for unpredictable commands, but alert instructors if/what they need to check manually.
- Allow for modest variation in outputs (regexp?)
- Allow for large differences in outputs??
- Skip checking for unpredictable outputs, but alert instructors if/what they need to check manually.

`sedrila` needs to provide syntactical mechanisms for specifying the checks 
(with validation performed by `sedrila author`)
and execution logic for performing them and reporting when running `sedrila instructor`.

#### Implementation for now

To avoid errors caused by redundant content, please read `authors.md` section 2.1.2 and `instructors.md` section 2.3.

### 2.2 Programs

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

#### Implementation for now

To avoid errors caused by redundant content, please read `maintainers.md` section 1-3 and 5.

### 2.3 Program snippets

Tasks will often show snippets from programs for various purposes:

- For students to include them into their programs, so they need not write it all themselves.
- For students to view them for learning something.
  Such a snippet may not appear in the solution at all.
- For students to learn how _not_ to do something (anti-patterns).
- For students to use them as a starting point for what they have to write (incomplete snippet).
- And probably some other kinds.

Testing snippets is probably too variable and too hard to be included in `sedrila`
but it would be nice to at least ensure a snippet that is to be included in the student's
solution is identical to the respective part of the exemplary solution.

One approach could be to avoid all redudancy right from the start:
mark the snippet in the exemplary solution and extract it directly from there
when rendering the task in `sedrila author`.
Then testing the snippet would be reduced to testing the program in which it appears.

#### Implementation for now

To avoid errors caused by redundant content, please read `authors.md` section 2.3.1.

### 2.4 Other

The above ideas are not readily applicable to all kinds of tasks, for instance

- when a program's (or command's) effect is not expressed as text output;
- when students are given artistic freedom in what to build;
- and probably a number of other cases.

If we stumble over ideas how to cover some of these that are easy to implement,
we may do it.
But more likely we should apply YAGNI here ("you ain't gonna need it")
and not solve problems of which we have not seen any instance.


## 3. Birds-eye view: Recurring issues

So our goal is to find good solutions for the following problems
(in various contexts and forms):

- How to specify the expectation?
- How to realize the technical preconditions for running whatever there is to be run?
- How to cope with unexpected behaviors?
- How to report behaviors and test outcomes in an easy-to-digest manner?
- How and where to wire all this into `sedrila`?