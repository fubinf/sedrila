import argparse
import functools
import glob
import html
import json
import os
import os.path
import shutil
import typing as tg

import jinja2

import base as b
import sdrl.course
import sdrl.html as h
import sdrl.markdown as md

help = """Creates and renders an instance of a SeDriLa course.
Checks consistency of the course description beforehands.
"""

OUTPUT_INSTRUCTORS_DEFAULT_SUBDIR = "cino2r2s2tu"  # quasi-anagram of "instructors"

Structurepart = tg.Union[sdrl.course.Item, sdrl.course.Task]


def configure_argparser(subparser: argparse.ArgumentParser):
    subparser.add_argument('--config', default=b.CONFIG_FILENAME,
                           help="SeDriLa configuration description YAML file")
    subparser.add_argument('--incomplete', default=False, action='store_const', const=True,
                           help="include parts with 'status: incomplete' in the generated output")
    subparser.add_argument('--log', default="ERROR", choices=b.loglevels.keys(),
                           help="Log level for logging to stdout")
    subparser.add_argument('targetdir',
                           help="Directory to which output will be written")


def execute(pargs: argparse.Namespace):
    b.set_loglevel(pargs.log)
    course = sdrl.course.Course(pargs.config, read_contentfiles=True, include_incomplete=pargs.incomplete)
    b.info(f"## chapter {course.chapters[-1].shorttitle} status: {getattr(course.chapters[-1], 'status', '-')}")
    generate(pargs, course)
    b.exit_if_errors()
    print_volume_report(course)


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
    # ----- prepare directories:
    b.info(f"preparing directories '{targetdir_s}', '{targetdir_i}'")
    backup_targetdir(targetdir_i, markerfile=f"_{b.CONFIG_FILENAME}")  # must do _i first if it is a subdir of _s
    backup_targetdir(targetdir_s, markerfile=f"_{b.CONFIG_FILENAME}")
    os.mkdir(targetdir_s)
    os.mkdir(targetdir_i)
    shutil.copyfile(b.CONFIG_FILENAME, f"{targetdir_s}/_{b.CONFIG_FILENAME}")  # mark dir as a SeDriLa instance
    shutil.copyfile(b.CONFIG_FILENAME, f"{targetdir_i}/_{b.CONFIG_FILENAME}")  # mark dir as a SeDriLa instance
    # ----- copy baseresources:
    b.info(f"copying '{course.baseresourcedir}'")
    for filename in glob.glob(f"{course.baseresourcedir}/*"):
        b.debug(f"copying '{filename}'\t-> '{targetdir_s}'")
        shutil.copy(filename, targetdir_s)
        b.debug(f"copying '{filename}'\t-> '{targetdir_i}'")
        shutil.copy(filename, targetdir_i)
    # ----- add tocs to upper structure parts:
    b.info(f"building tables-of-content (TOCs)")
    course.toc = toc(course)
    for chapter in course.chapters:
        chapter.toc = toc(chapter)
        for taskgroup in chapter.taskgroups:
            taskgroup.toc = toc(taskgroup)
    # ----- register macroexpanders:
    b.info("registering macros")
    md.register_macro('TAS', 1, functools.partial(expand_ta, course))  # short link to task
    md.register_macro('TAL', 1, functools.partial(expand_ta, course))  # long link
    md.register_macro('TAM', 2, functools.partial(expand_ta, course))  # manual link
    md.register_macro('TGS', 1, functools.partial(expand_tg, course))  # short link to taskgroup
    md.register_macro('TGL', 1, functools.partial(expand_tg, course))  # long link
    md.register_macro('TGM', 2, functools.partial(expand_tg, course))  # manual link
    md.register_macro('CHS', 1, functools.partial(expand_ch, course))  # short link to chapter
    md.register_macro('CHL', 1, functools.partial(expand_ch, course))  # long link
    md.register_macro('CHM', 2, functools.partial(expand_ch, course))  # manual link
    md.register_macro('HINT', 1, expand_hint)
    md.register_macro('ENDHINT', 0, expand_hint)
    md.register_macro('INSTRUCTOR', 1, expand_instructor)
    md.register_macro('ENDINSTRUCTOR', 0, expand_instructor)
    md.register_macro('WARNING', 0, expand_warning)
    md.register_macro('ENDWARNING', 0, expand_warning)
    md.register_macro('SECTION', 2, expand_section)
    md.register_macro('ENDSECTION', 0, expand_section)
    # ----- generate top-level file:
    b.info(f"generating top-level index files")
    render_welcome(course, env, targetdir_s, b.Mode.STUDENT, course.blockmacro_topmatter)
    render_welcome(course, env, targetdir_i, b.Mode.INSTRUCTOR, course.blockmacro_topmatter)
    # ----- generate chapter and taskgroup files:
    b.info(f"generating chapter and taskgroup files")
    for chapter in course.chapters:
        if chapter.to_be_skipped:
            continue  # ignore the entire incomplete chapter
        b.info(f"  chapter '{chapter.slug}'")
        render_chapter(chapter, env, targetdir_s, b.Mode.STUDENT, course.blockmacro_topmatter)
        render_chapter(chapter, env, targetdir_i, b.Mode.INSTRUCTOR, course.blockmacro_topmatter)
        for taskgroup in chapter.taskgroups:
            if taskgroup.to_be_skipped:
                continue  # ignore the entire incomplete taskgroup
            b.info(f"    taskgroup '{taskgroup.slug}'")
            render_taskgroup(taskgroup, env, targetdir_s, b.Mode.STUDENT, course.blockmacro_topmatter)
            render_taskgroup(taskgroup, env, targetdir_i, b.Mode.INSTRUCTOR, course.blockmacro_topmatter)
    # ----- generate task files:
    b.info(f"generating task files")
    for taskname, task in course.taskdict.items():
        if task.to_be_skipped or task.taskgroup.to_be_skipped or task.taskgroup.chapter.to_be_skipped:
            continue  # ignore the incomplete task
        b.debug(f"  task '{task.slug}'")
        render_task(task, env, targetdir_s, b.Mode.STUDENT, course.blockmacro_topmatter)
        render_task(task, env, targetdir_i, b.Mode.INSTRUCTOR, course.blockmacro_topmatter)
    # ----- generate metadata file:
    b.info(f"generating metadata file '{targetdir_s}/{sdrl.course.METADATA_FILE}'")
    write_metadata(course, f"{targetdir_s}/{sdrl.course.METADATA_FILE}")
    # ------ report outcome:
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


def toc(structure: Structurepart) -> str:
    """Return a table-of-contents HTML fragment for the given structure via structural recursion."""
    parts = structure_path(structure)
    fulltoc = len(parts) == 1  # path only contains course
    assert isinstance(parts[-1], sdrl.course.Course)
    course = parts[-1]
    result = []
    for chapter in course.chapters:  # noqa
        if chapter.to_be_skipped:
            continue
        result.append(chapter.toc_link(0))
        if not fulltoc and chapter not in parts:
            continue
        for taskgroup in chapter.taskgroups:
            if taskgroup.to_be_skipped:
                continue
            result.append(taskgroup.toc_link(1))
            if not fulltoc and taskgroup not in parts:
                continue
            for task in (t for t in course.taskorder if t in taskgroup.tasks):  # noqa
                if not task.to_be_skipped:
                    result.append(task.toc_link(2))
    return "\n".join(result)


def expand_ta(course: sdrl.course.Course, macrocall: md.Macrocall) -> str:
    taskname = macrocall.arg1
    linktext = macrocall.arg2
    task = course.task(taskname)
    if task is None:
        macrocall.error(f"Task '{taskname}' does not exist")
        return ""
    if macrocall.macroname == "TA0":
        return task.breadcrumb_item
    elif macrocall.macroname == "TA1":
        return task.toc_link_text
    elif macrocall.macroname == "TA2":
        return f"[{html.escape(linktext, quote=False)}]({task.outputfile})"
    else:
        assert False, macrocall  # impossible


def expand_tg(course: sdrl.course.Course, macrocall: md.Macrocall) -> str:
    slug = macrocall.arg1
    linktext = macrocall.arg2
    taskgroup = course.taskgroup(slug)
    if taskgroup is None:
        macrocall.error(f"Taskgroup '{slug}' does not exist")
        return ""
    if macrocall.macroname == "TG0":
        return taskgroup.breadcrumb_item
    elif macrocall.macroname == "TG1":
        return taskgroup.toc_link_text
    elif macrocall.macroname == "TG2":
        return f"[{html.escape(linktext, quote=False)}]({taskgroup.outputfile})"
    else:
        assert False, macrocall  # impossible


def expand_ch(course: sdrl.course.Course, macrocall: md.Macrocall) -> str:
    slug = macrocall.arg1
    linktext = macrocall.arg2
    chapter = course.chapter(slug)
    if chapter is None:
        macrocall.error(f"Chapter '{slug}' does not exist")
        return ""
    if macrocall.macroname == "CH0":
        return chapter.breadcrumb_item
    elif macrocall.macroname == "CH1":
        return chapter.toc_link_text
    elif macrocall.macroname == "CH2":
        return f"[{html.escape(linktext, quote=False)}]({chapter.outputfile})"
    else:
        assert False, macrocall  # impossible


def expand_hint(macrocall: md.Macrocall) -> str:
    if macrocall.macroname == 'HINT':
        summary = macrocall.arg1
        intro = topmatter(macrocall, 'hint')
        return f"<details class='blockmacro-hint'><summary>\n{intro}{summary}\n</summary>\n"
    elif macrocall.macroname == 'ENDHINT':
        return "</details>"
    assert False, macrocall  # impossible


def expand_instructor(macrocall: md.Macrocall) -> str:
    if macrocall.macroname == 'INSTRUCTOR':
        title = macrocall.arg1
        intro = topmatter(macrocall, 'instructor')
        return f"<div class='blockmacro-instructor'>\n{intro}{title}"
    elif macrocall.macroname == 'ENDINSTRUCTOR':
        return "</div>"
    assert False, macrocall  # impossible


def expand_warning(macrocall: md.Macrocall) -> str:
    if macrocall.macroname == 'WARNING':
        return f"<div class='blockmacro-warning'>\n{topmatter(macrocall, 'warning')}"
    elif macrocall.macroname == 'ENDWARNING':
        return "</div>"
    assert False, macrocall  # impossible


def expand_section(macrocall: md.Macrocall) -> str:
    """
    [SECTION::goal::goaltype1,goaltype2] etc.
    Blocks of [SECTION::forinstructor::itype] lots of text [ENDSECTION]
    can be removed by the Sedrila markdown extension before processing; see there.
    """
    sectionname = macrocall.arg1
    sectiontypes = macrocall.arg2
    if macrocall.macroname == 'SECTION':
        typeslist = sectiontypes.split(",")
        types_cssclass_list = (f"section-{sectionname}-{t}" for t in typeslist)
        div = "<div class='section %s %s'>" % (f"section-{sectionname}", " ".join(types_cssclass_list))
        thetopmatter = section_topmatter(macrocall, typeslist)
        return f"{div}\n{thetopmatter}"
    elif macrocall.macroname == 'ENDSECTION':
        return "</div>"
    assert False, macrocall  # impossible


def section_topmatter(macrocall: md.Macrocall, typeslist: list[str]) -> str:
    sectionname = macrocall.arg1
    result = ""
    for part in [""] + typeslist:
        name = f"section_{sectionname}{'_' if part else ''}{part}"
        result += topmatter(macrocall, name)
    return result


def topmatter(macrocall: md.Macrocall, name: str) -> str:
    topmatterdict = macrocall.md.blockmacro_topmatter  # noqa
    if name in topmatterdict:
        return topmatterdict[name]
    else:
        b.error("'%s', %s\n  blockmacro_topmatter '%s' is not defined in config" %
                (macrocall.filename, macrocall.macrocall_text, name))
        return ""  # neutral result


def render_welcome(course: sdrl.course.Course, env, targetdir: str, 
                   mode: b.Mode, blockmacro_topmatter: dict[str, str]):
    template = env.get_template("welcome.html")
    if hasattr(course, "content"):
        render_structure(course, template, course, env, targetdir, mode, blockmacro_topmatter)


def render_chapter(chapter: sdrl.course.Chapter, env, targetdir: str, 
                   mode: b.Mode, blockmacro_topmatter: dict[str, str]):
    template = env.get_template("chapter.html")
    render_structure(chapter.course, template, chapter, env, targetdir, mode, blockmacro_topmatter)


def render_taskgroup(taskgroup: sdrl.course.Taskgroup, env, targetdir: str, 
                     mode: b.Mode, blockmacro_topmatter: dict[str, str]):
    template = env.get_template("taskgroup.html")
    render_structure(taskgroup.chapter.course, template, taskgroup, env, targetdir, mode, blockmacro_topmatter)


def render_task(task: sdrl.course.Task, env, targetdir: str, 
                mode: b.Mode, blockmacro_topmatter: dict[str, str]):
    template = env.get_template("task.html")
    course = task.taskgroup.chapter.course
    render_structure(course, template, task, env, targetdir, mode, blockmacro_topmatter)


def render_structure(course: sdrl.course.Course, 
                     template, structure: Structurepart, 
                     env, targetdir: str, 
                     mode: b.Mode, blockmacro_topmatter: dict[str, str]):
    toc = (structure.taskgroup if isinstance(structure, sdrl.course.Task) else structure).toc
    html = md.render_markdown(structure.inputfile, structure.content, mode, blockmacro_topmatter)
    output = template.render(sitetitle=course.title,
                             index=course.chapters[0].slug, index_title=course.chapters[0].title,
                             breadcrumb=h.breadcrumb(*structure_path(structure)[::-1]),
                             title=structure.title,
                             toc=toc, fulltoc=course.toc,
                             content=html)
    b.spit(f"{targetdir}/{structure.outputfile}", output)


def structure_path(structure: Structurepart) -> list[Structurepart]:
    path = []
    if isinstance(structure, sdrl.course.Task):
        path.append(structure)
        structure = structure.taskgroup
    if isinstance(structure, sdrl.course.Taskgroup):
        path.append(structure)
        structure = structure.chapter
    if isinstance(structure, sdrl.course.Chapter):
        path.append(structure)
        structure = structure.course
    if isinstance(structure, sdrl.course.Course):
        path.append(structure)
    return path


def write_metadata(course: sdrl.course.Course, filename: str):
    b.spit(filename, json.dumps(course.as_json(), ensure_ascii=False, indent=2))


def print_volume_report(course: sdrl.course.Course):
    """Show total timevalues per difficulty and per chapter."""
    table = b.Table()
    table.add_column("Difficulty")
    table.add_column("#Tasks", justify="right")
    table.add_column("Timevalue", justify="right")
    for difficulty, numtasks, timevalue in course.volume_report_per_difficulty():
        table.add_row(f"{difficulty}:{h.difficulty_levels[difficulty-1]}",
                      str(numtasks), 
                      "%5.1f" % timevalue)
    table.add_row("[b]=TOTAL", 
                  f"[b]{len(course.taskdict)}", 
                  "[b]%5.1f" % sum((t.timevalue for t in course._all_tasks()
                                    if not t.to_be_skipped)))
    b.info(table)  # noqa
    table = b.Table()
    table.add_column("Chapter")
    table.add_column("#Tasks", justify="right")
    table.add_column("Timevalue", justify="right")
    for chaptername, numtasks, timevalue in course.volume_report_per_chapter():
        table.add_row(chaptername,
                      str(numtasks), 
                      "%5.1f" % timevalue)
    b.info(table)  # noqa


def _instructor_targetdir(pargs: argparse.Namespace) -> str:
    default = f"{pargs.targetdir}/{OUTPUT_INSTRUCTORS_DEFAULT_SUBDIR}"
    has_instructor_targetdir = getattr(pargs, 'instructor_targetdir', False)
    return pargs.instructor_targetdir if has_instructor_targetdir else default
