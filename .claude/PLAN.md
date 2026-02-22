2026-02-22: course.py is overly long.
I am considering splitting it into three files:
- move CourseSI to course_si.py
- move Taskbuilder, Taskgroupbuilder, Coursebuilder, MetadataDerivation to coursebuilder.py
- leave the rest where it is
- all files that need Coursebuilder import both course.py and coursebuilder.py
- all files that need CourseSI import both course.py and course_si.py
- no file should need to import all three of them, correct?

Check if this is going to create problems.
If yes, explain these.
If not, make the above changes.
