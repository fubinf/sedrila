import glob
import typing as tg

import base
import sdrl.config
import sdrl.task

def read_and_check(config: sdrl.config.Config):
    """Reads all task files into memory and performs consistency checking."""
    for chapter in config.chapters:
        for taskgroup in chapter.taskgroups:
            filenames = glob.glob(f"{config.chapterdir}/{chapter.slug}/{taskgroup.slug}/*.md")
            for filename in filenames:
                if not filename.endswith("index.md"):
                    taskgroup.add_task(sdrl.task.Task(filename))
    check(config)

    
def check(config: sdrl.config.Config):
    pass  # TODO 2
