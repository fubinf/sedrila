"""
Maintainer subcommand for SeDriLa courses.

The maintainer role is for people who maintain course quality without
necessarily developing new tasks.
"""
import argparse
import os
import sys
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
    subparser.add_argument('--check-programs', nargs='?', const='all', metavar="program_file",
                           help="Test exemplary programs against protocol files. Use without argument to test all programs, or specify a single program file to test")
    subparser.add_argument('--batch', action='store_true',
                           help="Use batch/CI-friendly output: concise output, only show failures, complete error list at end")
    subparser.add_argument('targetdir',
                           help="Directory for maintenance reports")


def execute(pargs: argparse.Namespace):
    b.set_loglevel(pargs.log)
    
    # Check links if requested
    if hasattr(pargs, 'check_links') and pargs.check_links is not None:
        check_links_command(pargs)
        return
    
    # Check programs if requested
    if hasattr(pargs, 'check_programs') and pargs.check_programs is not None:
        check_programs_command(pargs)
        return
    
    # If no specific command was given, show help
    b.error("No maintenance command specified. Use --check-links, --check-programs, or see --help for options.")


def _build_metadata_only(directory: dir.Directory):
    """
    Build only the elements needed for metadata and stage evaluation.
    This follows the DRY principle by reusing the build system.
    
    Builds: Sourcefile, Topmatter, MetadataDerivation
    This ensures that:
    - All source files are registered
    - YAML topmatter is parsed
    - Metadata is copied into Parts (via process_topmatter)
    - Stage filtering is evaluated (via evaluate_stage)
    """
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
    try:
        import sdrl.linkchecker as linkchecker
    except ImportError as e:
        b.error(f"Cannot import link checking modules: {e}")
        return
    
    if pargs.check_links == 'all':
        # Check all course files using build system
        b.info("Checking links in all course files...")
        
        # Auto-derive targetdir_s and targetdir_i from user input
        targetdir_s = pargs.targetdir
        targetdir_i = targetdir_s + "_i"
        
        # Prepare directories
        os.makedirs(targetdir_s, exist_ok=True)
        os.makedirs(targetdir_i, exist_ok=True)
        
        try:
            # Create course builder to leverage existing file identification logic
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
            
            # Build only the elements needed for file identification (DRY principle)
            # This builds: Sourcefile, Topmatter, and MetadataDerivation
            # MetadataDerivation.do_build() handles topmatter processing and stage evaluation
            _build_metadata_only(directory)
            
            # Extract markdown files from course structure (respects stages and taskgroups)
            markdown_files = find_markdown_files(the_course)
            
            b.info(f"Found {len(markdown_files)} markdown files to check")
            
            # Extract links from all files
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
                    md_content = reporter.render_markdown_report(results)
                    
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
                    
                except Exception as e:
                    b.error(f"Failed to generate report files: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Close cache and clean up
            the_cache.close()
            
        except Exception as e:
            b.error(f"Failed to initialize course structure: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
        
        # Check for failures and exit with appropriate status
        failed_count = sum(1 for r in results if not r.success)
        if failed_count > 0:
            sys.exit(1)
        
    else:
        # Check specific file (no build system needed)
        results = check_single_file(pargs.check_links)
        
        # Check for failures and exit with appropriate status
        if results:
            failed_count = sum(1 for r in results if not r.success)
            if failed_count > 0:
                sys.exit(1)


def extract_markdown_files_from_course(course: sdrl.course.Coursebuilder) -> list[str]:
    """
    Extract markdown file paths from course structure.
    Respects stages filtering and only includes configured taskgroups.
    
    Args:
        course: Coursebuilder object with parsed course structure
    
    Returns:
        List of markdown file paths from taskgroups (includes index.md and task .md files)
    """
    files = []
    
    for chapter in course.chapters:
        # Skip chapters filtered by stages
        if chapter.to_be_skipped:
            b.debug(f"Skipping chapter {chapter.name} (filtered by stage)")
            continue
            
        for taskgroup in chapter.taskgroups:
            # Skip taskgroups filtered by stages
            if taskgroup.to_be_skipped:
                b.debug(f"Skipping taskgroup {taskgroup.name} (filtered by stage)")
                continue
            
            # Add taskgroup index.md
            if os.path.exists(taskgroup.sourcefile):
                files.append(taskgroup.sourcefile)
            
            # Add all task .md files
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
    
    Args:
        files: List of file paths from chapterdir
        chapterdir: Base directory for chapters (e.g., 'ch')
        altdir: Alternative directory (e.g., 'alt')
    
    Returns:
        List with both chapterdir and altdir files
    """
    result = list(files)  # Start with original files
    
    for filepath in files:
        # Simple path prefix replacement
        alt_filepath = filepath.replace(chapterdir, altdir, 1)
        
        # Only add if altdir file actually exists
        if os.path.exists(alt_filepath) and alt_filepath not in result:
            result.append(alt_filepath)
            b.debug(f"Found altdir file: {alt_filepath}")
    
    return result


def check_single_file(filepath: str):
    """Check links in a single markdown file.
    
    Returns:
        list[LinkCheckResult]: List of check results, or None if file not found/no links
    """
    import sdrl.linkchecker as linkchecker
    
    if not os.path.exists(filepath):
        b.error(f"File not found: {filepath}")
        return None
    
    b.info(f"Checking links in file: {filepath}")
    
    # Extract links
    extractor = linkchecker.LinkExtractor()
    links = extractor.extract_links_from_file(filepath)
    
    if not links:
        b.info("No external links found in file.")
        return None
    
    b.info(f"Found {len(links)} external links:")
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
            if link.validation_rule.ignore_cert:
                rule_parts.append("ignore_cert=true")
            if rule_parts:
                rule_info = f" [CUSTOM: {', '.join(rule_parts)}]"
        
        b.info(f"  {i}. {link.url}{rule_info}")
    
    b.info("")
    b.info("Checking links...")
    
    # Check links
    checker = linkchecker.LinkChecker()
    results = checker.check_links(links, show_progress=True)
    
    # Display Markdown summary (no report files for single file testing)
    if results:
        reporter = linkchecker.LinkCheckReporter()
        markdown_report = reporter.render_markdown_report(results)
        print(markdown_report)
    
    return results


def check_programs_command(pargs: argparse.Namespace):
    """Execute program testing (lightweight, no course build)."""
    try:
        import sdrl.programchecker as programchecker
    except ImportError as e:
        b.error(f"Cannot import program checking modules: {e}")
        return
    
    if pargs.check_programs == 'all':
        # Test all programs
        b.info("Testing exemplary programs...")
        
        # Auto-derive targetdir_s and targetdir_i from user input
        targetdir_s = pargs.targetdir
        targetdir_i = targetdir_s + "_i"
        batch_mode = getattr(pargs, 'batch', False)
        
        # Ensure targetdir exists
        os.makedirs(targetdir_s, exist_ok=True)
        os.makedirs(targetdir_i, exist_ok=True)
        
        # Create a temporary directory for intermediate report generation
        import tempfile
        import shutil
        temp_report_dir = tempfile.mkdtemp(prefix='sedrila_progtest_')
        
        try:
            # Initialize cache and directory for build system
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
            
            # Initialize checker (uses annotation-based configuration from task .md files)
            checker = programchecker.ProgramChecker(
                parallel_execution=True,
                report_dir=temp_report_dir  # Write to temp dir first
            )
            
            # Run tests with appropriate verbosity
            show_progress = not batch_mode  # Less verbose in batch mode
            results = checker.test_all_programs(
                targets=targets,
                show_progress=show_progress,
                batch_mode=batch_mode
            )
            
            # Generate reports to temp directory
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
                
            except Exception as e:
                b.error(f"Failed to generate report files: {e}")
                import traceback
                traceback.print_exc()
            
            # Close cache
            the_cache.close()
            
        finally:
            # Clean up temporary directory
            if os.path.exists(temp_report_dir):
                shutil.rmtree(temp_report_dir)
        
        # Check for failures and exit with appropriate status
        failed_count = sum(1 for r in results if not r.success and not r.skipped)
        if failed_count > 0:
            sys.exit(1)
    else:
        # Test single program file
        programchecker.test_single_program_file(pargs.check_programs)
