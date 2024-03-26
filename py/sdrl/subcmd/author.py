import argparse
import datetime as dt
import functools
import glob
import html
import json
import os
import os.path
import pickle
import shutil
import typing as tg

import jinja2

import base as b
import sdrl.course
import sdrl.html as h
import sdrl.macros as macros
import sdrl.markdown as md
import sdrl.part

meaning = """Creates and renders an instance of a SeDriLa course.
Checks consistency of the course description beforehands.
"""

OUTPUT_INSTRUCTORS_DEFAULT_SUBDIR = "cino2r2s2tu"  # alphabetically sorted count-anagram of "instructors"


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
    b.info(f"## chapter {course.chapters[-1].slug} status: {getattr(course.chapters[-1], 'status', '-')}")
    generate(course)
    if pargs.sums:
        print_volume_report(course)
    b.exit_if_errors()


def get_course(pargs):
    CacheMode = sdrl.course.CacheMode
    targetdir_s = pargs.targetdir  # for students
    targetdir_i = f"{targetdir_s}/{OUTPUT_INSTRUCTORS_DEFAULT_SUBDIR}"  # for instructors
    cache_file = cache_filename(targetdir_i)
    if not pargs.cache or not os.path.exists(cache_file):  # no cache present
        course = sdrl.course.Course(pargs.config, read_contentfiles=True, include_stage=pargs.include_stage)
        course.cache_mode = CacheMode.WRITE if pargs.cache else CacheMode.UNCACHED
    else:  # we have a filled cache
        print(f"using cache file '{cache_file}'")
        with open(cache_file, 'rb') as f:
            course = pickle.load(f)
        course.cache_mode = sdrl.course.CacheMode.READ
        course.mtime = os.stat(cache_file).st_mtime  # reference timestamp for tasks to have changed
    course.targetdir_s = targetdir_s
    course.targetdir_i = targetdir_i
    return course


def generate(course: sdrl.course.Course):
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
    register_macros(course)
    generate_upper_parts_files(course, env)
    generate_task_files(course, env)
    generate_metadata_and_glossary(course, env)
    generate_htaccess(course)
    if course.cache_mode == sdrl.course.CacheMode.READ:
        os.utime(cache_filename(course))  # update mtime of cache file to now
    else:
        print(f"wrote student files to  '{targetdir_s}'")
        print(f"wrote instructor files to  '{targetdir_i}'")


def remove_empty_partscontainers(course: sdrl.course.Course):
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


def generate_htaccess(course: sdrl.course.Course):
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


def generate_metadata_and_glossary(course: sdrl.course.Course, env):
    if course.cache_mode == sdrl.course.CacheMode.READ:
        return  # nothing to do
    b.info(f"generating metadata file '{course.targetdir_s}/{b.METADATA_FILE}'")
    write_metadata(course, f"{course.targetdir_s}/{b.METADATA_FILE}")
    render_glossary(course, env, course.targetdir_s, b.Mode.STUDENT)
    render_glossary(course, env, course.targetdir_i, b.Mode.INSTRUCTOR)
    course.glossary.report_issues()


def generate_task_files(course: sdrl.course.Course, env):
    using_cache = course.cache_mode == sdrl.course.CacheMode.READ
    which = " for modified tasks" if using_cache else ""
    b.info(f"generating task files{which}")
    for taskname, task in course.taskdict.items():
        if task.to_be_skipped or task.taskgroup.to_be_skipped or task.taskgroup.chapter.to_be_skipped \
                or (using_cache and task_is_unchanged(task)):
            b.debug(f"  task '{task.slug}' skipped: "
                    f"{task.to_be_skipped}, {task.taskgroup.to_be_skipped}, {task.taskgroup.chapter.to_be_skipped}")
            continue  # ignore the incomplete task
        b.debug(f"  task '{task.slug}' (in {task.taskgroup.chapter.slug}/{task.taskgroup.slug})")
        if using_cache:
            print(f"re-rendering task '{task.slug}'")
            task.read_partsfile(task.sourcefile)
        render_task(task, env, course.targetdir_s, b.Mode.STUDENT)
        render_task(task, env, course.targetdir_i, b.Mode.INSTRUCTOR)


def generate_upper_parts_files(course: sdrl.course.Course, env):
    if course.cache_mode == sdrl.course.CacheMode.READ:
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


def add_tocs_to_upper_parts(course: sdrl.course.Course):
    b.info(f"building tables-of-content (TOCs)")
    course.toc = toc(course)
    for chapter in course.chapters:
        chapter.toc = toc(chapter)
        for taskgroup in chapter.taskgroups:
            taskgroup.toc = toc(taskgroup)


def copy_baseresources(course: sdrl.course.Course):
    if course.cache_mode == sdrl.course.CacheMode.READ:
        return  # nothing to do
    b.info(f"copying '{course.baseresourcedir}'")
    for filename in glob.glob(f"{course.baseresourcedir}/*"):
        b.debug(f"copying '{filename}'\t-> '{course.targetdir_s}'")
        shutil.copy(filename, course.targetdir_s)
        b.debug(f"copying '{filename}'\t-> '{course.targetdir_i}'")
        shutil.copy(filename, course.targetdir_i)


def prepare_directories(course: sdrl.course.Course):
    if course.cache_mode == sdrl.course.CacheMode.READ:
        b.info(f"cached mode: leaving directories as they are: '{course.targetdir_s}', '{course.targetdir_i}'")
    else:
        b.info(f"preparing directories '{course.targetdir_s}', '{course.targetdir_i}'")
        backup_targetdir(course.targetdir_i, markerfile=f"_{b.CONFIG_FILENAME}")  # do _i first if it is a subdir of _s
        backup_targetdir(course.targetdir_s, markerfile=f"_{b.CONFIG_FILENAME}")
        os.mkdir(course.targetdir_s)
        os.mkdir(course.targetdir_i)
        # mark dirs as SeDriLa instances:
        shutil.copyfile(course.configfile, f"{course.targetdir_s}/_{b.CONFIG_FILENAME}")  
        shutil.copyfile(course.configfile, f"{course.targetdir_i}/_{b.CONFIG_FILENAME}")
    if course.cache_mode == sdrl.course.CacheMode.WRITE:
        with open(cache_filename(course), 'wb') as f:
            pickle.dump(course, f)
        print(f"wrote cache file '{cache_filename(course)}'")


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


def register_macros(course):
    MM = macros.MM
    b.info("registering macros")
    if course.cache_mode == sdrl.course.CacheMode.READ:
        course.glossary._register_macros_phase1()  # modifies state in module 'mocros'! 
    # ----- register EARLY-mode macros:
    macros.register_macro('INCLUDE', 1, MM.EARLY,
                          expand_include)
    # ----- register INNER-mode macros:
    macros.register_macro('HREF', 1, MM.INNER,
                          functools.partial(expand_href, course))  # show and link a URL
    macros.register_macro('PARTREF', 1, MM.INNER, 
                          functools.partial(expand_partref, course))  # slug as linktext
    macros.register_macro('PARTREFTITLE', 1, MM.INNER, 
                          functools.partial(expand_partref, course))  # title as linktext
    macros.register_macro('PARTREFMANUAL', 2, MM.INNER, 
                          functools.partial(expand_partref, course))  # explicit linktext
    macros.register_macro('EC', 0, MM.INNER, expand_enumeration, partswitch_enumeration)
    macros.register_macro('EQ', 0, MM.INNER, expand_enumeration, partswitch_enumeration)
    macros.register_macro('ER', 0, MM.INNER, expand_enumeration, partswitch_enumeration)
    macros.register_macro('EREFC', 1, MM.INNER, expand_enumerationref)
    macros.register_macro('EREFQ', 1, MM.INNER, expand_enumerationref)
    macros.register_macro('EREFR', 1, MM.INNER, expand_enumerationref)
    macros.register_macro('DIFF', 1, MM.INNER, sdrl.course.Task.expand_diff)
    # ----- register hard-coded block macros:
    macros.register_macro('SECTION', 2, MM.BLOCKSTART, expand_section)
    macros.register_macro('ENDSECTION', 0, MM.BLOCKEND, expand_section)
    macros.register_macro('INNERSECTION', 2, MM.BLOCKSTART, expand_section)
    macros.register_macro('ENDINNERSECTION', 0, MM.BLOCKEND, expand_section)
    macros.register_macro('HINT', 1, MM.BLOCKSTART, expand_hint)
    macros.register_macro('ENDHINT', 0, MM.BLOCKEND, expand_hint)
    # ----- register generic block macros:
    generic_defs = {key: val for key, val in course.blockmacro_topmatter.items() if key.isupper()}
    for key, value in generic_defs.items():
        if "{arg2}" in value:
            args = 2
        elif "{arg1}" in value:
            args = 1
        else:
            args = 0
        macros.register_macro(key, args, MM.BLOCKSTART, expand_block)
        macros.register_macro(f'END{key}', 0, MM.BLOCKEND, expand_block)


def expand_href(course: sdrl.course.Course, macrocall: macros.Macrocall) -> str:
    return f"<a href='{macrocall.arg1}'>{macrocall.arg1}</a>"


def expand_partref(course: sdrl.course.Course, macrocall: macros.Macrocall) -> str:
    part = course.get_part(macrocall.filename, macrocall.arg1)
    linktext = dict(PARTREF=part.slug, 
                    PARTREFTITLE=part.title, 
                    PARTREFMANUAL=macrocall.arg2)[macrocall.macroname]
    return f"<a href='{part.outputfile}' class='partref-link'>{html.escape(linktext)}</a>"


def expand_section(macrocall: macros.Macrocall) -> str:
    """
    [SECTION::goal::subtype1,subtype2] etc.
    [INNERSECTION] is equivalent and serves for one level of proper nesting if needed.
    (Nesting [SECTION][ENDSECTION] blocks happens to work, but for the wrong reasons.)
    A section [SECTION]...[ENDSECTION] like the ahove gets rendered into the following structure:
    <div class='section section-goal'>
      <div class='section-subtypes section-goal-subtypes'>
        <div class='section-subtype section-goal-subtype1'>section_goal_subtype1_topmatter</div>
        <div class='section-subtype section-goal-subtype2'>section_goal_subtype2_topmatter</div>
      </div>
      section_goal_topmatter
      the entire body of the section block
    </div>
    """
    sectiontype = macrocall.arg1
    sectionsubtypes = macrocall.arg2
    if macrocall.macroname in ('SECTION', 'INNERSECTION'):
        r = []  # results list, to be join'ed
        r.append(f"<div class='section section-{sectiontype}'>")  # level 1
        r.append(f"<div class='section-subtypes section-{sectiontype}-subtypes'>")  # level 2
        subtypeslist = sectionsubtypes.split(",")
        for subtype in subtypeslist:
            matter = topmatter(macrocall, f'section_{sectiontype}_{subtype}')
            r.append(f"<div class='section-subtype section-{sectiontype}-{subtype}'>{matter}</div>")
        r.append("</div>")  # end level 2
        r.append(topmatter(macrocall, f'section_{sectiontype}'))
        return "\n".join(r)
    elif macrocall.macroname in ('ENDSECTION', 'ENDINNERSECTION'):
        return "</div>"
    assert False, macrocall  # impossible


def expand_hint(macrocall: macros.Macrocall) -> str:
    if macrocall.macroname == 'HINT':
        content = topmatter(macrocall, 'hint').format(arg1=macrocall.arg1)
        return f"<details class='blockmacro blockmacro-hint'><summary>\n{content}\n</summary>\n"
    elif macrocall.macroname == 'ENDHINT':
        return "</details>"
    assert False, macrocall  # impossible


def expand_block(macrocall: macros.Macrocall) -> str:
    is_end = macrocall.macroname.startswith('END')
    macroname = (macrocall.macroname if not is_end else macrocall.macroname[3:])
    if is_end:
        return f"</div>"
    else:
        content = topmatter(macrocall, macroname).format(arg1=macrocall.arg1, arg2=macrocall.arg2)
        return f"<div class='blockmacro blockmacro-{macroname.lower()}'>\n{content}"


def expand_enumeration(macrocall: macros.Macrocall) -> str:
    macroname = macrocall.macroname
    classname = f"enumeration-{macroname.lower()}"
    value = macros.get_state(macroname) + 1
    macros.set_state(macroname, value)
    return f"<span class='{classname}'>{value}</span>"


def partswitch_enumeration(macroname: str, newpartname: str):  # noqa
    macros.set_state(macroname, 0)  # is independent of newpartname


def expand_enumerationref(macrocall: macros.Macrocall) -> str:
    # markup matches that of expand_enumeration(), argument is not checked in any way
    macroname = macrocall.macroname
    classname = f"enumeration-{macroname.lower()}"
    value = macrocall.arg1
    return f"<span class='{classname}'>{value}</span>"


def expand_include(macrocall: macros.Macrocall) -> str:
    """
    [INCLUDE::filename] inserts file contents into the Markdown text.
    If the file has suffix *.md or *.md.inc, it is macro-expanded beforehands,
    contents of all other files are inserted verbatim.
    The filename is relative to the location of the file containing the macro call.
    """
    filename = macrocall.arg1
    path = os.path.dirname(macrocall.filename)
    fullfilename = os.path.join(path, filename)
    if not os.path.exists(fullfilename):
        macrocall.error(f"file '{fullfilename}' does not exist")
        return ""
    with open(fullfilename, "rt", encoding='utf8') as f:
        rawcontent = f.read()
    if filename.endswith('.md') or filename.endswith('.md.inc'):
        return macros.expand_macros(md.md.context_sourcefile, md.md.partname, rawcontent)
    else:
        return rawcontent


def render_homepage(course: sdrl.course.Course, env, targetdir: str, mode: b.Mode):
    template = env.get_template("homepage.html")
    render_structure(course, template, course, targetdir, mode)
    course.render_zipdirs(targetdir)


def render_chapter(chapter: sdrl.course.Chapter, env, targetdir: str, mode: b.Mode):
    template = env.get_template("chapter.html")
    render_structure(chapter.course, template, chapter, targetdir, mode)
    chapter.render_zipdirs(targetdir)


def render_taskgroup(taskgroup: sdrl.course.Taskgroup, env, targetdir: str, mode: b.Mode):
    template = env.get_template("taskgroup.html")
    render_structure(taskgroup.chapter.course, template, taskgroup, targetdir, mode)
    taskgroup.render_zipdirs(targetdir)


def render_task(task: sdrl.course.Task, env, targetdir: str, mode: b.Mode):
    template = env.get_template("task.html")
    course = task.taskgroup.chapter.course
    task.linkslist_top = render_task_linkslist(task, 'assumes', 'requires')
    task.linkslist_bottom = render_task_linkslist(task, 'assumed_by', 'required_by')
    render_structure(course, template, task, targetdir, mode)


def render_task_linkslist(task: sdrl.course.Task, a_attr: str, r_attr: str) -> str:
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


def render_glossary(course: sdrl.course.Course, env, targetdir: str, mode: b.Mode):
    glossary = course.glossary
    b.info(f"generating glossary '{glossary.outputfile}'")
    glossary_html = course.glossary.render(mode)
    template = env.get_template(f"{b.GLOSSARY_BASENAME}.html")
    output = template.render(sitetitle=course.title,
                             index=course.chapters[0].slug, index_title=course.chapters[0].title,
                             breadcrumb=h.breadcrumb(course, glossary),
                             title=glossary.title,
                             part=glossary,
                             toc=course.toc, fulltoc=course.toc,
                             content=glossary_html)
    b.spit(f"{targetdir}/{glossary.outputfile}", output)


def render_structure(course: sdrl.course.Course, template, structure: sdrl.part.Structurepart, 
                     targetdir: str, mode: b.Mode):
    macros.switch_part(structure.slug)
    toc = (structure.taskgroup if isinstance(structure, sdrl.course.Task) else structure).toc
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


def write_metadata(course: sdrl.course.Course, filename: str):
    b.spit(filename, json.dumps(course.as_json(), ensure_ascii=False, indent=2))


def print_volume_report(course: sdrl.course.Course):
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


def cache_filename(context: tg.Union[sdrl.course.Course, str]) -> str:
    if isinstance(context, sdrl.course.Course):
        return f"{context.targetdir_i}/{b.CACHE_FILE}"
    else:
        # the context _is_ the targetdir_i:
        return f"{context}/{b.CACHE_FILE}"


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


def topmatter(macrocall: macros.Macrocall, name: str) -> str:
    topmatterdict = macrocall.md.blockmacro_topmatter  # noqa
    if name in topmatterdict:
        return topmatterdict[name]
    else:
        b.error("'%s', %s\n  blockmacro_topmatter '%s' is not defined in config" %
                (macrocall.filename, macrocall.macrocall_text, name))
        return ""  # neutral result
