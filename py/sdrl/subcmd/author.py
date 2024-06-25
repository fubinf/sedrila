import argparse
import datetime as dt
import functools
import glob
import html
import json
import os
import os.path
import pickle
import re
import shutil
import typing as tg

import jinja2

import base as b
import sdrl.course
import sdrl.glossary
import sdrl.html as h
import sdrl.macros as macros
import sdrl.macroexpanders as macroexpanders
import sdrl.markdown as md
import sdrl.part

meaning = """Creates and renders an instance of a SeDriLa course.
Checks consistency of the course description beforehands.
"""

OUTPUT_INSTRUCTORS_DEFAULT_SUBDIR = "instructor"


def add_arguments(subparser: argparse.ArgumentParser):
    subparser.add_argument('--config', metavar="configfile", default=b.CONFIG_FILENAME,
                           help="SeDriLa configuration description YAML file")
    subparser.add_argument('--include_stage', metavar="stage", default='',
                           help="include parts with this and higher 'stage:' entries in the generated output "
                                "(default: only those with no stage)")
    subparser.add_argument('--log', default="WARNING", choices=b.loglevels.keys(),
                           help="Log level for logging to stdout (default: WARNING)")
    subparser.add_argument('--sums', action='store_const', const=True, default=False,
                           help="Print task volume reports")
    subparser.add_argument('--cache', action='store_const', const=True, default=False,
                           help="re-use metadata and output, re-render only task files that have changed")
    subparser.add_argument('targetdir',
                           help=f"Directory to which output will be written.")


def execute(pargs: argparse.Namespace):
    b.set_loglevel(pargs.log)
    course = get_course(pargs)
    generate(course)
    if pargs.sums:
        print_volume_report(course)
    b.exit_if_errors()


def get_course(pargs):
    CacheMode = sdrl.course.CacheMode
    targetdir_s = pargs.targetdir  # for students
    targetdir_i = f"{targetdir_s}/{OUTPUT_INSTRUCTORS_DEFAULT_SUBDIR}"  # for instructors
    cache1_file = cache_filename(targetdir_i)
    if not pargs.cache or not os.path.exists(cache1_file):  # no cache present
        course = sdrl.course.Coursebuilder(pargs.config, include_stage=pargs.include_stage)
        course.cache1_mode = CacheMode.WRITE if pargs.cache else CacheMode.UNCACHED
    else:  # we have a filled cache
        print(f"using cache1 file '{cache1_file}'")
        with open(cache1_file, 'rb') as f:
            course = pickle.load(f)
        course.cache1_mode = sdrl.course.CacheMode.READ
        course.mtime = os.stat(cache1_file).st_mtime  # reference timestamp for tasks to have changed
    course.targetdir_s = targetdir_s
    course.targetdir_i = targetdir_i
    return course


def generate(course: sdrl.course.Coursebuilder):
    """
    Render the tasks, intros and navigation stuff to output directories (student version, instructor version).
    For each, tenders all HTML into a single flat directory because this greatly simplifies
    the link generation.
    Uses the basenames of the chapter and taskgroup directories as keys.
    """
    targetdir_s = course.targetdir_s
    targetdir_i = course.targetdir_i
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(course.templatedir), autoescape=False)
    prepare_directories(course)
    copy_baseresources(course)
    remove_empty_partscontainers(course)
    add_tocs_to_upper_parts(course)
    macroexpanders.register_macros(course)
    generate_upper_parts_files(course, env)
    generate_task_files(course, env)
    generate_metadata_and_glossary(course, env)
    generate_itree_zipfile(course)
    generate_htaccess(course)
    if course.cache1_mode == sdrl.course.CacheMode.READ:
        os.utime(cache_filename(course))  # update mtime of cache file to now
    else:
        print(f"wrote student files to  '{targetdir_s}'")
        print(f"wrote instructor files to  '{targetdir_i}'")


def remove_empty_partscontainers(course: sdrl.course.Coursebuilder):
    b.info("removing empty partscontainers")
    chapters_new = list(course.chapters)  # copy
    for chapter in course.chapters:  # iterate original
        taskgroups_new = list(chapter.taskgroups)  # copy
        for taskgroup in chapter.taskgroups:  # iterate original
            size = sum(1 for t in taskgroup.tasks if not t.to_be_skipped)
            if size == 0:  # taskgroup is empty
                b.info(f"    removing taskgroup '{taskgroup.slug}'\tfrom chapter '{chapter.slug}'")
                taskgroups_new.remove(taskgroup)
        chapter.taskgroups = taskgroups_new
        if len(chapter.taskgroups) == 0:  # chapter is empty
            b.info(f"  removing chapter '{chapter.slug}'")
            chapters_new.remove(chapter)
    course.chapters = chapters_new


def generate_htaccess(course: sdrl.course.Coursebuilder):
    if not course.htaccess_template:
        return  # nothing to do
    targetfile = f"{course.targetdir_i}/.htaccess"
    b.info(f"generating htaccess file '{targetfile}'")
    userlist = [u['webaccount'] for u in course.instructors]
    htaccess_txt = (course.htaccess_template.format( 
                       userlist_commas=",".join(userlist), 
                       userlist_spaces=" ".join(userlist),
                       userlist_quotes_spaces=" ".join((f'"{u}"' for u in userlist))))
    b.spit(f"{targetfile}", htaccess_txt)


def generate_itree_zipfile(course: sdrl.course.Coursebuilder):
    if not course.itreedir or course.cache1_mode == sdrl.course.CacheMode.READ:
        return  # nothing to do
    b.info(f"generating itreedir ZIP file to '{course.targetdir_i}/{course.itreedir}'")
    if not course.itreedir.endswith(".zip"):
        b.critical(f"itreedir = '{course.itreedir}'; must end with '.zip'")
    itreedir = sdrl.part.Partscontainer()
    itreedir.zipdirs = [sdrl.part.Zipdir(course.itreedir)]
    itreedir.render_zipdirs(course.targetdir_i)


def generate_metadata_and_glossary(course: sdrl.course.Coursebuilder, env):
    if course.cache1_mode == sdrl.course.CacheMode.READ:
        return  # nothing to do
    b.info(f"generating metadata file '{course.targetdir_s}/{b.METADATA_FILE}'")
    write_metadata(course, f"{course.targetdir_s}/{b.METADATA_FILE}")
    render_glossary(course, env, course.targetdir_s, b.Mode.STUDENT)
    render_glossary(course, env, course.targetdir_i, b.Mode.INSTRUCTOR)
    course.glossary.report_issues()


def generate_task_files(course: sdrl.course.Coursebuilder, env):
    using_cache1 = course.cache1_mode == sdrl.course.CacheMode.READ
    which = " for modified tasks" if using_cache1 else ""
    b.info(f"generating task files{which}")
    for taskname, task in course.taskdict.items():
        if task.to_be_skipped or task.taskgroup.to_be_skipped or task.taskgroup.chapter.to_be_skipped \
                or (using_cache1 and task_is_unchanged(task)):
            b.debug(f"  task '{task.slug}' skipped: "
                    f"{task.to_be_skipped}, {task.taskgroup.to_be_skipped}, {task.taskgroup.chapter.to_be_skipped}")
            continue  # ignore the incomplete task
        b.debug(f"  task '{task.slug}' (in {task.taskgroup.chapter.slug}/{task.taskgroup.slug})")
        if using_cache1:
            print(f"re-rendering task '{task.slug}'")
            task.read_partsfile(task.sourcefile)
        render_task(task, env, course.targetdir_s, b.Mode.STUDENT)
        render_task(task, env, course.targetdir_i, b.Mode.INSTRUCTOR)


def generate_upper_parts_files(course: sdrl.course.Coursebuilder, env):
    if course.cache1_mode == sdrl.course.CacheMode.READ:
        return  # nothing to do
    # ----- generate top-level file:
    b.info(f"generating top-level index files")
    render_homepage(course, env, course.targetdir_s, b.Mode.STUDENT)
    render_homepage(course, env, course.targetdir_i, b.Mode.INSTRUCTOR)
    # ----- generate chapter and taskgroup files:
    b.info(f"generating chapter and taskgroup files")
    for chapter in course.chapters:
        if chapter.to_be_skipped:
            continue  # ignore the entire incomplete chapter
        b.info(f"  chapter '{chapter.slug}'")
        render_chapter(chapter, env, course.targetdir_s, b.Mode.STUDENT)
        render_chapter(chapter, env, course.targetdir_i, b.Mode.INSTRUCTOR)
        for taskgroup in chapter.taskgroups:
            if taskgroup.to_be_skipped or taskgroup.chapter.to_be_skipped:
                continue  # ignore the entire incomplete taskgroup
            b.info(f"    taskgroup '{taskgroup.slug}'")
            render_taskgroup(taskgroup, env, course.targetdir_s, b.Mode.STUDENT)
            render_taskgroup(taskgroup, env, course.targetdir_i, b.Mode.INSTRUCTOR)


def add_tocs_to_upper_parts(course: sdrl.course.Coursebuilder):
    b.info(f"building tables-of-content (TOCs)")
    course.toc = toc(course)
    for chapter in course.chapters:
        chapter.toc = toc(chapter)
        for taskgroup in chapter.taskgroups:
            taskgroup.toc = toc(taskgroup)
    course.glossary.toc = toc_for_glossary(course)


def copy_baseresources(course: sdrl.course.Coursebuilder):
    if course.cache1_mode == sdrl.course.CacheMode.READ:
        return  # nothing to do
    b.info(f"copying '{course.baseresourcedir}'")
    for filename in glob.glob(f"{course.baseresourcedir}/*"):
        b.debug(f"copying '{filename}'\t-> '{course.targetdir_s}'")
        shutil.copy(filename, course.targetdir_s)
        b.debug(f"copying '{filename}'\t-> '{course.targetdir_i}'")
        shutil.copy(filename, course.targetdir_i)


def prepare_directories(course: sdrl.course.Coursebuilder):
    if course.cache1_mode == sdrl.course.CacheMode.READ:
        b.info(f"cached1 mode: leaving directories as they are: '{course.targetdir_s}', '{course.targetdir_i}'")
    else:
        b.info(f"preparing directories '{course.targetdir_s}', '{course.targetdir_i}'")
        backup_targetdir(course.targetdir_i, markerfile=b.CONFIG_FILENAME)  # do _i first if it is a subdir of _s
        backup_targetdir(course.targetdir_s, markerfile=b.CONFIG_FILENAME)
        os.mkdir(course.targetdir_s)
        os.mkdir(course.targetdir_i)
        # mark dirs as SeDriLa instances:
        shutil.copyfile(course.configfile, f"{course.targetdir_s}/{b.CONFIG_FILENAME}")  
        shutil.copyfile(course.configfile, f"{course.targetdir_i}/{b.CONFIG_FILENAME}")
    if course.cache1_mode == sdrl.course.CacheMode.WRITE:
        with open(cache_filename(course), 'wb') as f:
            pickle.dump(course, f)
        print(f"wrote cache1 file '{cache_filename(course)}'")


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
    assert isinstance(parts[-1], sdrl.course.Coursebuilder)
    course = tg.cast(sdrl.course.Coursebuilder, parts[-1])
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


def toc_for_glossary(course: sdrl.course.Coursebuilder) -> str:
    """Return a chapters-only table of contents for the glossary."""
    result = ['']  # start with a newline
    for chapter in course.chapters:  # noqa
        if chapter.to_be_skipped:
            continue
        result.append(chapter.toc_entry)
    return "\n".join(result)


def render_homepage(course: sdrl.course.Coursebuilder, env, targetdir: str, mode: b.Mode):
    template = env.get_template("homepage.html")
    render_structure(course, template, course, targetdir, mode)
    course.render_zipdirs(targetdir)


def render_chapter(chapter: sdrl.course.Chapterbuilder, env, targetdir: str, mode: b.Mode):
    template = env.get_template("chapter.html")
    render_structure(chapter.course, template, chapter, targetdir, mode)
    chapter.render_zipdirs(targetdir)


def render_taskgroup(taskgroup: sdrl.course.Taskgroupbuilder, env, targetdir: str, mode: b.Mode):
    template = env.get_template("taskgroup.html")
    render_structure(taskgroup.chapter.course, template, taskgroup, targetdir, mode)
    taskgroup.render_zipdirs(targetdir)


def render_task(task: sdrl.course.Taskbuilder, env, targetdir: str, mode: b.Mode):
    template = env.get_template("task.html")
    course = task.taskgroup.chapter.course
    task.linkslist_top = render_task_linkslist(task, 'assumes', 'requires')
    task.linkslist_bottom = render_task_linkslist(task, 'assumed_by', 'required_by')
    render_structure(course, template, task, targetdir, mode)


def render_task_linkslist(task: sdrl.course.Taskbuilder, a_attr: str, r_attr: str) -> str:
    """HTML for the links to assumes/requires (or assumed_by/required_by) related tasks on a task page."""
    links = []
    a_links = sorted((f"[PARTREF::{part}]" for part in getattr(task, a_attr)))
    r_links = sorted((f"[PARTREF::{part}]" for part in getattr(task, r_attr)))
    a_cssname = a_attr.replace("_", "")
    r_cssname = r_attr.replace("_", "")
    any_links = a_links or r_links
    if any_links:
        links.append(f"\n<div class='{a_cssname}-{r_cssname}-linkblock'>\n")
    if a_links:
        links.append(f" <div class='{a_cssname}-links'>\n   ")
        links.append("  " + macros.expand_macros("-", task.slug, ", ".join(a_links)))
        links.append("\n </div>\n")
    if r_links:
        links.append(f" <div class='{r_cssname}-links'>\n")
        links.append("  " + macros.expand_macros("-", task.slug, ", ".join(r_links)))
        links.append("\n </div>\n")
    if any_links:
        links.append("</div>\n")
    return "".join(links)


def render_glossary(course: sdrl.course.Coursebuilder, env, targetdir: str, mode: b.Mode):
    glossary = course.glossary
    b.info(f"generating glossary '{glossary.outputfile}'")
    glossary_html = course.glossary.render(mode)
    template = env.get_template(f"{b.GLOSSARY_BASENAME}.html")
    output = template.render(sitetitle=course.title,
                             index=course.chapters[0].slug, index_title=course.chapters[0].title,
                             breadcrumb=h.breadcrumb(course, glossary),
                             title=glossary.title,
                             part=glossary,
                             toc=glossary.toc, fulltoc=course.toc,
                             content=glossary_html)
    b.spit(f"{targetdir}/{glossary.outputfile}", output)


def render_structure(course: sdrl.course.Coursebuilder, template, structure: sdrl.part.Structurepart, 
                     targetdir: str, mode: b.Mode):
    macros.switch_part(structure.slug)
    toc = (structure.taskgroup if isinstance(structure, sdrl.course.Taskbuilder) else structure).toc
    html = md.render_markdown(structure.sourcefile, structure.slug, structure.content, mode, 
                              course.blockmacro_topmatter)
    output = template.render(sitetitle=course.title,
                             index=course.chapters[0].slug, index_title=course.chapters[0].title,
                             breadcrumb=h.breadcrumb(*structure_path(structure)[::-1]),
                             title=structure.title,
                             linkslist_top=structure.linkslist_top,
                             linkslist_bottom=structure.linkslist_bottom,
                             part=structure,
                             toc=toc, fulltoc=course.toc,
                             content=html)
    b.spit(f"{targetdir}/{structure.outputfile}", output)


def write_metadata(course: sdrl.course.Coursebuilder, filename: str):
    b.spit(filename, json.dumps(course.as_json(), ensure_ascii=False, indent=2))


def print_volume_report(course: sdrl.course.Coursebuilder):
    """Show total timevalues per stage, difficulty, and chapter."""
    # ----- print cumulative timevalues per stage as comma-separated values (CSV):
    volume_report_per_stage = course.volume_report_per_stage()
    print("date", end="")
    for stage, numtasks, timevalue in volume_report_per_stage.rows:
        print(f",{stage}", end="")
    print("")  # newline
    print(dt.date.today().strftime("%Y-%m-%d"), end="")
    for stage, numtasks, timevalue in volume_report_per_stage.rows:
        print(",%.2f" % timevalue, end="")
    print("")  # newline

    # ----- print all reports as rich tables:
    for report in (volume_report_per_stage,
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
        table.add_row("[b]=TOTAL", f"[b]{totaltasks}", "[b]%5.1f" % totaltime)
        b.rich_print(table)  # noqa


def cache_filename(context: tg.Union[sdrl.course.Coursebuilder, str]) -> str:
    if isinstance(context, sdrl.course.Coursebuilder):
        return f"{context.targetdir_i}/{b.CACHE1_FILE}"
    else:
        # the context _is_ the targetdir_i:
        return f"{context}/{b.CACHE1_FILE}"


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


def task_is_unchanged(task: sdrl.course.Task) -> bool:
    task_mtime = os.stat(task.sourcefile).st_mtime
    return task_mtime < task.taskgroup.chapter.course.mtime
