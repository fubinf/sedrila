I want to extend report.py such that it can also generate reports for the student and instructor role.
There, the report should not cover all tasks, but rather only those the student has actually
worked on and ignore the rest (including suppressing entire chapters or difficulty levels
if zero tasks from them have been worked on).

Such a report should replace the current report's columns 2 and 3 (titled "#Tasks" and "Timevalue") 
by the following:
"worktime" (sum of task.worktime), 
"accept" (sum of task.timevalue if task.is_accepted else 0), 
"reject" (sum of task.timevalue if task.rejections > 0 and not task.is_accepted else 0)

Change the main entry point signature to 
print_volume_report(course: 'sdrl.course.Course', author_mode: bool)
where author_mode means the current report and not author_mode means the new version as
sketched above.
The new version contains only the chapter and difficulty level tables,
not the stage table nor the stage volume summary at the very top.

Ask if anything is unclear.
Execute the change otherwise.
