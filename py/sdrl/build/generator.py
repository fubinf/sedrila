import argparse
import glob
import os
import os.path
import shutil
import typing as tg

import jinja2

import base as b
import sdrl.course
import sdrl.html as h
import sdrl.markdown as md
import sdrl.task


OUTPUT_INSTRUCTORS_DEFAULT_SUBDIR = "cino2r2s2tu"  # quasi-anagram of "instructors"

Structurepart = tg.Union[sdrl.course.Item, sdrl.task.Task]

def generate(pargs: argparse.Namespace, course: sdrl.course.Course):
    """
    Render the tasks, intros and navigation stuff to output directories (student version, instructor version).
    For each, tenders all HTML into a single flat directory because this greatly simplifies
    the link generation.
    Uses the basenames of the chapter and taskgroup directories as keys.
    """
    targetdir_s = pargs.targetdir  # for students
    targetdir_i = _instructor_targetdir(pargs)  # for instructors
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(course.templatedir), autoescape=False)
    #----- prepare directories:
    backup_targetdir(targetdir_i, markerfile=f"_{b.CONFIG_FILENAME}")  # must do _i first if it is a subdir of _s
    backup_targetdir(targetdir_s, markerfile=f"_{b.CONFIG_FILENAME}")
    os.mkdir(targetdir_s)
    os.mkdir(targetdir_i)
    shutil.copyfile(b.CONFIG_FILENAME, f"{targetdir_s}/_{b.CONFIG_FILENAME}")  # mark dir as a SeDriLa instance
    shutil.copyfile(b.CONFIG_FILENAME, f"{targetdir_i}/_{b.CONFIG_FILENAME}")  # mark dir as a SeDriLa instance
    #----- copy baseresources:
    for filename in glob.glob(f"{course.baseresourcedir}/*"):
        shutil.copy(filename, targetdir_s)
        shutil.copy(filename, targetdir_i)
    #----- add tocs to upper structure parts:
    course.toc = toc(course)
    for chapter in course.chapters:
        chapter.toc = toc(chapter)
        for taskgroup in chapter.taskgroups:
            taskgroup.toc = toc(taskgroup)
    #----- generate top-level file:
    render_welcome(course, env, targetdir_s, b.Mode.STUDENT)
    render_welcome(course, env, targetdir_i, b.Mode.INSTRUCTOR)
    #----- generate chapter and taskgroup files:
    for chapter in course.chapters:
        render_chapter(chapter, env, targetdir_s, b.Mode.STUDENT)
        render_chapter(chapter, env, targetdir_i, b.Mode.INSTRUCTOR)
        for taskgroup in chapter.taskgroups:
            render_taskgroup(taskgroup, env, targetdir_s, b.Mode.STUDENT)
            render_taskgroup(taskgroup, env, targetdir_i, b.Mode.INSTRUCTOR)
    #----- generate task files:
    for taskname, task in course.taskdict.items():
        render_task(task, env, targetdir_s, b.Mode.STUDENT)
        render_task(task, env, targetdir_i, b.Mode.INSTRUCTOR)
    #------ report outcome:
    print(f"wrote student files to  '{targetdir_s}'")
    print(f"wrote instructor files to  '{targetdir_i}'")


def backup_targetdir(targetdir: str, markerfile: str):
    """Moves targetdir to targetdir.bak to make room for the new one."""
    if not os.path.exists(targetdir):
        return
    # ----- keep a backup copy:
    targetdir_bak = f"{targetdir}.bak"
    if os.path.exists(targetdir_bak):
        if not os.path.exists(f"{targetdir_bak}/{markerfile}"):
            raise ValueError(f"will not remove '{targetdir_bak}': it is not a SeDriLa instance")
        shutil.rmtree(targetdir_bak)
    os.rename(targetdir, targetdir_bak)


def render_welcome(course: sdrl.course.Course, env, targetdir: str, mode: b.Mode):
    template = env.get_template("welcome.html")
    output = template.render(sitetitle=course.title,
                             breadcrumb=h.breadcrumb(course),
                             title=course.title,
                             toc=course.toc, fulltoc=course.toc,
                             content=md.render_markdown(_content_for(course, mode)))
    b.spit(f"{targetdir}/{course.outputfile}", output)


def render_chapter(chapter: sdrl.course.Chapter, env, targetdir: str, mode: b.Mode):
    template = env.get_template("chapter.html")
    output = template.render(sitetitle=chapter.course.title,
                             breadcrumb=h.breadcrumb(chapter.course, chapter),
                             title=chapter.title,
                             toc=chapter.toc, fulltoc=chapter.course.toc,
                             content=md.render_markdown(_content_for(chapter, mode)))
    b.spit(f"{targetdir}/{chapter.outputfile}", output)


def render_taskgroup(taskgroup: sdrl.course.Taskgroup, env, targetdir: str, mode: b.Mode):
    template = env.get_template("taskgroup.html")
    output = template.render(sitetitle=taskgroup.chapter.course.title,
                             breadcrumb=h.breadcrumb(taskgroup.chapter.course, taskgroup.chapter, taskgroup),
                             title=taskgroup.title,
                             toc=taskgroup.toc, fulltoc=taskgroup.chapter.course.toc,
                             content=md.render_markdown(_content_for(taskgroup, mode)))
    b.spit(f"{targetdir}/{taskgroup.outputfile}", output)


def render_task(task: sdrl.task.Task, env, targetdir: str, mode: b.Mode):
    template = env.get_template("task.html")
    output = template.render(sitetitle=task.taskgroup.chapter.course.title,
                             breadcrumb=h.breadcrumb(task.taskgroup.chapter.course, task.taskgroup.chapter,
                                                     task.taskgroup, task),
                             title=task.title,
                             toc=task.taskgroup.toc, fulltoc=task.taskgroup.chapter.course.toc, 
                             content=md.render_markdown(_content_for(task, mode)))
    b.spit(f"{targetdir}/{task.outputfile}", output)


def toc(structure: Structurepart, level=0) -> str:
    """Return a table-of-contents HTML fragment for the given structure via structural recursion."""
    result = []
    if isinstance(structure, sdrl.course.Course):
        for chapter in structure.chapters:
            result.append(toc(chapter, level))
    elif isinstance(structure, sdrl.course.Chapter):
        result.append(structure.toc_link(level))  # Chapter toc_link
        for taskgroup in structure.taskgroups:
            result.append(toc(taskgroup, level+1))
    elif isinstance(structure, sdrl.course.Taskgroup):
        result.append(structure.toc_link(level))  # Taskgroup toc_link
        for task in structure.tasks:
            result.append(toc(task, level+1))
    elif isinstance(structure, sdrl.task.Task):
        result.append(structure.toc_link(level))  # Task toc_link
    else:
        assert False
    return "\n".join(result)


def _content_for(item, mode: b.Mode) -> str:
    return      item.content if mode == b.Mode.STUDENT else item.instructorcontent


def _instructor_targetdir(pargs: argparse.Namespace) -> str:
    default = f"{pargs.targetdir}/{OUTPUT_INSTRUCTORS_DEFAULT_SUBDIR}"
    has_instructor_targetdir = getattr(pargs, 'instructor_targetdir', False)
    return pargs.instructor_targetdir if has_instructor_targetdir else default