import argparse
import os
import os.path
import shutil
import typing as tg

import jinja2
import markdown

import base
import sdrl.config as conf
import sdrl.task

def generate(pargs: argparse.Namespace, config: conf.Config):
    """
    Render the tasks, intros and navigation stuff to output directory.
    Renders all HTML into a single flat directory because this greatly simplifies
    the link generation.
    Uses the basenames of the chapter and taskgroup directories as keys.
    """
    clean_targetdir(pargs.targetdir, markerfile=f"_{base.CONFIG_FILENAME}")
    shutil.copyfile(base.CONFIG_FILENAME, f"{pargs.targetdir}/_{base.CONFIG_FILENAME}")  # mark dir as a SeDriLa instance
    for taskname, task in config.taskdict.items():
        render_task(task, config, pargs.targetdir)
    print(toc(config))

def clean_targetdir(targetdir: str, markerfile: str):
    """Keeps one backup copy, then cleans (or creates) targetdir, making sure it holds a configfile."""
    if not os.path.exists(targetdir):
        os.mkdir(targetdir)
        return
    #----- keep a backup copy:
    targetdir_bak = f"{targetdir}.bak"
    if os.path.exists(targetdir_bak):
        if not os.path.exists(f"{targetdir_bak}/{markerfile}"):
            raise ValueError(f"will not remove '{targetdir_bak}': it is not a SeDriLa instance")
        shutil.rmtree(targetdir_bak)
    os.rename(targetdir, targetdir_bak)
    os.mkdir(targetdir)
    

def render_task(task: sdrl.task.Task, config: conf.Config, targetdir: str):
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(config.templatedir), autoescape=False)
    template = env.get_template("task.html")
    output = template.render(title=task.title,
                             content=markdown.markdown(task.content))
    base.spit(f"{targetdir}/{task.filename}", output)
    

def render_chapter():
    ...


def render_welcome():
    ...


def toc(structure: tg.Union[conf.Config, conf.Chapter, conf.Taskgroup, sdrl.task.Task]) -> str:
    """Return a table-of-contents HTML fragment for the given structure via structural recursion."""
    result = []
    if isinstance(structure, conf.Config):
        for chapter in structure.chapters:
            result.append(toc(chapter))
    elif isinstance(structure, conf.Chapter):
        result.append(structure.toc_link())  # Chapter toc_link
        for taskgroup in structure.taskgroups:
            result.append(toc(taskgroup))
    elif isinstance(structure, conf.Taskgroup):
        result.append(structure.toc_link())  # Taskgroup toc_link
        for task in structure.tasks:
            result.append(toc(task))
    elif isinstance(structure, sdrl.task.Task):
        result.append(structure.toc_link())  # Task toc_link
    else:
        assert False
    return "\n".join(result)