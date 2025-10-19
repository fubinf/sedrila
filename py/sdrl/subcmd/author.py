"""
Generate the website with incremental build.
See the architecture sketch in docs/internal_notes.md.
TODO:
- 
- use sedrila2.yaml, force titles to be in topmatter
- eventually: kick out author, rename author2 to author, changelog, adjust docs
"""
import argparse
import csv
import datetime as dt
import json
import os
import os.path
import typing as tg

import base as b
import cache
import sdrl.constants as c
import sdrl.course
import sdrl.elements as el
import sdrl.directory as dir
import sdrl.macroexpanders as macroexpanders
import sdrl.rename


meaning = """Creates and renders an instance of a SeDriLa course with incremental build.
Checks consistency of the course description.
"""


def add_arguments(subparser: argparse.ArgumentParser):
    subparser.add_argument('--config', metavar="configfile", default=c.AUTHOR_CONFIG_FILENAME,
                           help="SeDriLa configuration description YAML file")
    subparser.add_argument('--include_stage', metavar="stage", default='',
                           help="include parts with this and higher 'stage:' entries in the generated output "
                                "(default: only those with no stage)")
    subparser.add_argument('--log', default="INFO", choices=b.loglevels.keys(),
                           help="Log level for logging to stdout (default: INFO)")
    subparser.add_argument('--sums', action='store_const', const=True, default=False,
                           help="Print task volume reports")
    subparser.add_argument('--clean', action='store_const', const=True, default=False,
                           help="purge cache and perform a complete build")
    subparser.add_argument('--rename', nargs=2, metavar=("partname", "new_partname"),
                           help="Rename files of part, macro calls in *.md. and part mentions in *.prot, then stop.")
    subparser.add_argument('--validate-protocols', nargs='?', const='all', metavar="protocol_file",
                           help="Validate protocol check annotations in .prot files. Use without argument to check all course protocol files, or specify a single .prot file to check")
    subparser.add_argument('--validate-snippets', nargs='?', const='all', metavar="task_file",
                           help="Validate code snippet references and definitions. Use without argument to check all course files, or specify a single task file to check")
    subparser.add_argument('--test-programs', nargs='?', const='all', metavar="program_file",
                           help="Test exemplary programs from itree.zip against their .prot files. Use without argument to test all programs, or specify a single program file to test")
    subparser.add_argument('targetdir',
                           help=f"Directory to which output will be written.")


def execute(pargs: argparse.Namespace):
    b.set_loglevel(pargs.log)
    if pargs.rename:
        b.suppress_msg_duplicates(False)
        do_rename(pargs.config, pargs.rename[0], pargs.rename[1])
        return
    b.suppress_msg_duplicates(True)
    targetdir_s = pargs.targetdir
    targetdir_i = _targetdir_i(pargs.targetdir)
    prepare_directories(targetdir_s, targetdir_i)
    the_course = create_and_build_course(pargs, targetdir_i, targetdir_s)
    
    # Perform protocol annotation validation if requested
    if hasattr(pargs, 'validate_protocols') and pargs.validate_protocols is not None:
        b.info("=" * 60)
        if pargs.validate_protocols == 'all':
            # Validate all course protocol files
            b.info("Validating protocol annotations in all course files...")
            protocols_ok = the_course.validate_protocol_annotations(show_progress=True)
            if not protocols_ok:
                b.error("Protocol annotation validation failed - some annotations are invalid")
                # Note: We don't exit with error code here to allow the build to complete
                # Users can check the log output to see which annotations failed
        else:
            # Validate specific file
            validate_single_protocol_file(pargs.validate_protocols)
        b.info("=" * 60)
        if pargs.validate_protocols != 'all':
            return  # Exit early when validating single file, don't continue with normal build
    
    # Perform snippet validation if requested
    if hasattr(pargs, 'validate_snippets') and pargs.validate_snippets is not None:
        b.info("=" * 60)
        if pargs.validate_snippets == 'all':
            # Validate all course snippet references and definitions
            b.info("Validating code snippet references and definitions in all course files...")
            snippets_ok = the_course.validate_snippet_references(show_progress=True)
            if not snippets_ok:
                b.error("Snippet validation failed - some references or definitions are invalid")
                # Note: We don't exit with error code here to allow the build to complete
                # Users can check the log output to see which snippets failed
        else:
            # Validate specific file
            validate_single_task_snippets(pargs.validate_snippets)
        b.info("=" * 60)
        if pargs.validate_snippets != 'all':
            return  # Exit early when validating single file, don't continue with normal build
    
    # Perform program testing if requested
    if hasattr(pargs, 'test_programs') and pargs.test_programs is not None:
        b.info("=" * 60)
        if pargs.test_programs == 'all':
            # Test all programs in itree.zip
            b.info("Testing all exemplary programs from itree.zip...")
            programs_ok = the_course.test_exemplary_programs(show_progress=True)
            # Note: Error reporting is already done in test_exemplary_programs()
            # We don't exit with error code here to allow the build to complete
            # Users can check the log output to see which programs failed
        else:
            # Test specific program file
            test_single_program_file(pargs.test_programs)
        b.info("=" * 60)
        if pargs.test_programs != 'all':
            return  # Exit early when testing single file, don't continue with normal build
    
    b.finalmessage()


def validate_single_protocol_file(filepath: str):
    """Validate protocol annotations in a single protocol file for development/debugging."""
    try:
        import sdrl.protocolchecker as protocolchecker
    except ImportError as e:
        b.error(f"Cannot import protocol checking modules: {e}")
        return
    
    b.info(f"Validating protocol annotations in: {filepath}")
    
    validator = protocolchecker.ProtocolValidator()
    errors = validator.validate_file(filepath)
    
    if not errors:
        b.info("All protocol annotations are valid")
    else:
        b.error(f"Found {len(errors)} validation errors:")
        for error in errors:
            b.error(f"  {error}")


def validate_single_task_snippets(filepath: str):
    """Validate snippet references in a single task file for development/debugging."""
    try:
        import sdrl.snippetchecker as snippetchecker
    except ImportError as e:
        b.error(f"Cannot import snippet checking modules: {e}")
        return
    
    import os.path
    
    b.info(f"Validating snippet references in: {filepath}")
    
    if not os.path.exists(filepath):
        b.error(f"File not found: {filepath}")
        return
    
    # Use the directory containing the task file as base directory for resolving references
    base_directory = os.path.dirname(os.path.abspath(filepath))
    
    validator = snippetchecker.SnippetValidator()
    results = validator.validate_file_references(filepath, base_directory)
    
    if not results:
        b.info("No snippet references found in file")
        return
    
    # Generate report
    reporter = snippetchecker.SnippetReporter()
    reporter.print_summary(results)
    
    # Save detailed reports for single file testing
    reporter.generate_json_report(results)  # Uses default fixed name
    reporter.generate_markdown_report(results)  # Uses default fixed name
    
    # Return success status
    failed_results = [r for r in results if not r.success]
    return len(failed_results) == 0


def do_rename(configfile: str, old_partname: str, new_partname: str):
    config = b.slurp_yaml(configfile)
    chapterdir, altdir, itreedir = config['chapterdir'], config['altdir'], config['itreedir']
    sdrl.rename.rename_part(chapterdir, altdir, itreedir, old_partname, new_partname)
    
    
def create_and_build_course(pargs, targetdir_i, targetdir_s) -> sdrl.course.Coursebuilder:
    # ----- prepare build:
    the_cache = cache.SedrilaCache(os.path.join(targetdir_i, c.CACHE_FILENAME), start_clean=pargs.clean)
    b.set_register_files_callback(the_cache.set_file_dirty)
    directory = dir.Directory(the_cache)
    the_course = sdrl.course.Coursebuilder(
        configfile=pargs.config, context=pargs.config, include_stage=pargs.include_stage,
        targetdir_s=targetdir_s, targetdir_i=targetdir_i, directory=directory)
    # ----- perform main part of build:
    prepare_itree_zip(the_course)
    macroexpanders.register_macros(the_course)
    directory.build()
    # ----- build special files:
    b.spit(os.path.join(targetdir_s, c.METADATA_FILE), json.dumps(the_course.as_json(), indent=2))
    generate_htaccess(the_course)
    # ----- clean up and report:
    purge_leftover_outputfiles(directory, targetdir_s, targetdir_i)
    if pargs.sums:
        print_volume_report(the_course)
    the_cache.close()  # write back changes
    return the_course


def generate_htaccess(course: sdrl.course.Coursebuilder):
    if not course.htaccess_template:
        return  # nothing to do
    userlist = [u['webaccount'] for u in course.instructors]
    htaccess_txt = (course.htaccess_template.format(
                       userlist_commas=",".join(userlist),
                       userlist_spaces = " ".join(userlist),
                       userlist_quotes_spaces = " ".join((f'"{u}"' for u in userlist))))
    b.spit(os.path.join(course.targetdir_i, c.HTACCESS_FILE), htaccess_txt)


def prepare_directories(targetdir_s: str, targetdir_i: str):
    # ----- create from scratch if needed:
    if not os.path.exists(targetdir_s):
        os.mkdir(targetdir_s)
    # ----- check plausibility:
    not_empty = len(os.listdir(targetdir_s)) > 1  # targetdir_i will exist even in fresh ones 
    metadatafile = os.path.join(targetdir_s, c.METADATA_FILE)
    if not_empty and not os.path.exists(metadatafile):  # empty pre-existing dirs will fail, too
        b.critical(f"{targetdir_s} does not look like a build directory: {c.METADATA_FILE} is missing")
    # ----- add instructor dir if needed:
    if not os.path.exists(targetdir_i):
        os.mkdir(targetdir_i)


def prepare_itree_zip(the_course: sdrl.course.Coursebuilder):
    if not the_course.itreedir:
        return  # nothing to do
    if not the_course.itreedir.endswith(".zip"):
        b.critical(f"itreedir = '{the_course.itreedir}'; must end with '.zip'")
    the_course.directory.make_the(el.Zipdir, the_course.itreedir, parent=the_course)
    the_course.directory.make_the(el.Zipfile, os.path.basename(the_course.itreedir), parent=the_course, 
                                  sourcefile=the_course.itreedir, instructor_only=True)


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


def purge_leftover_outputfiles(directory: dir.Directory, targetdir_s: str, targetdir_i: str):
    def keep(outputfile: el.Outputfile) -> bool:
        # two cases: non-Parts, Parts
        return not isinstance(outputfile, el.Part) or not outputfile.to_be_skipped
    
    expected_files = set([of.outputfile for of in directory.get_all_outputfiles() if keep(of)])
    additions_s = {c.AUTHOR_OUTPUT_INSTRUCTORS_DEFAULT_SUBDIR, c.METADATA_FILE}
    additions_i = {c.HTACCESS_FILE}
    purge_all_but(targetdir_s, expected_files | additions_s)
    purge_all_but(targetdir_i, expected_files | additions_i, exception=c.CACHE_FILENAME)


def test_single_program_file(filepath: str):
    """Test a single program file for development/debugging."""
    try:
        import sdrl.programchecker as programchecker
    except ImportError as e:
        b.error(f"Program checker module not available: {e}")
        return
    
    programchecker.test_single_program_file(filepath)


def purge_all_but(dir: str, files: set[str], exception: tg.Optional[str] = None):
    """Delete all files in dir that are not mentioned in files and are no exceptions."""
    actual_files = set(os.listdir(dir))
    delete_these = actual_files - files
    for file in sorted(delete_these):
        if exception and file.startswith(exception):
            continue  # avoid deleting any kind of cache file
        path = os.path.join(dir, file)
        b.info(f"deleted: {path}")
        os.remove(path)


def _targetdir_i(targetdir_s):
    return os.path.join(targetdir_s, c.AUTHOR_OUTPUT_INSTRUCTORS_DEFAULT_SUBDIR)
