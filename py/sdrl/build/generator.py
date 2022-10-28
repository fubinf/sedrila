import argparse
import os
import os.path
import shutil

import jinja2
import markdown

import base
import sdrl.task

def generate(pargs: argparse.Namespace, config: base.StrAnyMap, tasks: sdrl.task.Tasks):
    """
    Render the tasks, intros and navigation stuff to output directory.
    Renders all HTML into a single flat directory because this greatly simplifies
    the link generation.
    Uses the basenames of the chapter and taskgroup directories as keys.
    """
    clean_targetdir(pargs.targetdir, markerfile=f"_{base.CONFIG_FILENAME}")
    shutil.copyfile(base.CONFIG_FILENAME, f"{pargs.targetdir}/_{base.CONFIG_FILENAME}")  # mark dir as a SeDriLa instance
    for taskname, task in tasks.items():
        render_task(pargs.targetdir, task)
    

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
    

def render_task(targetdir: str, task: sdrl.task.Task):
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(base.TEMPLATES_DIR), autoescape=False)
    template = env.get_template("task.html")
    output = template.render(title=task.title,
                             content=markdown.markdown(task.content))
    base.spit(f"{targetdir}/{task.taskname}.html", output)
    

def render_chapter():
    ...

def render_welcome():
    ...