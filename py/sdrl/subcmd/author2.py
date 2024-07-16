"""
Generate the website with incremental build.
See the architecture sketch in README.
TODO:
- 
- rename slug to name, use sedrila2.yaml, force titles to be in topmatter, remove 'slug' in sedrila2.yaml
- eventually: kick out author, rename author2 to author, changelog, adjust docs
"""
import argparse
import datetime as dt
import os
import os.path

import base as b
import cache
import sdrl.course
import sdrl.course as course
import sdrl.directory as dir
import sdrl.macroexpanders as macroexpanders


meaning = """Creates and renders an instance of a SeDriLa course with incremental build.
Checks consistency of the course description beforehands.
"""

OUTPUT_INSTRUCTORS_DEFAULT_SUBDIR = "instructor"
ALTDIR_KEYWORD = "ALT:"


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
    subparser.add_argument('--clean', action='store_const', const=True, default=False,
                           help="purge cache and perform a complete build")
    subparser.add_argument('targetdir',
                           help=f"Directory to which output will be written.")


def execute(pargs: argparse.Namespace):
    b.set_loglevel(pargs.log)
    prepare_directories(pargs.targetdir)
    the_cache = cache.SedrilaCache(f"{pargs.targetdir}/{b.CACHE_FILENAME}")
    directory = dir.Directory()
    c = course  # abbrev
    the_course = c.Coursebuilder(c.Course.__name__,
            parttype=dict(Chapter=c.Chapterbuilder, Taskgroup=c.Taskgroupbuilder, Task=c.Taskbuilder), 
            configfile=pargs.config, include_stage=pargs.include_stage,
            targetdir_s=pargs.targetdir, targetdir_i=targetdir_i(pargs.targetdir),
            cache=the_cache, directory=directory)
    the_course.cache1_mode = sdrl.course.CacheMode.UNCACHED  # TODO 2: remove
    macroexpanders.register_macros(the_course)
    directory.build()
    if pargs.sums:
        print_volume_report(the_course)
    the_cache.close()  # write back changes
    b.exit_if_errors()


def prepare_directories(targetdir_s: str):
    # ----- create from scratch if needed:
    if not os.path.exists(targetdir_s):
        os.mkdir(targetdir_s)
    # ----- check plausibility:
    not_empty = len(os.listdir(targetdir_s)) > 1  # targetdir_i will exist even in fresh ones 
    metadatafile = os.path.join(targetdir_s, b.METADATA_FILE)
    if not_empty and not os.path.exists(metadatafile):  # empty pre-existing dirs will fail, too
        b.critical(f"{targetdir_s} does not look like a build directory: {b.METADATA_FILE} is missing")
    # ----- add instructor dir if needed:
    if not os.path.exists(targetdir_i(targetdir_s)):
        os.mkdir(targetdir_i(targetdir_s))


def targetdir_i(targetdir_s):
    return os.path.join(targetdir_s, OUTPUT_INSTRUCTORS_DEFAULT_SUBDIR)


def print_volume_report(course: course.Coursebuilder):
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
