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
import sdrl.macros as macros
import sdrl.markdown as md
import sdrl.part

help = """Creates and renders an instance of a SeDriLa course.
Checks consistency of the course description beforehands.
"""

OUTPUT_INSTRUCTORS_DEFAULT_SUBDIR = "cino2r2s2tu"  # quasi-anagram of "instructors"


def configure_argparser(subparser: argparse.ArgumentParser):
    subparser.add_argument('--config', metavar="configfile", default=b.CONFIG_FILENAME,
                           help="SeDriLa configuration description YAML file")
    subparser.add_argument('--include_stage', metavar="stage", default='',
                           help="include parts with this and higher 'stage:' entries in the generated output "
                                "(default: only those with no stage)")
    subparser.add_argument('--log', default="WARNING", choices=b.loglevels.keys(),
                           help="Log level for logging to stdout (default: WARNING)")
    subparser.add_argument('--sums', action='store_const', const=True, default=False,
                           help="Print task volume reports")
    subparser.add_argument('targetdir',
                           help="Directory to which output will be written")


def execute(pargs: argparse.Namespace):
    b.set_loglevel(pargs.log)
    course = sdrl.course.Course(pargs.config, read_contentfiles=True, include_stage=pargs.include_stage)
    b.info(f"## chapter {course.chapters[-1].slug} status: {getattr(course.chapters[-1], 'status', '-')}")
    generate(pargs, course)
    b.exit_if_errors()
    if pargs.sums:
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
    shutil.copyfile(course.configfile, f"{targetdir_s}/_{b.CONFIG_FILENAME}")  # mark dir as a SeDriLa instance
    shutil.copyfile(course.configfile, f"{targetdir_i}/_{b.CONFIG_FILENAME}")  # mark dir as a SeDriLa instance
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
    macros.register_macro('PARTREF', 1, functools.partial(expand_partref, course))  # slug as linktext
    macros.register_macro('PARTREFTITLE', 1, functools.partial(expand_partref, course))  # title as linktext
    macros.register_macro('PARTREFMANUAL', 2, functools.partial(expand_partref, course))  # explicit linktext
    macros.register_macro('DIFF', 1, sdrl.course.Task.expand_diff)
    macros.register_macro('HINT', 1, expand_hint)
    macros.register_macro('ENDHINT', 0, expand_hint)
    macros.register_macro('INSTRUCTOR', 1, expand_instructor)
    macros.register_macro('ENDINSTRUCTOR', 0, expand_instructor)
    macros.register_macro('WARNING', 0, expand_warning)
    macros.register_macro('ENDWARNING', 0, expand_warning)
    macros.register_macro('NOTICE', 0, expand_notice)
    macros.register_macro('ENDNOTICE', 0, expand_notice)
    macros.register_macro('SECTION', 2, expand_section)
    macros.register_macro('ENDSECTION', 0, expand_section)
    macros.register_macro('INNERSECTION', 2, expand_section)
    macros.register_macro('ENDINNERSECTION', 0, expand_section)
    macros.register_macro('INCLUDE', 1, expand_include)
    # ----- generate top-level file:
    b.info(f"generating top-level index files")
    render_homepage(course, env, targetdir_s, b.Mode.STUDENT, course.blockmacro_topmatter)
    render_homepage(course, env, targetdir_i, b.Mode.INSTRUCTOR, course.blockmacro_topmatter)
    # ----- generate chapter and taskgroup files:
    b.info(f"generating chapter and taskgroup files")
    for chapter in course.chapters:
        if chapter.to_be_skipped:
            continue  # ignore the entire incomplete chapter
        b.info(f"  chapter '{chapter.slug}'")
        render_chapter(chapter, env, targetdir_s, b.Mode.STUDENT, course.blockmacro_topmatter)
        render_chapter(chapter, env, targetdir_i, b.Mode.INSTRUCTOR, course.blockmacro_topmatter)
        for taskgroup in chapter.taskgroups:
            if taskgroup.to_be_skipped or taskgroup.chapter.to_be_skipped:
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
    b.info(f"generating metadata file '{targetdir_s}/{b.METADATA_FILE}'")
    write_metadata(course, f"{targetdir_s}/{b.METADATA_FILE}")
    # ----- generate glossary:
    render_glossary(course, env, targetdir_s, b.Mode.STUDENT)
    render_glossary(course, env, targetdir_i, b.Mode.INSTRUCTOR)
    course.glossary.report_issues()
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


def toc(structure: sdrl.part.Structurepart) -> str:
    """Return a table-of-contents HTML fragment for the given structure via structural recursion."""
    parts = structure_path(structure)
    fulltoc = len(parts) == 1  # path only contains course
    assert isinstance(parts[-1], sdrl.course.Course)
    course = tg.cast(sdrl.course.Course, parts[-1])
    result = ['']  # start with a newline
    for chapter in course.chapters:  # noqa
        if chapter.to_be_skipped:
            continue
        result.append(chapter.toc_entry)
        if not fulltoc and chapter not in parts:
            continue
        for taskgroup in chapter.taskgroups:
            effective_tasklist = [t for t in course.taskorder 
                                  if t in taskgroup.tasks and not t.to_be_skipped]
            if taskgroup.to_be_skipped or not effective_tasklist:
                continue
            result.append(taskgroup.toc_entry)
            if not fulltoc and taskgroup not in parts:
                continue
            for task in effective_tasklist:
                result.append(task.toc_entry)
    result.append(course.glossary.toc_entry)
    return "\n".join(result)


def expand_partref(course: sdrl.course.Course, macrocall: macros.Macrocall) -> str:
    part = course.get_part(macrocall.filename, macrocall.arg1)
    linktext = dict(PARTREF=part.slug, 
                    PARTREFTITLE=part.title, 
                    PARTREFMANUAL=macrocall.arg2)[macrocall.macroname]
    return f"<a href='{part.outputfile}' class='partref-link'>{html.escape(linktext)}</a>"


def expand_hint(macrocall: macros.Macrocall) -> str:
    if macrocall.macroname == 'HINT':
        summary = macrocall.arg1
        intro = topmatter(macrocall, 'hint')
        return f"<details class='blockmacro blockmacro-hint'><summary>\n{intro}{summary}\n</summary>\n"
    elif macrocall.macroname == 'ENDHINT':
        return "</details>"
    assert False, macrocall  # impossible


def expand_instructor(macrocall: macros.Macrocall) -> str:
    if macrocall.macroname == 'INSTRUCTOR':
        title = macrocall.arg1
        intro = topmatter(macrocall, 'instructor')
        return f"<div class='blockmacro blockmacro-instructor'>\n{intro}{title}"
    elif macrocall.macroname == 'ENDINSTRUCTOR':
        return "</div>"
    assert False, macrocall  # impossible


def expand_warning(macrocall: macros.Macrocall) -> str:
    if macrocall.macroname == 'WARNING':
        return f"<div class='blockmacro blockmacro-warning'>\n{topmatter(macrocall, 'warning')}"
    elif macrocall.macroname == 'ENDWARNING':
        return "</div>"
    assert False, macrocall  # impossible


def expand_notice(macrocall: macros.Macrocall) -> str:
    if macrocall.macroname == 'NOTICE':
        return f"<div class='blockmacro blockmacro-notice'>\n{topmatter(macrocall, 'notice')}"
    elif macrocall.macroname == 'ENDNOTICE':
        return "</div>"
    assert False, macrocall  # impossible


def expand_section(macrocall: macros.Macrocall) -> str:
    """
    [SECTION::goal::goaltype1,goaltype2] etc.
    Blocks of [SECTION::forinstructor::itype] lots of text [ENDSECTION]
    can be removed by the Sedrila markdown extension before processing; see there.
    [INNERSECTION] is equivalent and serves for one level of proper nesting if needed.
    (Nesting [SECTION][ENDSECTION] blocks happens to work, but for the wrong reasons.)
    """
    sectionname = macrocall.arg1
    sectiontypes = macrocall.arg2
    if macrocall.macroname in ('SECTION', 'INNERSECTION'):
        typeslist = sectiontypes.split(",")
        types_cssclass_list = (f"section-{sectionname}-{t}" for t in typeslist)
        div = "<div class='section %s %s'>" % (f"section-{sectionname}", " ".join(types_cssclass_list))
        thetopmatter = section_topmatter(macrocall, typeslist)
        return f"{div}\n{thetopmatter}"
    elif macrocall.macroname in ('ENDSECTION', 'ENDINNERSECTION'):
        return "</div>"
    assert False, macrocall  # impossible


def expand_include(macrocall: macros.Macrocall) -> str:
    """
    [INCLUDE::filename] inserts file contents verbatim into the Markdown text.
    The filename is relative to the location of the file containing the macro call."""
    filename = macrocall.arg1
    path = os.path.dirname(macrocall.filename)
    fullfilename = os.path.join(path, filename)
    if not os.path.exists(fullfilename):
        macrocall.error(f"file '{fullfilename}' does not exist")
        return ""
    with open(fullfilename, "rt", encoding='utf8') as f:
        return f.read()


def section_topmatter(macrocall: macros.Macrocall, typeslist: list[str]) -> str:
    sectionname = macrocall.arg1
    result = ""
    for part in [""] + typeslist:
        name = f"section_{sectionname}{'_' if part else ''}{part}"
        result += topmatter(macrocall, name)
    return result


def topmatter(macrocall: macros.Macrocall, name: str) -> str:
    topmatterdict = macrocall.md.blockmacro_topmatter  # noqa
    if name in topmatterdict:
        return topmatterdict[name]
    else:
        b.error("'%s', %s\n  blockmacro_topmatter '%s' is not defined in config" %
                (macrocall.filename, macrocall.macrocall_text, name))
        return ""  # neutral result


def render_homepage(course: sdrl.course.Course, env, targetdir: str,
                    mode: b.Mode, blockmacro_topmatter: dict[str, str]):
    template = env.get_template("homepage.html")
    render_structure(course, template, course, env, targetdir, mode, blockmacro_topmatter)
    course.render_zipdirs(targetdir)


def render_chapter(chapter: sdrl.course.Chapter, env, targetdir: str, 
                   mode: b.Mode, blockmacro_topmatter: dict[str, str]):
    template = env.get_template("chapter.html")
    render_structure(chapter.course, template, chapter, env, targetdir, mode, blockmacro_topmatter)
    chapter.render_zipdirs(targetdir)


def render_taskgroup(taskgroup: sdrl.course.Taskgroup, env, targetdir: str, 
                     mode: b.Mode, blockmacro_topmatter: dict[str, str]):
    template = env.get_template("taskgroup.html")
    render_structure(taskgroup.chapter.course, template, taskgroup, env, targetdir, mode, blockmacro_topmatter)
    taskgroup.render_zipdirs(targetdir)


def render_task(task: sdrl.course.Task, env, targetdir: str, 
                mode: b.Mode, blockmacro_topmatter: dict[str, str]):
    template = env.get_template("task.html")
    course = task.taskgroup.chapter.course
    render_structure(course, template, task, env, targetdir, mode, blockmacro_topmatter)


def render_glossary(course: sdrl.course.Course, env, targetdir: str, mode: b.Mode):
    glossary = course.glossary
    b.info(f"generating glossary '{glossary.outputfile}'")
    glossary_html = course.glossary.render(mode)
    template = env.get_template("glossary.html")
    output = template.render(sitetitle=course.title,
                             index=course.chapters[0].slug, index_title=course.chapters[0].title,
                             breadcrumb=h.breadcrumb(course, glossary),
                             title=glossary.title,
                             part=glossary,
                             toc=course.toc, fulltoc=course.toc,
                             content=glossary_html)
    b.spit(f"{targetdir}/{glossary.outputfile}", output)


def render_structure(course: sdrl.course.Course, 
                     template, structure: sdrl.part.Structurepart, 
                     env, targetdir: str, 
                     mode: b.Mode, blockmacro_topmatter: dict[str, str]):
    toc = (structure.taskgroup if isinstance(structure, sdrl.course.Task) else structure).toc
    html = md.render_markdown(structure.sourcefile, structure.slug, structure.content, mode, blockmacro_topmatter)
    output = template.render(sitetitle=course.title,
                             index=course.chapters[0].slug, index_title=course.chapters[0].title,
                             breadcrumb=h.breadcrumb(*structure_path(structure)[::-1]),
                             title=structure.title,
                             linkslist=structure.linkslist,
                             part=structure,
                             toc=toc, fulltoc=course.toc,
                             content=html)
    b.spit(f"{targetdir}/{structure.outputfile}", output)


def structure_path(structure: sdrl.part.Structurepart) -> list[sdrl.part.Structurepart]:
    """List of nested parts, from a given part up to the course."""
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
    """Show total timevalues per stage, difficulty, and chapter."""
    for report in (course.volume_report_per_stage(),
                   course.volume_report_per_difficulty(),
                   course.volume_report_per_chapter()):
        table = b.Table()
        table.add_column(report.columnheads[0])
        table.add_column(report.columnheads[1], justify="right")
        table.add_column(report.columnheads[2], justify="right")
        totaltasks = totaltime = 0
        for name, numtasks, timevalue in report.rows:
            table.add_row(name,
                          str(numtasks),
                          "%5.1f" % timevalue)
            totaltasks += numtasks
            totaltime += timevalue
        table.add_row("[b]=TOTAL", f"[b]{totaltasks}","[b]%5.1f" % totaltime)
        b.rich_print(table)  # noqa


def _instructor_targetdir(pargs: argparse.Namespace) -> str:
    default = f"{pargs.targetdir}/{OUTPUT_INSTRUCTORS_DEFAULT_SUBDIR}"
    has_instructor_targetdir = getattr(pargs, 'instructor_targetdir', False)
    return pargs.instructor_targetdir if has_instructor_targetdir else default
