import glob
import typing as tg

import base
import sdrl.task

def read_and_check(config: base.StrAnyMap) -> sdrl.task.Tasks:
    """Reads all task files into memory and performs consistency checking."""
    tasks = dict()
    for chapter in config['chapters']:
        dirname = chapter['directory']
        filenames = glob.glob(f"{dirname}/*.md")
        for filename in filenames:
            task = sdrl.task.Task(filename)
            task.assign(dirname, "default")
            tasks[task.taskname] = task
    check(tasks)
    return tasks

    
def check(tasks: sdrl.task.Tasks):
    pass  # TODO 2
