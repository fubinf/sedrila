# sedrila: Tool infrastructure for building and running 'self-driven lab' courses

A "self-driven lab" (SeDriLa) course is one where students select freely 
a subset from a large set of tasks.
The tasks are described with sufficient detail that no guidance from an instructor
is needed most of the time.

sedrila is a command-line tool. Read about its [general ideas](general_ideas.md).

The sedrila tool supports three main user groups:

- [Course authors](authors.md): 
  generate a static website from a markdown-based content structure.
  There is lots of support for specialized markup, cross-referencing, and consistency checking. 
- [Course instructors](instructors.md): 
  receive student submissions; accept or reject student solutions.
- [Students](students.md):
  submit finished tasks; compute status tables of submissions and time value earned.

Besides these, there are several less prominent user groups:

- [Course maintainers](maintainers.md):
  fight against the technical erosion of course contents over time.
  Link checking and automated testing of the programs and scripts contained in a SeDriLa
  are provided by this command to help them do it.
- [Course evaluators](evaluators.md):
  review a management dashboard (provided by this command) of a current or past SeDriLa course instance
  in order to understand its dynamics.

[changelog](changelog.md)