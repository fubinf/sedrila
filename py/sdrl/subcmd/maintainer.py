"""
Maintainer subcommand for SeDriLa courses.

This module provides lightweight maintenance tasks that don't require 
building the entire course. 

The maintainer role is for people who maintain course quality without
necessarily developing new tasks.
"""
import argparse
import os
from pathlib import Path
import typing as tg

import base as b
import sdrl.constants as c


meaning = """Maintain course quality with lightweight checks (no course build required).
Checks links, validates protocols, tests programs, etc.
"""


def add_arguments(subparser: argparse.ArgumentParser):
    subparser.add_argument('--config', metavar="configfile", default=c.AUTHOR_CONFIG_FILENAME,
                           help="SeDriLa configuration description YAML file")
    subparser.add_argument('--log', default="INFO", choices=b.loglevels.keys(),
                           help="Log level for logging to stdout (default: INFO)")
    subparser.add_argument('--check-links', nargs='?', const='all', metavar="markdown_file",
                           help="Check accessibility of external links. Use without argument to check all course files, or specify a single markdown file to check")


def execute(pargs: argparse.Namespace):
    b.set_loglevel(pargs.log)
    
    # Check links if requested
    if hasattr(pargs, 'check_links') and pargs.check_links is not None:
        check_links_command(pargs)
        return
    
    # If no specific command was given, show help
    b.error("No maintenance command specified. Use --check-links or see --help for options.")


def check_links_command(pargs: argparse.Namespace):
    """Execute link checking (lightweight, no course build)."""
    try:
        import sdrl.linkchecker as linkchecker
    except ImportError as e:
        b.error(f"Cannot import link checking modules: {e}")
        return
    
    b.info("=" * 60)
    
    if pargs.check_links == 'all':
        # Check all course files
        b.info("Checking links in all course files...")
        
        # Parse course structure (lightweight, no build)
        course_info = parse_course_structure(pargs.config)
        
        # Find all markdown files
        markdown_files = find_markdown_files(
            course_info['chapterdir'], 
            course_info['chapters']
        )
        
        b.info(f"Found {len(markdown_files)} markdown files to check")
        
        # Extract links from all files
        extractor = linkchecker.LinkExtractor()
        all_links = []
        
        for filepath in markdown_files:
            links = extractor.extract_links_from_file(filepath)
            all_links.extend(links)
        
        if not all_links:
            b.info("No external links found to check.")
            b.info("=" * 60)
            return
        
        # Check all links
        checker = linkchecker.LinkChecker()
        results = checker.check_links(all_links, show_progress=True)
        
        # Generate and display report
        reporter = linkchecker.LinkCheckReporter()
        reporter.print_summary(results)
        
        # Save detailed reports with fixed names
        if results:
            reporter.generate_json_report(results)
            reporter.generate_markdown_report(results)
        
    else:
        # Check specific file
        check_single_file(pargs.check_links)
    
    b.info("=" * 60)


def parse_course_structure(configfile: str) -> dict:
    """
    Lightweight parse of course structure from sedrila.yaml.
    Does NOT build the course - only extracts directory paths.
    
    Returns:
        dict with 'chapterdir' and 'chapters' keys
    """
    if not os.path.exists(configfile):
        b.error(f"Configuration file not found: {configfile}")
        return {'chapterdir': 'ch', 'chapters': []}
    
    config = b.slurp_yaml(configfile)
    chapterdir = config.get('chapterdir', 'ch')
    chapters = config.get('chapters', [])
    
    b.debug(f"Parsed config: chapterdir={chapterdir}, {len(chapters)} chapters")
    
    return {
        'chapterdir': chapterdir,
        'chapters': chapters
    }


def find_markdown_files(chapterdir: str, chapters: list) -> list[str]:
    """
    Scan filesystem for all task markdown files based on sedrila.yaml structure.
    Does NOT build the course - only walks the directory tree.
    
    Args:
        chapterdir: Base directory for chapters (e.g., 'ch')
        chapters: List of chapter dictionaries from sedrila.yaml
    
    Returns:
        List of markdown file paths (absolute paths as strings)
    """
    files = []
    chapterdir_path = Path(chapterdir)
    
    if not chapterdir_path.exists():
        b.error(f"Chapter directory not found: {chapterdir}")
        return files
    
    for chapter in chapters:
        chapter_name = chapter.get('name')
        if not chapter_name:
            continue
        
        chapter_path = chapterdir_path / chapter_name
        if not chapter_path.exists():
            b.warning(f"Chapter directory not found: {chapter_path}")
            continue
        
        taskgroups = chapter.get('taskgroups', [])
        for taskgroup in taskgroups:
            taskgroup_name = taskgroup.get('name') if isinstance(taskgroup, dict) else taskgroup
            if not taskgroup_name:
                continue
            
            tg_path = chapter_path / taskgroup_name
            if not tg_path.exists():
                b.warning(f"Taskgroup directory not found: {tg_path}")
                continue
            
            # Find all .md files except index.md
            for md_file in tg_path.glob('*.md'):
                if md_file.name != 'index.md':
                    files.append(str(md_file.absolute()))
    
    return files


def check_single_file(filepath: str):
    """Check links in a single markdown file."""
    import sdrl.linkchecker as linkchecker
    
    if not os.path.exists(filepath):
        b.error(f"File not found: {filepath}")
        return
    
    b.info(f"Checking links in file: {filepath}")
    b.info("=" * 60)
    
    # Extract links
    extractor = linkchecker.LinkExtractor()
    links = extractor.extract_links_from_file(filepath)
    
    if not links:
        b.info("No external links found in file.")
        return
    
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
            if link.validation_rule.ignore_ssl:
                rule_parts.append("ignore_ssl=true")
            if rule_parts:
                rule_info = f" [CUSTOM: {', '.join(rule_parts)}]"
        
        b.info(f"  {i}. {link.url}{rule_info}")
    
    b.info("")
    b.info("Checking links...")
    
    # Check links
    checker = linkchecker.LinkChecker()
    results = checker.check_links(links, show_progress=True)
    
    # Generate and display report
    reporter = linkchecker.LinkCheckReporter()
    reporter.print_summary(results)
    
    # Save detailed reports
    if results:
        reporter.generate_json_report(results)
        reporter.generate_markdown_report(results)

