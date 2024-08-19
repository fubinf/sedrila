# sedrila: Tool infrastructure for building and running 'self-driven lab' courses

A "self-driven lab" (SeDriLa) course is one where students select freely 
a subset from a large set of tasks.
The tasks are described with sufficient detail that no guidance from an instructor
is needed most of the time.

sedrila is a command-line tool. Read about its [general ideas](general_ideas.md).

The sedrila tool supports three user groups:

- [Course authors](authors.md): 
  generate a static website from a markdown-based content structure.
  There is lots of support for specialized markup, cross-referencing, and consistency checking. 
- [Course instructors](instructors.md): 
  receive student submissions; accept or reject student solutions.
- [Students](students.md):
  submit finished tasks; compute status tables of submissions and time value earned.

[Viewers](viewer.md) are instructors or students who browse a directory tree of solution files.  

[changelog](changelog.md)