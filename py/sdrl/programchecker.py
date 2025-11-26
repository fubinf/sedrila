"""
Program testing functionality for SeDriLa courses.

This module provides functionality to test exemplary programs from itree.zip
against their corresponding protocol files to ensure programs can run
successfully and produce expected output.
"""

import subprocess as sp
import os
import time
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
import shutil
import re

import base as b
import sdrl.course

PROGRAM_FILE_EXCLUDE_SUFFIXES = {
    '.md', '.markdown', '.yaml', '.yml', '.txt', '.json', '.prot',
    '.cfg', '.conf', '.ini', '.xml', '.html'
}
_ITREE_EXTRACTION_CACHE: dict[str, tuple[Path, float]] = {}

@dataclass
class ProgramTestAnnotation:
    """Program test markup from task .md file."""
    skip: bool = False
    skip_reason: str = ""
    manual_test_required: bool = False
    partial_skip: bool = False
    skip_commands_with: List[str] = field(default_factory=list)
    partial_skip_reason: str = ""
    testable_note: str = ""
    command_override: bool = False
    original_command: str = ""
    correct_command: str = ""
    override_reason: str = ""
    notes: str = ""
    has_markup: bool = False

class AnnotationExtractor:
    """Extracts program test markup from task .md files."""
    
    # Regex patterns for different markup types
    PROGRAM_TEST_SKIP_RE = re.compile(
        r'<!--\s*@PROGRAM_TEST_SKIP:\s*(.+?)\s*-->', re.DOTALL
    )
    PROGRAM_TEST_PARTIAL_RE = re.compile(
        r'<!--\s*@PROGRAM_TEST_PARTIAL:\s*(.+?)\s*-->', re.DOTALL
    )
    PROGRAM_TEST_OVERRIDE_RE = re.compile(
        r'<!--\s*@PROGRAM_TEST_OVERRIDE:\s*(.+?)\s*-->', re.DOTALL
    )
    PROGRAM_TEST_RE = re.compile(
        r'<!--\s*@PROGRAM_TEST(?::\s*(.+?))?\s*-->', re.DOTALL
    )
    
    def extract_annotations_from_file(self, md_filepath: str, content: Optional[str] = None) -> ProgramTestAnnotation:
        """Extract program test markup from a task .md file."""
        if not os.path.exists(md_filepath):
            b.debug(f"Task file not found: {md_filepath}")
            return ProgramTestAnnotation()
        
        try:
            if content is None:
                with open(md_filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
        except Exception as e:
            b.warning(f"Cannot read task file {md_filepath}: {e}")
            return ProgramTestAnnotation()
        
        annotation = ProgramTestAnnotation()
        
        # Check for SKIP annotation
        skip_match = self.PROGRAM_TEST_SKIP_RE.search(content)
        if skip_match:
            annotation.skip = True
            annotation.has_markup = True
            self._parse_skip_params(skip_match.group(1), annotation)
        
        # Check for PARTIAL annotation
        partial_match = self.PROGRAM_TEST_PARTIAL_RE.search(content)
        if partial_match:
            annotation.partial_skip = True
            annotation.has_markup = True
            self._parse_partial_params(partial_match.group(1), annotation)
        
        # Check for OVERRIDE annotation
        override_match = self.PROGRAM_TEST_OVERRIDE_RE.search(content)
        if override_match:
            annotation.command_override = True
            annotation.has_markup = True
            self._parse_override_params(override_match.group(1), annotation)
        
        # Check for general PROGRAM_TEST annotation
        test_match = self.PROGRAM_TEST_RE.search(content)
        if test_match:
            annotation.has_markup = True
            params_text = test_match.group(1)
            if params_text:
                self._parse_test_params(params_text, annotation)

        return annotation
    
    def _parse_skip_params(self, params_text: str, annotation: ProgramTestAnnotation):
        """Parse parameters from @PROGRAM_TEST_SKIP markup."""
        params = self._parse_key_value_pairs(params_text)
        annotation.skip_reason = params.get('reason', '')
        annotation.manual_test_required = params.get('manual_test_required', '').lower() in ('true', '1', 'yes')
    
    def _parse_partial_params(self, params_text: str, annotation: ProgramTestAnnotation):
        """Parse parameters from @PROGRAM_TEST_PARTIAL markup."""
        params = self._parse_key_value_pairs(params_text)
        skip_commands = params.get('skip_commands_with', '')
        if skip_commands:
            annotation.skip_commands_with = [cmd.strip() for cmd in skip_commands.split(',')]
        annotation.partial_skip_reason = params.get('skip_reason', '')
        annotation.testable_note = params.get('testable_note', '')
    
    def _parse_override_params(self, params_text: str, annotation: ProgramTestAnnotation):
        """Parse parameters from @PROGRAM_TEST_OVERRIDE markup."""
        params = self._parse_key_value_pairs(params_text)
        annotation.original_command = params.get('original_command', '')
        annotation.correct_command = params.get('correct_command', '')
        annotation.override_reason = params.get('reason', '')
    
    def _parse_test_params(self, params_text: str, annotation: ProgramTestAnnotation):
        """Parse parameters from @PROGRAM_TEST markup."""
        params = self._parse_key_value_pairs(params_text)
        annotation.notes = params.get('notes', '')
    
    def _parse_key_value_pairs(self, text: str) -> Dict[str, str]:
        """Parse key="value" pairs from markup parameters."""
        params = {}
        # Match key="value" or key='value' patterns
        pattern = r'(\w+)\s*=\s*["\']([^"\']*)["\']'
        for match in re.finditer(pattern, text):
            key = match.group(1)
            value = match.group(2)
            params[key] = value
        return params


@dataclass
class CommandTest:
    """Single command test extracted from .prot file"""
    command: str                    # The command to run
    expected_output: str           # Expected output for this command
    has_errors: bool = False       # True if output contains Traceback/errors
    needs_interaction: bool = False # True if command needs user input
    has_redirection: bool = False  # True if command has >/< redirection

@dataclass
class ProgramTestConfig:
    """Configuration for testing a program (may contain multiple commands)."""
    program_path: Path
    program_name: str
    expected_protocol_file: Path
    working_dir: Path
    command_tests: List[CommandTest] = field(default_factory=list)
    timeout: int = 30
    annotation: ProgramTestAnnotation = field(default_factory=ProgramTestAnnotation)


@dataclass
class ProgramTestTarget:
    """Mapping between a task, its program file, and associated protocol."""
    task_file: Path
    program_file: Path
    protocol_file: Path


def _relative_task_path(chapterdir: Path, task_path: Path) -> Optional[Path]:
    """Return the task path relative to chapterdir, or None if mismatched."""
    try:
        return task_path.relative_to(chapterdir)
    except Exception as exc:
        b.warning(f"Cannot derive relative path for {task_path}: {exc}")
        return None


def _default_protocol_path(altdir_chapter: Path, relative_task_path: Path) -> Path:
    """Compute default protocol path by replacing root and suffix."""
    return (altdir_chapter / relative_task_path).with_suffix('.prot')


def _find_program_file(itree_root: Path, relative_task_path: Path) -> Optional[Path]:
    """Find the program file matching the task stem under itree."""
    program_dir = itree_root / relative_task_path.parent
    if not program_dir.exists():
        return None
    stem = relative_task_path.stem
    candidates = sorted(
        [p for p in program_dir.iterdir()
         if p.is_file() and p.stem == stem and p.suffix.lower() not in PROGRAM_FILE_EXCLUDE_SUFFIXES]
    )
    return candidates[0] if candidates else None


def _extract_itree_zip(zip_path: Path) -> Optional[Path]:
    """Extract an itree zip archive and return the extraction directory."""
    try:
        mtime = zip_path.stat().st_mtime
    except OSError:
        return None
    cache_key = str(zip_path.resolve())
    cached = _ITREE_EXTRACTION_CACHE.get(cache_key)
    if cached and cached[1] == mtime and cached[0].exists():
        return cached[0]
    extract_dir = Path(tempfile.mkdtemp(prefix="programchecker_itree_"))
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)
    _ITREE_EXTRACTION_CACHE[cache_key] = (extract_dir, mtime)
    return extract_dir


def _prepare_itree_directory(itree_path: Path) -> Optional[Path]:
    """Ensure that the itree path points to a usable directory."""
    if itree_path.is_dir():
        return itree_path
    if itree_path.is_file():
        return _extract_itree_zip(itree_path)
    return None


def extract_program_test_targets(course: sdrl.course.Coursebuilder) -> List[ProgramTestTarget]:
    """Collect program/protocol pairs from task markdown files based on manual markup."""
    targets: List[ProgramTestTarget] = []
    seen_pairs: set[tuple[Path, Path]] = set()
    annotation_extractor = AnnotationExtractor()
    chapterdir_value = getattr(course, 'chapterdir', None)
    altdir_value = getattr(course, 'altdir', None)
    itreedir_value = getattr(course, 'itreedir', None)
    if not chapterdir_value or not altdir_value or not itreedir_value:
        b.error("Course configuration missing chapterdir/altdir/itreedir settings")
        return targets
    chapterdir_path = Path(chapterdir_value)
    altdir_chapter_path = Path(altdir_value)
    raw_itreedir_path = Path(itreedir_value)
    if not chapterdir_path.exists():
        b.error(f"chapterdir not found: {chapterdir_path}")
        return targets
    if not altdir_chapter_path.exists():
        b.error(f"altdir (chapter) not found: {altdir_chapter_path}")
        return targets
    itree_root = _prepare_itree_directory(raw_itreedir_path)
    if not itree_root or not itree_root.exists():
        b.error(f"itreedir not found: {raw_itreedir_path}")
        return targets
    for chapter in course.chapters:
        if chapter.to_be_skipped:
            continue
        for taskgroup in chapter.taskgroups:
            if taskgroup.to_be_skipped:
                continue
            for task in taskgroup.tasks:
                if task.to_be_skipped:
                    continue
                source_path = Path(task.sourcefile)
                if not source_path.exists():
                    b.warning(f"Task file not found for program tests: {source_path}")
                    continue
                try:
                    content = source_path.read_text(encoding='utf-8')
                except Exception as exc:
                    b.warning(f"Cannot read task file {source_path}: {exc}")
                    continue
                annotation = annotation_extractor.extract_annotations_from_file(
                    str(source_path), content=content
                )
                if not annotation.has_markup:
                    b.debug(f"No PROGRAM_TEST markup found in {source_path}; skipping program tests")
                    continue
                rel_path = _relative_task_path(chapterdir_path, source_path)
                if rel_path is None:
                    continue
                protocol_path = _default_protocol_path(altdir_chapter_path, rel_path)
                if not protocol_path.exists():
                    b.warning(f"Protocol file not found for {source_path}: {protocol_path}")
                    continue
                program_path = _find_program_file(itree_root, rel_path)
                if not program_path:
                    b.warning(f"Program file not found for {source_path} in {raw_itreedir_path}")
                    continue
                pair_key = (program_path, protocol_path)
                if pair_key in seen_pairs:
                    b.debug(f"Duplicate program test reference ignored: {program_path}")
                    continue
                seen_pairs.add(pair_key)
                targets.append(ProgramTestTarget(
                    task_file=source_path,
                    program_file=program_path,
                    protocol_file=protocol_path
                ))
    return targets
    
@dataclass
class ProgramTestResult:
    """Result of running and testing a program."""
    program_name: str
    success: bool
    actual_output: str = ""
    expected_output: str = ""
    error_message: str = ""
    missing_dependencies: List[str] = field(default_factory=list)
    skipped: bool = False
    execution_time: float = 0.0
    exit_code: int = 0
    skip_category: str = ""  # "config_skip", "partial_skip", "runtime_skip"
    partial_skip_details: Dict[str, Any] = field(default_factory=dict)  # For partial skip programs
    command_override: bool = False  # Whether command override was used
    override_details: Dict[str, str] = field(default_factory=dict)  # Override command details
    
    def __str__(self) -> str:
        status = "PASS" if self.success else ("SKIP" if self.skipped else "FAIL")
        return f"{self.program_name}: {status}"

class ProgramChecker:
    """Main program testing class for SeDriLa courses."""
    
    # Default timeout for program execution
    DEFAULT_TIMEOUT = 30
    
    def __init__(self, course_root: Path = None, parallel_execution: bool = True, report_dir: str = None):
        """Initialize ProgramChecker.
        
        Args:
            course_root: Root directory of the course (defaults to current directory)
            parallel_execution: Whether to run tests in parallel (default: True)
            report_dir: Directory for report output (defaults to current directory)
        """
        self.course_root = course_root or Path.cwd()
        self.report_dir = report_dir or str(Path.cwd())
        self.results = []
        self.skipped_programs = []  # Track programs skipped by markup
        self.parallel_execution = parallel_execution
        self.annotation_extractor = AnnotationExtractor()
    
    def _get_task_md_path(self, program_path: Path, itree_root: Path) -> Optional[Path]:
        """Map program file path to corresponding task .md file.
        
        Args:
            program_path: Path to program file
            itree_root: Root path of itree directory
            
        Returns:
            Path to task .md file, or None if not found
        """
        try:
            # Get relative path from itree root
            rel_path = program_path.relative_to(itree_root)
            
            # Remove extension and add .md
            md_name = rel_path.stem + '.md'
            md_rel_path = rel_path.parent / md_name
            
            # Construct path in ch/ directory
            task_md_path = self.course_root / 'ch' / md_rel_path
            
            if task_md_path.exists():
                b.debug(f"Found task file: {task_md_path}")
                return task_md_path
            else:
                b.debug(f"Task file not found: {task_md_path}")
                return None
        except Exception as e:
            b.debug(f"Error mapping program to task file: {e}")
            return None
    
    def _get_annotation_for_program(self, program_path: Path, itree_root: Path) -> ProgramTestAnnotation:
        """Get program test markup from corresponding task .md file.
        
        Args:
            program_path: Path to program file
            itree_root: Root path of itree directory
            
        Returns:
            ProgramTestAnnotation object (empty if no task file or no markup)
        """
        task_md_path = self._get_task_md_path(program_path, itree_root)
        if task_md_path is None:
            return ProgramTestAnnotation()
        
        return self.annotation_extractor.extract_annotations_from_file(str(task_md_path))
    
    def _should_skip_program(self, annotation: ProgramTestAnnotation) -> Tuple[bool, str]:
        """Check if program should be completely skipped based on markup.
        
        Args:
            annotation: Program test markup from task .md file
            
        Returns:
            Tuple of (should_skip, reason)
        """
        if annotation.skip:
            return True, annotation.skip_reason or 'Configured to skip'
        return False, ""
    
    def _should_skip_command(self, annotation: ProgramTestAnnotation, command: str, output: str) -> Tuple[bool, str]:
        """Check if specific command should be skipped based on markup.
        
        Args:
            annotation: Program test markup from task .md file
            command: The command being tested
            output: Expected output from command
            
        Returns:
            Tuple of (should_skip, reason)
        """
        if annotation.partial_skip and annotation.skip_commands_with:
            for keyword in annotation.skip_commands_with:
                if keyword in output:
                    return True, annotation.partial_skip_reason or f'Contains {keyword}'
        return False, ""
    
    def build_configs_from_targets(self, targets: List[ProgramTestTarget]) -> List[ProgramTestConfig]:
        """Build ProgramTestConfig objects from manually identified targets."""
        configs: List[ProgramTestConfig] = []
        seen_pairs: set[tuple[Path, Path]] = set()
        for target in targets:
            pair_key = (target.program_file, target.protocol_file)
            if pair_key in seen_pairs:
                b.debug(f"Duplicate target ignored: {target.program_file}")
                continue
            seen_pairs.add(pair_key)
            annotation = self.annotation_extractor.extract_annotations_from_file(str(target.task_file))
            should_skip, skip_reason = self._should_skip_program(annotation)
            program_name = target.program_file.stem
            if should_skip:
                skipped_result = ProgramTestResult(
                    program_name=program_name,
                    success=False,
                    skipped=True,
                    error_message=skip_reason or 'Configured to skip',
                    skip_category="config_skip"
                )
                self.skipped_programs.append(skipped_result)
                continue
            command_tests = self.parse_command_tests_from_prot(
                target.protocol_file,
                target.program_file.name,
                annotation
            )
            if not command_tests:
                b.debug(f"No testable commands found in {target.protocol_file}")
                continue
            config = ProgramTestConfig(
                program_path=target.program_file,
                program_name=program_name,
                expected_protocol_file=target.protocol_file,
                working_dir=target.program_file.parent,
                command_tests=command_tests,
                annotation=annotation
            )
            configs.append(config)
            total_commands = len(command_tests)
            testable_commands = len([
                ct for ct in command_tests
                if not ct.has_errors and not ct.needs_interaction and not ct.has_redirection
            ])
            b.debug(
                f"Configured test pair: {program_name} <-> {target.protocol_file.name} "
                f"({testable_commands}/{total_commands} testable commands)"
            )
        return configs
    
    def parse_command_tests_from_prot(self, prot_file: Path, program_name: str, annotation: ProgramTestAnnotation) -> List[CommandTest]:
        """Parse all command tests from .prot file.
        
        Args:
            prot_file: Path to .prot file
            program_name: Name of the program
            annotation: Program test markup from task .md file
            
        Returns:
            List of CommandTest objects
        """
        try:
            content = prot_file.read_text(encoding='utf-8')
        except Exception as e:
            b.error(f"Failed to read {prot_file}: {e}")
            return []
        
        lines = content.split('\n')
        command_tests = []
        current_command = None
        current_output = []
        
        for i, line in enumerate(lines):
            stripped_line = line.strip()
            
            # Check if this is a command line
            if stripped_line.startswith('$'):
                # Save previous command if exists
                if current_command:
                    output_text = '\n'.join(current_output).strip()
                    command_test = self._create_command_test(current_command, output_text, program_name, annotation)
                    if command_test:
                        command_tests.append(command_test)
                
                # Start new command
                current_command = stripped_line[1:].strip()  # Remove $ and whitespace
                current_output = []
                continue
            
            # Check if this is a shell prompt line (user@host pattern)
            if self._is_shell_prompt(stripped_line):
                # Save previous command if exists
                if current_command:
                    output_text = '\n'.join(current_output).strip()
                    command_test = self._create_command_test(current_command, output_text, program_name, annotation)
                    if command_test:
                        command_tests.append(command_test)
                    current_command = None
                    current_output = []
                continue
            
            # Collect output lines
            if current_command is not None:
                current_output.append(line.rstrip())
        
        # Handle last command
        if current_command:
            output_text = '\n'.join(current_output).strip()
            command_test = self._create_command_test(current_command, output_text, program_name, annotation)
            if command_test:
                command_tests.append(command_test)
        
        return command_tests
    
    def _is_shell_prompt(self, line: str) -> bool:
        """Check if line is a shell prompt (user@host pattern)."""
        return '@' in line and any(x in line for x in ['$', '#', '~', '/'])
    
    def _create_command_test(self, command: str, output: str, program_name: str, annotation: ProgramTestAnnotation) -> Optional[CommandTest]:
        """Create CommandTest object and analyze its properties.
        
        Args:
            command: The command to run
            output: Expected output from command
            program_name: Name of the program file
            annotation: Program test markup from task .md file
        """
        
        # If there's a command override, use it directly without checking relevance
        if annotation.command_override:
            final_command = annotation.correct_command
        else:
            # Normal flow: check if command relates to our program file
            if program_name not in command:
                return None  # Not related to this program
            final_command = command
        
        # Check for various flags using both hardcoded logic and markup
        has_errors = self._has_error_output(output)
        needs_interaction = self._needs_interaction(output)
        has_redirection = self._has_redirection(command)
        
        # Additional check for markup-based partial skip
        should_skip_cmd, _ = self._should_skip_command(annotation, command, output)
        if should_skip_cmd:
            has_errors = True  # Mark as having errors to skip it
        
        return CommandTest(
            command=final_command,
            expected_output=output,
            has_errors=has_errors,
            needs_interaction=needs_interaction,
            has_redirection=has_redirection
        )
    
    def _has_error_output(self, output: str) -> bool:
        """Check if output contains error traces or exceptions."""
        error_indicators = [
            'Traceback (most recent call last):',
            'Error:',
            'Exception:',
            'MemoryError',
            'IndexError',
            'ValueError',
            'KeyError',
            'FileNotFoundError',
        ]
        return any(indicator in output for indicator in error_indicators)
    
    def _needs_interaction(self, output: str) -> bool:
        """Check if command needs interactive input."""
        interaction_indicators = [
            'Enter',
            'Input:',
            'input:',
            '(Enter to proceed)',
            'Press',
            'Continue?',
        ]
        return any(indicator in output for indicator in interaction_indicators)
    
    def _has_redirection(self, command: str) -> bool:
        """Check if command has shell redirection."""
        redirection_indicators = ['>', '<', '>>', '|', '&&', '||', '(', ')']
        return any(indicator in command for indicator in redirection_indicators)
    
    def run_single_command_test(self, config: ProgramTestConfig, command_test: CommandTest) -> ProgramTestResult:
        """Execute a single command test."""
        start_time = time.time()
        
        # Skip tests with errors, interaction, or redirection
        if command_test.has_errors:
            return ProgramTestResult(
                program_name=config.program_name,
                success=False,
                error_message=f"Command contains error demonstration: {command_test.command[:50]}...",
                skipped=True,
                execution_time=time.time() - start_time,
                skip_category="runtime_skip"
            )
        
        if command_test.needs_interaction:
            return ProgramTestResult(
                program_name=config.program_name,
                success=False,
                error_message=f"Command needs interactive input: {command_test.command[:50]}...",
                skipped=True,
                execution_time=time.time() - start_time,
                skip_category="runtime_skip"
            )
        
        if command_test.has_redirection:
            return ProgramTestResult(
                program_name=config.program_name,
                success=False,
                error_message=f"Command has shell redirection: {command_test.command[:50]}...",
                skipped=True,
                execution_time=time.time() - start_time,
                skip_category="runtime_skip"
            )
        
        # Execute program directly using shell
        try:
            result = sp.run(
                command_test.command,
                shell=True,  # Use shell to support all command formats
                cwd=config.working_dir,
                capture_output=True,
                text=True,
                timeout=config.timeout,
                input="\n"  # Provide empty input for programs that might expect it
            )
            
            actual_output = result.stdout.strip()
            expected_output = command_test.expected_output.strip()
            
            # Compare outputs
            success = self.compare_outputs(actual_output, expected_output)
            
            return ProgramTestResult(
                program_name=config.program_name,
                success=success,
                actual_output=actual_output,
                expected_output=expected_output,
                error_message="" if success else f"Output mismatch for command: {command_test.command}",
                execution_time=time.time() - start_time,
                exit_code=result.returncode
            )
            
        except sp.TimeoutExpired:
            return ProgramTestResult(
                program_name=config.program_name,
                success=False,
                error_message=f"Program execution timeout ({config.timeout}s)",
                execution_time=time.time() - start_time
            )
        except Exception as e:
            return ProgramTestResult(
                program_name=config.program_name,
                success=False,
                error_message=f"Execution error: {str(e)}",
                execution_time=time.time() - start_time
            )
    
    def _cleanup_generated_files(self, working_dir: Path, program_name: str) -> None:
        """Clean up files generated during program testing.
        
        Args:
            working_dir: Directory where the program was executed
            program_name: Name of the program (for logging)
        """
        # List of file patterns that are typically generated during testing
        cleanup_patterns = [
            '*.db',      
            '*.sqlite',  
            '*.sqlite3', 
            '*.log',     
            '*.tmp',     
            '__pycache__', 
            '*.pyc',     
        ]
        
        try:
            for pattern in cleanup_patterns:
                if pattern == '__pycache__':
                    # Handle directories specially
                    for pycache_dir in working_dir.rglob(pattern):
                        if pycache_dir.is_dir():
                            shutil.rmtree(pycache_dir)
                            b.debug(f"Cleaned up directory: {pycache_dir.name}")
                else:
                    # Handle file patterns
                    for file_path in working_dir.glob(pattern):
                        if file_path.is_file():
                            file_path.unlink()
                            b.debug(f"Cleaned up generated file: {file_path.name}")
        except Exception as e:
            b.debug(f"Error during cleanup for {program_name}: {e}")
    
    def run_program_test(self, config: ProgramTestConfig) -> ProgramTestResult:
        """Execute all testable commands for a program and return aggregated result."""
        start_time = time.time()
        
        # Clean up any generated files from previous runs
        self._cleanup_generated_files(config.working_dir, config.program_name)
        
        if not config.command_tests:
            # Clean up before returning
            self._cleanup_generated_files(config.working_dir, config.program_name)
            
            return ProgramTestResult(
                program_name=config.program_name,
                success=False,
                error_message="No command tests found in .prot file",
                skipped=True,
                execution_time=time.time() - start_time,
                skip_category="runtime_skip"
            )
        
        # Check if this is a partial skip program (from markup)
        is_partial_skip = config.annotation.partial_skip
        
        # Filter testable commands (not errors, not interactive, not redirected)
        testable_commands = [
            ct for ct in config.command_tests 
            if not ct.has_errors and not ct.needs_interaction and not ct.has_redirection
        ]
        
        # Collect skip details for partial skip programs
        skipped_commands = []
        for ct in config.command_tests:
            if ct.has_errors or ct.needs_interaction or ct.has_redirection:
                skip_reason = ""
                if ct.has_errors:
                    skip_reason = config.annotation.partial_skip_reason or "error demonstration"
                elif ct.needs_interaction:
                    skip_reason = "interactive input"
                elif ct.has_redirection:
                    skip_reason = "shell redirection"
                skipped_commands.append({
                    "command": ct.command[:80] + "..." if len(ct.command) > 80 else ct.command,
                    "reason": skip_reason
                })
        
        if not testable_commands:
            # All commands are skipped
            skip_reasons = []
            for ct in config.command_tests:
                if ct.has_errors:
                    skip_reasons.append("error demonstration")
                elif ct.needs_interaction:
                    skip_reasons.append("interactive input")
                elif ct.has_redirection:
                    skip_reasons.append("shell redirection")
            
            partial_details = {}
            if is_partial_skip:
                partial_details = {
                    "skipped_commands": skipped_commands,
                    "tested_commands": [],
                    "skip_reason": config.annotation.partial_skip_reason,
                    "testable_note": config.annotation.testable_note
                }
            
            # Clean up generated files even when all commands are skipped
            self._cleanup_generated_files(config.working_dir, config.program_name)
            
            return ProgramTestResult(
                program_name=config.program_name,
                success=False,
                error_message=f"All commands skipped: {', '.join(set(skip_reasons))}",
                skipped=True,
                execution_time=time.time() - start_time,
                skip_category="partial_skip" if is_partial_skip else "runtime_skip",
                partial_skip_details=partial_details
            )
        
        # Test ALL testable commands
        tested_cmd_infos = []
        all_passed = True
        first_error = None
        total_execution_time = 0
        
        for cmd_test in testable_commands:
            result = self.run_single_command_test(config, cmd_test)
            total_execution_time += result.execution_time
            
            cmd_info = {
                "command": cmd_test.command[:80] + "..." if len(cmd_test.command) > 80 else cmd_test.command,
                "status": "PASS" if result.success else "FAIL",
                "error": result.error_message if not result.success else None
            }
            tested_cmd_infos.append(cmd_info)
            
            if not result.success:
                all_passed = False
                if first_error is None:
                    first_error = result.error_message
        
        # Build final result
        final_result = ProgramTestResult(
            program_name=config.program_name,
            success=all_passed,
            execution_time=time.time() - start_time,
            skip_category="partial_skip" if is_partial_skip and skipped_commands else None
        )
        
        # Set error message for failures
        if not all_passed:
            passed_count = sum(1 for cmd in tested_cmd_infos if cmd["status"] == "PASS")
            failed_count = len(tested_cmd_infos) - passed_count
            final_result.error_message = f"{failed_count}/{len(tested_cmd_infos)} commands failed. First error: {first_error}"
        
        # Add partial skip details
        if is_partial_skip or skipped_commands:
            final_result.partial_skip_details = {
                "skipped_commands": skipped_commands,
                "tested_commands": tested_cmd_infos,
                "skip_reason": config.annotation.partial_skip_reason if is_partial_skip else "",
                "testable_note": config.annotation.testable_note if is_partial_skip else ""
            }
        
        # Add info about multiple commands even for normal programs
        if len(tested_cmd_infos) > 1 and not final_result.partial_skip_details:
            final_result.partial_skip_details = {
                "tested_commands": tested_cmd_infos,
                "skipped_commands": skipped_commands
            }
        
        # Add command override details if used
        if config.annotation.command_override:
            final_result.command_override = True
            final_result.override_details = {
                "original_command": config.annotation.original_command,
                "correct_command": config.annotation.correct_command,
                "reason": config.annotation.override_reason
            }
        
        # Clean up generated files after testing
        self._cleanup_generated_files(config.working_dir, config.program_name)
        
        return final_result
    
    def compare_outputs(self, actual: str, expected: str) -> bool:
        """Compare actual output with expected output."""
        # Basic string comparison, strip whitespace
        actual_clean = actual.strip()
        expected_clean = expected.strip()
        
        # If expected output is empty, only check if program runs normally (no errors)
        if not expected_clean:
            return True  # Consider success if program can run
        
        return actual_clean == expected_clean
    
    def test_all_programs(self, targets: Optional[List[ProgramTestTarget]] = None,
                          show_progress: bool = False, batch_mode: bool = False) -> List[ProgramTestResult]:
        """Execute tests for all provided program targets."""
        self.skipped_programs = []
        if targets is None:
            b.error("Program test targets must be provided when running test_all_programs.")
            return []
        configs = self.build_configs_from_targets(targets)
        total_programs = len(configs) + len(self.skipped_programs)
        if total_programs == 0:
            b.warning("No program-protocol test targets found. Nothing to test.")
            self.results = []
            return []
        if batch_mode:
            b.info(f"Testing {len(configs)} programs ({len(self.skipped_programs)} skipped by markup)...")
        else:
            b.info(f"Starting program tests for {total_programs} programs...")
            b.info(f"  - {len(configs)} programs to test")
            b.info(f"  - {len(self.skipped_programs)} programs skipped by markup")
        if self.parallel_execution and len(configs) > 1:
            results = self._run_tests_parallel(configs, show_progress, batch_mode)
        else:
            results = self._run_tests_sequential(configs, show_progress, batch_mode)
        all_results = results + self.skipped_programs
        self.results = all_results
        return all_results
    
    def _run_tests_sequential(self, configs: List[ProgramTestConfig], show_progress: bool, batch_mode: bool = False) -> List[ProgramTestResult]:
        """Run tests sequentially.
        
        Args:
            configs: List of test configurations
            show_progress: Show detailed progress
            batch_mode: Use batch/CI-friendly output
        """
        results = []
        
        # Calculate offset for progress display (account for skipped programs)
        offset = len(self.skipped_programs)
        
        for i, config in enumerate(configs):
            if show_progress and not batch_mode:
                # Adjust progress to account for total programs including skipped ones
                progress = f"[{i+1+offset}/{len(configs)+offset}]"
                b.info(f"{progress} Testing {config.program_name}...")
            
            result = self.run_program_test(config)
            results.append(result)
            
            if show_progress and not batch_mode:
                status = "PASS" if result.success else ("SKIP" if result.skipped else "FAIL")
                b.info(f"{progress} {config.program_name}: {status}")
            elif batch_mode:
                # In batch mode, only show failures
                if not result.success and not result.skipped:
                    b.error(f"FAIL: {config.program_name}")
        
        return results
    
    def _run_tests_parallel(self, configs: List[ProgramTestConfig], show_progress: bool, batch_mode: bool = False) -> List[ProgramTestResult]:
        """Run tests in parallel using ThreadPoolExecutor.
        
        Args:
            configs: List of test configurations
            show_progress: Show detailed progress
            batch_mode: Use batch/CI-friendly output
        """
        results = []
        completed_count = 0
        
        # Calculate offset for progress display (account for skipped programs)
        offset = len(self.skipped_programs)
        total_programs = len(configs) + offset
        
        # Use at most 4 threads to avoid overwhelming the system
        max_workers = min(4, len(configs))
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all jobs
            future_to_config = {executor.submit(self.run_program_test, config): config for config in configs}
            
            # Process completed jobs as they finish
            for future in as_completed(future_to_config):
                config = future_to_config[future]
                completed_count += 1
                
                try:
                    result = future.result()
                    results.append(result)
                    
                    if show_progress and not batch_mode:
                        progress = f"[{completed_count+offset}/{total_programs}]"
                        status = "PASS" if result.success else ("SKIP" if result.skipped else "FAIL")
                        b.info(f"{progress} {config.program_name}: {status}")
                    elif batch_mode and not result.success and not result.skipped:
                        # In batch mode, only show failures
                        b.error(f"FAIL: {config.program_name}")
                        
                except Exception as e:
                    # Create a failed result for any exception during execution
                    error_result = ProgramTestResult(
                        program_name=config.program_name,
                        success=False,
                        error_message=f"Test execution failed: {str(e)}"
                    )
                    results.append(error_result)
                    
                    if show_progress and not batch_mode:
                        progress = f"[{completed_count+offset}/{total_programs}]"
                        b.error(f"{progress} {config.program_name}: ERROR - {str(e)}")
                    elif batch_mode:
                        b.error(f"FAIL: {config.program_name}: ERROR - {str(e)}")
        
        # Sort results by program name for consistent output
        results.sort(key=lambda r: r.program_name)
        return results
    
    def generate_reports(self, results: List[ProgramTestResult] = None, batch_mode: bool = False) -> None:
        """Generate test reports.
        
        Args:
            results: Test results to report
            batch_mode: Use batch/CI-friendly output
        """
        if results is None:
            results = self.results
        
        # Generate Markdown report
        self.generate_markdown_report(results)
        
        # Print summary
        self.print_summary(results, batch_mode=batch_mode)
    
    def generate_markdown_report(self, results: List[ProgramTestResult]) -> None:
        """Generate Markdown report."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        passed_tests = [r for r in results if r.success]
        failed_tests = [r for r in results if not r.success and not r.skipped]
        skipped_tests = [r for r in results if r.skipped]
        skipped_config = [r for r in skipped_tests if r.skip_category == "config_skip"]
        skipped_runtime = [r for r in skipped_tests if r.skip_category == "runtime_skip"]
        
        report_content = f"""# Program Test Report

Generated: {timestamp}

## Summary

- **Total Tests**: {len(results)}
- **Passed**: {len(passed_tests)}
- **Failed**: {len(failed_tests)}
- **Skipped (annotation)**: {len(skipped_config)}
- **Skipped (runtime)**: {len(skipped_runtime)}
- **Success Rate**: {(len(passed_tests) / len(results) * 100):.1f}%

## Failed Tests
"""
        
        if failed_tests:
            for result in failed_tests:
                report_content += f"""
### {result.program_name}

- **Error**: {result.error_message}
- **Execution Time**: {result.execution_time:.2f}s
- **Exit Code**: {result.exit_code}

"""
                if result.actual_output:
                    preview = result.actual_output[:300]
                    if len(result.actual_output) > 300:
                        preview += "..."
                    report_content += f"""**Actual Output Preview:**
```
{preview}
```

"""
        else:
            report_content += "\nNo failed tests.\n"
        
        report_content += "\n## Skipped Tests (by markup)\n"
        
        if skipped_config:
            for result in skipped_config:
                report_content += f"""
### {result.program_name}

- **Reason**: {result.error_message}

"""
        else:
            report_content += "\nNo tests skipped by markup.\n"
        
        if skipped_runtime:
            report_content += "\n## Skipped Tests (at runtime)\n"
            for result in skipped_runtime:
                deps = f" [Missing: {', '.join(result.missing_dependencies)}]" if result.missing_dependencies else ""
                report_content += f"""
### {result.program_name}

- **Reason**: {result.error_message}{deps}

"""
        
        # Add command override section
        override_tests = [r for r in results if r.command_override]
        if override_tests:
            report_content += "\n## Programs with Command Override\n"
            for result in override_tests:
                status = "PASS" if result.success else ("SKIP" if result.skipped else "FAIL")
                report_content += f"""
### {result.program_name} - {status}

- **Original Command**: `{result.override_details.get('original_command', 'N/A')}`
- **Overridden Command**: `{result.override_details.get('correct_command', 'N/A')}`
- **Reason**: {result.override_details.get('reason', 'N/A')}
- **Execution Time**: {result.execution_time:.2f}s

"""
        
        report_content += "\n## Passed Tests\n"
        
        if passed_tests:
            for result in passed_tests:
                override_note = " *(with command override)*" if result.command_override else ""
                report_content += f"""
### {result.program_name}{override_note}

- **Execution Time**: {result.execution_time:.2f}s

"""
        else:
            report_content += "\nNo passed tests.\n"
        
        report_file = os.path.join(self.report_dir, "program_test_report.md")
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report_content)
        except Exception as e:
            b.error(f"Failed to save Markdown report: {e}")
    
    def print_summary(self, results: List[ProgramTestResult], batch_mode: bool = False) -> None:
        """Print test summary.
        
        Args:
            results: Test results to summarize
            batch_mode: Use batch/CI-friendly output (concise, errors at end)
        """
        if not results:
            b.info("No program tests were executed.")
            return
        
        passed = sum(1 for r in results if r.success)
        failed = sum(1 for r in results if not r.success and not r.skipped)
        skipped_config = sum(1 for r in results if r.skipped and r.skip_category == "config_skip")
        skipped_partial = sum(1 for r in results if r.skip_category == "partial_skip")
        skipped_runtime = sum(1 for r in results if r.skipped and r.skip_category == "runtime_skip")
        total_skipped = skipped_config + skipped_partial + skipped_runtime
        
        summary_line = (
            f"Programs: {len(results)} | Passed: {passed} | Failed: {failed} | Skipped: {total_skipped}"
        )
        b.info(summary_line)
        if total_skipped and not batch_mode:
            b.info(
                f"    (Markup: {skipped_config}, Partial: {skipped_partial}, Runtime: {skipped_runtime})"
            )
        success_rate = (passed / len(results) * 100) if results else 0.0
        b.info(f"Success Rate: {success_rate:.1f}%")
        
        if failed:
            header = f"Failed Programs ({failed})"
            b.info(header)
            for result in results:
                if not result.success and not result.skipped:
                    b.error(f"  - {result.program_name}: {result.error_message}")


def test_single_program_file(program_path: str) -> None:
    """Test a single program file (for development/debugging)."""
    try:
        # Initialize checker with current working directory as course root
        checker = ProgramChecker(course_root=Path.cwd())
        program_file = Path(program_path)
        
        if not program_file.exists():
            b.error(f"Program file not found: {program_path}")
            return
        
        b.info(f"Testing single program file: {program_file.name}")
        b.info("=" * 60)
        
        # Determine program name
        program_name = program_file.stem
        
        # Find corresponding .prot file
        # For single file testing, we need to locate the .prot file
        # Assume the program is in itree structure: altdir/itree.zip/...
        # and .prot is in altdir/ch/... structure
        
        # Try to determine relative path from itree structure
        course_root = Path.cwd()
        altdir = course_root / "altdir"
        
        if not altdir.exists():
            b.error(f"altdir not found at {altdir}")
            return
            
        # Extract relative path from itree structure
        try:
            # If path contains itree.zip, get path after it
            path_parts = program_file.parts
            if 'itree.zip' in path_parts:
                itree_idx = path_parts.index('itree.zip')
                rel_parts = path_parts[itree_idx + 1:]
                rel_path = Path(*rel_parts) if rel_parts else Path(program_file.name)
            else:
                # Fallback: use just the filename
                rel_path = Path(program_file.name)
                
            prot_path = altdir / "ch" / rel_path.with_suffix('.prot')
            
            if not prot_path.exists():
                b.error(f"Corresponding .prot file not found: {prot_path}")
                return
                
        except Exception as e:
            b.error(f"Could not determine .prot file location: {e}")
            return
        
        # Get annotation from task .md file
        # Need to determine itree root for mapping
        if 'itree.zip' in path_parts:
            itree_idx = path_parts.index('itree.zip')
            itree_root = Path(*path_parts[:itree_idx+1])
        else:
            # Fallback: assume we're in altdir/itree.zip directory
            itree_root = altdir / "itree.zip"
        
        annotation = checker._get_annotation_for_program(program_file, itree_root)
        
        # Parse command tests from .prot file
        command_tests = checker.parse_command_tests_from_prot(prot_path, program_file.name, annotation)
        
        if not command_tests:
            b.warning(f"No testable commands found in {prot_path}")
            return
        
        # Create test configuration
        config = ProgramTestConfig(
            program_path=program_file,
            program_name=program_name,
            expected_protocol_file=prot_path,
            working_dir=program_file.parent,
            command_tests=command_tests,
            annotation=annotation
        )
        
        # Run the test
        b.info(f"Running test for {program_name}")
        b.info(f"Found {len(command_tests)} command(s) in .prot file")
        result = checker.run_program_test(config)
        # Display detailed results
        if result.partial_skip_details:
            details = result.partial_skip_details
            tested = details.get("tested_commands", [])
            skipped = details.get("skipped_commands", [])
            
            if tested:
                b.info("")
                b.info(f"✓ Tested Commands ({len(tested)}):")
                for i, cmd_info in enumerate(tested, 1):
                    status_symbol = "✓" if cmd_info['status'] == "PASS" else "✗"
                    b.info(f"  {i}. {status_symbol} [{cmd_info['status']}] {cmd_info['command']}")
                    if cmd_info.get('error'):
                        b.info(f"      Error: {cmd_info['error']}")
            
            if skipped:
                b.info("")
                b.info(f"✗ Skipped Commands ({len(skipped)}):")
                for i, cmd_info in enumerate(skipped, 1):
                    b.info(f"  {i}. {cmd_info['command']}")
                    b.info(f"      Reason: {cmd_info['reason']}")
                if details.get("skip_reason"):
                    b.info("")
                    b.info(f"  Overall Skip Reason: {details['skip_reason']}")
        
        # Display final result
        status = "PASS" if result.success else ("SKIP" if result.skipped else "FAIL")
        b.info(f"\nFinal Result: {status}")
        
        if result.skipped:
            b.info(f"Reason: {result.error_message}")
        elif not result.success:
            b.error(f"Test failed: {result.error_message}")
        else:
            b.info("All commands passed successfully!")
                    
        b.info("=" * 60)
        
    except Exception as e:
        b.error(f"Program test failed: {e}")
        raise
