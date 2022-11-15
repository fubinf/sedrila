import glob
import typing as tg

import sdrl.course
import sdrl.task

def read_and_check(course: sdrl.course.Course):
    """Reads all task files into memory and performs consistency checking."""
    for chapter in course.chapters:
        for taskgroup in chapter.taskgroups:
            filenames = glob.glob(f"{course.chapterdir}/{chapter.slug}/{taskgroup.slug}/*.md")
            for filename in filenames:
                if not filename.endswith("index.md"):
                    taskgroup.add_task(sdrl.task.Task(filename))
    check(course)

    
def check(course: sdrl.course.Course):
    pass  # TODO 2
