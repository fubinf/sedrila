import glob
import typing as tg

import base as b
import sdrl.course

def read_and_check(course: sdrl.course.Course):
    """Reads all task files into memory and performs consistency checking."""
    for chapter in course.chapters:
        for taskgroup in chapter.taskgroups:
            filenames = glob.glob(f"{course.chapterdir}/{chapter.slug}/{taskgroup.slug}/*.md")
            for filename in filenames:
                if not filename.endswith("index.md"):
                    taskgroup.add_task(sdrl.course.Task(filename))
    check(course)

    
def check(course: sdrl.course.Course):
    for task in course.all_tasks():
        for assumed in task.assumes:
            if not course.task(assumed):
                b.error(f"{task.slug}:\t assumed task '{assumed}' does not exist")
        for required in task.requires:
            if not course.task(required):
                b.error(f"{task.slug}:\t required task '{required}' does not exist")
