"""
Maintainer subcommand for SeDriLa courses.

The maintainer role is for people who maintain course quality.
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import base as b
import cache
import sdrl.constants as c
import sdrl.course
import sdrl.directory as dir
import sdrl.elements


meaning = """Maintain course quality with checks that are not suitable at build time.
Checks links, tests programs.
"""


def add_arguments(subparser: argparse.ArgumentParser):
    subparser.add_argument('--config', metavar="configfile", default=c.AUTHOR_CONFIG_FILENAME,
                           help="SeDriLa configuration description YAML file")
    subparser.add_argument('--log', default="INFO", choices=b.loglevels.keys(),
                           help="Log level for logging to stdout (default: INFO)")
    subparser.add_argument('--include-stage', metavar="stage", default='draft',
                           help="include parts with this and higher 'stage:' entries in the checking "
                                "(default: 'draft' which includes all stages)")
    subparser.add_argument('--check-links', nargs='?', const='all', metavar="markdown_file",
                           help="Check accessibility of external links. Use without argument to check all course files, or specify a single markdown file to check")
    subparser.add_argument('--check-programs', action='store_true',
                           help="Test exemplary programs against protocol files")
    subparser.add_argument('--collect', action='store_true',
                           help="Collect languages and dependencies from @TEST_SPEC blocks, output as JSON")
    subparser.add_argument('-o', '--output', metavar="json_file",
                           help="Output file for --collect (if not specified, writes to stdout)")
    subparser.add_argument('--batch', action='store_true',
                           help="Use batch/CI-friendly output: concise output, only show failures, complete error list at end")
    subparser.add_argument('targetdir', nargs='?',
                           help="Directory for maintenance reports (optional for --collect)")


def execute(pargs: argparse.Namespace):
    b.set_loglevel(pargs.log)
    if hasattr(pargs, 'collect') and pargs.collect:
        collect_command(pargs)
        return
    if hasattr(pargs, 'check_links') and pargs.check_links is not None:
        check_links_command(pargs)
        return
    if hasattr(pargs, 'check_programs') and pargs.check_programs:
        check_programs_command(pargs)
        return
    b.error("No maintenance command specified. Use --check-links, --check-programs, or --collect, or see --help for options.")


def _build_metadata_only(directory: dir.Directory):
    """Build only the elements needed for metadata and stage evaluation."""
    import sdrl.elements as el
    import sdrl.course
    # Build in dependency order (same as directory.managed_types)
    build_types = [
        el.Sourcefile,      # Register source files
        el.Topmatter,       # Parse YAML topmatter
        sdrl.course.MetadataDerivation,  # Process metadata and evaluate stages
    ]
    for element_type in build_types:
        b.debug(f"Building all Elements of type {element_type.__name__}")
        for elem in directory.get_all(element_type):
            elem.build()


def check_links_command(pargs: argparse.Namespace):
    """Execute link checking using build system for file identification."""
    import sdrl.linkchecker as linkchecker
    if pargs.check_links == 'all':
        b.info("Checking links in all course files...")
        targetdir_s = pargs.targetdir
        targetdir_i = targetdir_s + "_i"
        os.makedirs(targetdir_s, exist_ok=True)
        os.makedirs(targetdir_i, exist_ok=True)
        try:
            the_cache = cache.SedrilaCache(os.path.join(targetdir_i, c.CACHE_FILENAME), start_clean=False)
            b.set_register_files_callback(the_cache.set_file_dirty)
            directory = dir.Directory(the_cache)
            the_course = sdrl.course.Coursebuilder(
                configfile=pargs.config, 
                context=pargs.config, 
                include_stage=pargs.include_stage,
                targetdir_s=targetdir_s,
                targetdir_i=targetdir_i,
                directory=directory
            )
            # This builds: Sourcefile, Topmatter, and MetadataDerivation
            # MetadataDerivation.do_build() handles topmatter processing and stage evaluation
            _build_metadata_only(directory)
            markdown_files = find_markdown_files(the_course)
            b.info(f"Found {len(markdown_files)} markdown files to check")
            extractor = linkchecker.LinkExtractor()
            all_links = []
            for filepath in markdown_files:
                links = extractor.extract_links_from_file(filepath)
                all_links.extend(links)
            if not all_links:
                b.info("No external links found to check.")
                the_cache.close()
                b.info("=" * 60)
                return
            # Check all links
            checker = linkchecker.LinkChecker()
            batch_mode = getattr(pargs, 'batch', False)
            results = checker.check_links(all_links, show_progress=True, batch_mode=batch_mode)
            reporter = linkchecker.LinkCheckReporter()
            if results:
                try:
                    md_content = reporter.render_markdown_report(results, max_workers=checker.max_workers)
                    md_report = directory.make_the(
                        sdrl.elements.ReportFile,
                        "link_check_report.md",
                        content=md_content,
                        markdown_files=markdown_files,
                        targetdir_s=targetdir_s,
                        targetdir_i=targetdir_i
                    )
                    md_report.do_build()
                    b.info("Report generated as build product:")
                    b.info(f"  Markdown: {md_report.outputfile_i}")
                except (OSError, RuntimeError, ValueError) as e:
                    b.error(f"Failed to generate report files: {e}")
                    import traceback
                    traceback.print_exc()
            # Close cache and clean up
            the_cache.close()
        except (FileNotFoundError, OSError, ValueError, RuntimeError) as e:
            b.error(f"Failed to initialize course structure: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
        failed_count = sum(1 for r in results if not r.success)
        if failed_count > 0:
            sys.exit(1)
    else:
        # Check specific file
        results = linkchecker.check_single_file(pargs.check_links)
        if results:
            failed_count = sum(1 for r in results if not r.success)
            if failed_count > 0:
                sys.exit(1)


def extract_markdown_files_from_course(course: sdrl.course.Coursebuilder) -> list[str]:
    """
    Extract markdown file paths from course structure.
    Respects stages filtering and only includes configured taskgroups.
    """
    files = []
    for chapter in course.chapters:
        if chapter.to_be_skipped:
            b.debug(f"Skipping chapter {chapter.name} (filtered by stage)")
            continue
        for taskgroup in chapter.taskgroups:
            if taskgroup.to_be_skipped:
                b.debug(f"Skipping taskgroup {taskgroup.name} (filtered by stage)")
                continue
            if os.path.exists(taskgroup.sourcefile):
                files.append(taskgroup.sourcefile)
            for task in taskgroup.tasks:
                if not task.to_be_skipped:
                    if os.path.exists(task.sourcefile):
                        files.append(task.sourcefile)
    return files


def find_markdown_files(course: sdrl.course.Coursebuilder) -> list[str]:
    """Return markdown files from both chapter and alternative directories."""
    files = extract_markdown_files_from_course(course)
    if course.altdir and os.path.isdir(course.altdir):
        return add_altdir_files(files, course.chapterdir, course.altdir)
    return files


def add_altdir_files(files: list[str], chapterdir: str, altdir: str) -> list[str]:
    """
    Add altdir files using simple path replacement.
    For each file in chapterdir, check if corresponding file exists in altdir.
    """
    result = list(files)
    for filepath in files:
        # Simple path prefix replacement
        alt_filepath = filepath.replace(chapterdir, altdir, 1)
        if os.path.exists(alt_filepath) and alt_filepath not in result:
            result.append(alt_filepath)
            b.debug(f"Found altdir file: {alt_filepath}")
    return result


def check_programs_command(pargs: argparse.Namespace):
    """Execute program testing (lightweight, no course build)."""
    import sdrl.programchecker as programchecker
    b.info("Testing exemplary programs...")
    targetdir_s = pargs.targetdir
    targetdir_i = targetdir_s + "_i"
    batch_mode = getattr(pargs, 'batch', False)
    os.makedirs(targetdir_s, exist_ok=True)
    os.makedirs(targetdir_i, exist_ok=True)
    temp_report_dir = tempfile.mkdtemp(prefix='sedrila_progtest_')
    try:
        the_cache = cache.SedrilaCache(os.path.join(targetdir_i, c.CACHE_FILENAME), start_clean=False)
        b.set_register_files_callback(the_cache.set_file_dirty)
        directory = dir.Directory(the_cache)
        the_course = sdrl.course.Coursebuilder(
            configfile=pargs.config,
            context=pargs.config,
            include_stage=pargs.include_stage,
            targetdir_s=targetdir_s,
            targetdir_i=targetdir_i,
            directory=directory
        )
        _build_metadata_only(directory)
        targets = programchecker.extract_program_test_targets(the_course)
        checker = programchecker.ProgramChecker(
            report_dir=temp_report_dir,
            course=the_course
        )
        show_progress = not batch_mode
        results = checker.test_all_programs(
            targets=targets,
            show_progress=show_progress,
            batch_mode=batch_mode
        )
        try:
            checker.generate_reports(results, batch_mode=batch_mode)
            md_temp_path = os.path.join(temp_report_dir, "program_test_report.md")
            with open(md_temp_path, 'r', encoding='utf-8') as f:
                md_content = f.read()
            md_report = directory.make_the(
                sdrl.elements.ReportFile,
                "program_test_report.md",
                content=md_content,
                markdown_files=None,
                targetdir_s=targetdir_s,
                targetdir_i=targetdir_i
            )
            md_report.do_build()
            b.info("Report generated as build product:")
            b.info(f"  Markdown: {md_report.outputfile_i}")
        except (OSError, RuntimeError, ValueError) as e:
            b.error(f"Failed to generate report files: {e}")
            import traceback
            traceback.print_exc()
        the_cache.close()
    finally:
        if os.path.exists(temp_report_dir):
            shutil.rmtree(temp_report_dir)
    failed_count = sum(1 for r in results if not r.success and not r.skipped)
    if failed_count > 0:
        sys.exit(1)


def collect_command(pargs: argparse.Namespace):
    """Collect languages, dependencies, and task assumes from @TEST_SPEC blocks."""
    import sdrl.programchecker as programchecker
    # Use temporary directory for cache
    temp_cache_dir = tempfile.mkdtemp(prefix='sedrila_collect_')
    try:
        the_cache = cache.SedrilaCache(os.path.join(temp_cache_dir, c.CACHE_FILENAME), start_clean=False)
        b.set_register_files_callback(the_cache.set_file_dirty)
        directory = dir.Directory(the_cache)
        the_course = sdrl.course.Coursebuilder(
            configfile=pargs.config,
            context=pargs.config,
            include_stage=pargs.include_stage,
            targetdir_s=temp_cache_dir,
            targetdir_i=temp_cache_dir,
            directory=directory
        )
        _build_metadata_only(directory)
        targets = programchecker.extract_program_test_targets(the_course)
        checker = programchecker.ProgramChecker(course=the_course)
        deps_by_task = checker.collect_deps_by_task(targets)
        # Collect all unique lang commands
        all_lang_commands = set()
        for target in targets:
            header = target.program_check_header
            commands = header.get_lang_install_commands()
            all_lang_commands.update(commands)
        # Build simple task list
        tasks = {}
        for target in targets:
            task_name = target.protocol_file.stem
            task_obj = the_course.task(task_name)
            assumes = task_obj.assumes if task_obj else []
            tasks[task_name] = {
                "deps": deps_by_task.get(task_name, []),
                "assumes": assumes,
                "protocol": str(target.protocol_file)
            }
        result = {
            "lang": sorted(list(all_lang_commands)),
            "tasks": tasks
        }
        # Output to file or stdout
        output_json = json.dumps(result, indent=2, sort_keys=True)
        if hasattr(pargs, 'output') and pargs.output:
            with open(pargs.output, 'w') as f:
                f.write(output_json)
            b.info(f"Metadata collected and written to {pargs.output}")
        else:
            print(output_json)
        the_cache.close()
    except (FileNotFoundError, OSError, ValueError, RuntimeError) as e:
        b.error(f"Failed to collect metadata: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Clean up temporary directory
        if os.path.exists(temp_cache_dir):
            shutil.rmtree(temp_cache_dir)
