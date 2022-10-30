import argparse
import glob
import os
import os.path
import shutil
import typing as tg

import jinja2
import markdown

import base
import sdrl.config as conf
import sdrl.task

Structurepart = tg.Union[conf.Config, conf.Chapter, conf.Taskgroup, sdrl.task.Task]

def generate(pargs: argparse.Namespace, config: conf.Config):
    """
    Render the tasks, intros and navigation stuff to output directory.
    Renders all HTML into a single flat directory because this greatly simplifies
    the link generation.
    Uses the basenames of the chapter and taskgroup directories as keys.
    """
    clean_targetdir(pargs.targetdir, markerfile=f"_{base.CONFIG_FILENAME}")
    shutil.copyfile(base.CONFIG_FILENAME, f"{pargs.targetdir}/_{base.CONFIG_FILENAME}")  # mark dir as a SeDriLa instance
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(config.templatedir), autoescape=False)
    #----- copy baseresources:
    for filename in glob.glob(f"{config.baseresourcedir}/*"):
        shutil.copy(filename, pargs.targetdir)
    #----- add tocs to upper structure parts:
    config.toc = toc(config)
    for chapter in config.chapters:
        chapter.toc = toc(chapter)
        for taskgroup in chapter.taskgroups:
            taskgroup.toc = toc(taskgroup)
    #----- generate top-level file:
    render_welcome(config, env, pargs.targetdir)
    #----- generate chapter and taskgroup files:
    for chapter in config.chapters:
        render_chapter(chapter, env, pargs.targetdir)
        for taskgroup in chapter.taskgroups:
            render_taskgroup(taskgroup, env, pargs.targetdir)
    #----- generate task files:
    for taskname, task in config.taskdict.items():
        render_task(task, env, pargs.targetdir)


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
    

def render_welcome(config: conf.Config, env, targetdir: str):
    template = env.get_template("welcome.html")
    output = template.render(title=config.title,
                             toc=config.toc, fulltoc=config.toc, 
                             content=markdown.markdown(config.content))
    base.spit(f"{targetdir}/{config.outputfile}", output)


def render_chapter(chapter: sdrl.config.Chapter, env, targetdir: str):
    template = env.get_template("chapter.html")
    output = template.render(title=chapter.title,
                             toc=chapter.toc, fulltoc=chapter.config.toc, 
                             content=markdown.markdown(chapter.content))
    base.spit(f"{targetdir}/{chapter.outputfile}", output)


def render_taskgroup(taskgroup: sdrl.config.Taskgroup, env, targetdir: str):
    template = env.get_template("taskgroup.html")
    output = template.render(title=taskgroup.title,
                             toc=taskgroup.toc, fulltoc=taskgroup.chapter.config.toc, 
                             content=markdown.markdown(taskgroup.content))
    base.spit(f"{targetdir}/{taskgroup.outputfile}", output)


def render_task(task: sdrl.task.Task, env, targetdir: str):
    template = env.get_template("task.html")
    output = template.render(title=task.title,
                             toc=task.taskgroup.toc, fulltoc=task.taskgroup.chapter.config.toc, 
                             content=markdown.markdown(task.content))
    base.spit(f"{targetdir}/{task.outputfile}", output)


def toc(structure: Structurepart, level=0) -> str:
    """Return a table-of-contents HTML fragment for the given structure via structural recursion."""
    result = []
    if isinstance(structure, conf.Config):
        for chapter in structure.chapters:
            result.append(toc(chapter, level))
    elif isinstance(structure, conf.Chapter):
        result.append(structure.toc_link(level))  # Chapter toc_link
        for taskgroup in structure.taskgroups:
            result.append(toc(taskgroup, level+1))
    elif isinstance(structure, conf.Taskgroup):
        result.append(structure.toc_link(level))  # Taskgroup toc_link
        for task in structure.tasks:
            result.append(toc(task, level+1))
    elif isinstance(structure, sdrl.task.Task):
        result.append(structure.toc_link(level))  # Task toc_link
    else:
        assert False
    return "\n".join(result)