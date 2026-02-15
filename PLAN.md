I want to move all parts having to do with author.print_volume_report() into a new module report.py:
from author.py: print_volume_report();
from course.py: the Volumereport nested class, the 3 volume_report_per_*() methods and their 
_volume_report() helper.
Is this going to create any difficulty? Am I missing something?
If not, then perform the change and adapt the source modules accordingly.
