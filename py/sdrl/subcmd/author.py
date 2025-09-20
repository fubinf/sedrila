"""
Generate the website with incremental build.
See the architecture sketch in docs/internal_notes.md.
TODO:
- 
- use sedrila2.yaml, force titles to be in topmatter
- eventually: kick out author, rename author2 to author, changelog, adjust docs
"""
import argparse
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
    subparser.add_argument('--check-links', action='store_true',
                           help="Check accessibility of external links in markdown files")
    subparser.add_argument('--link-statistics', action='store_true',
                           help="Generate detailed statistics about external links without checking them")
    subparser.add_argument('--check-link', nargs='?', const='', metavar="markdown_file",
                           help="Check links in a specific markdown file, or all ProPra files if no file specified")
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
    
    # Perform external link checking if requested
    if hasattr(pargs, 'check_links') and pargs.check_links:
        b.info("=" * 60)
        links_ok = the_course.check_external_links(show_progress=True)
        if not links_ok:
            b.error("External link validation failed - some links are broken")
            # Note: We don't exit with error code here to allow the build to complete
            # Users can check the log output to see which links failed
        b.info("=" * 60)
    
    # Generate link statistics if requested (without actual checking)
    if hasattr(pargs, 'link_statistics') and pargs.link_statistics:
        b.info("=" * 60)
        the_course.generate_link_statistics()
        b.info("=" * 60)
    
    # Check links in specific file or all ProPra files if requested
    if hasattr(pargs, 'check_link') and pargs.check_link is not None:
        if pargs.check_link:  # Specific file provided
            test_single_markdown_file(pargs.check_link)
        else:  # No file specified, check all ProPra files
            b.info("=" * 60)
            b.info("Checking links in all ProPra course files...")
            links_ok = the_course.check_external_links(show_progress=True)
            if not links_ok:
                b.error("External link validation failed - some links are broken")
            b.info("=" * 60)
        return  # Exit early, don't continue with normal build
    
    b.finalmessage()


def test_single_markdown_file(filepath: str):
    """Test links in a single markdown file for development/debugging."""
    import os
    from sdrl.quality.link_checker import LinkExtractor, LinkChecker, LinkCheckReporter
    
    if not os.path.exists(filepath):
        b.error(f"File not found: {filepath}")
        return
    
    b.info(f"Testing file: {filepath}")
    b.info("=" * 60)
    
    # Extract links
    extractor = LinkExtractor()
    links = extractor.extract_links_from_file(filepath)
    
    b.info(f"Found {len(links)} links:")
    for i, link in enumerate(links, 1):
        rule_info = ""
        if link.validation_rule:
            rule_parts = []
            if link.validation_rule.expected_status:
                rule_parts.append(f"status={link.validation_rule.expected_status}")
            if link.validation_rule.required_text:
                rule_parts.append(f"content='{link.validation_rule.required_text}'")
            if link.validation_rule.timeout:
                rule_parts.append(f"timeout={link.validation_rule.timeout}")
            if link.validation_rule.ignore_ssl:
                rule_parts.append("ignore_ssl=true")
            if rule_parts:
                rule_info = f" [CUSTOM: {', '.join(rule_parts)}]"
        
        b.info(f"  {i}. {link.url} ({link.link_type}){rule_info}")
    
    if not links:
        b.info("No external links found to test.")
        return
    
    b.info("\n" + "=" * 60)
    b.info("Starting link validation...")
    b.info("=" * 60)
    
    # Check links
    checker = LinkChecker()
    results = checker.check_links(links, show_progress=True)
    
    # Generate report
    reporter = LinkCheckReporter()
    reporter.print_summary(results)
    
    # Save detailed reports for single file testing
    import os
    from datetime import datetime
    
    # Get filename without path and extension for report naming
    filename = os.path.splitext(os.path.basename(filepath))[0]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save JSON report
    json_filename = f"single_file_link_check_{filename}_{timestamp}.json"
    reporter.generate_json_report(results, json_filename)
    b.info(f"JSON report saved: {json_filename}")
    
    # Save Markdown report
    md_filename = f"single_file_link_check_{filename}_{timestamp}.md"
    reporter.generate_markdown_report(results, md_filename)
    b.info(f"Markdown report saved: {md_filename}")
    
    # Return success status
    failed_results = LinkCheckReporter.get_failed_links(results)
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
