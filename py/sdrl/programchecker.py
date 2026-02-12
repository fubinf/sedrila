"""
Program testing functionality for SeDriLa courses.

Automatically tests exemplary programs from itreedir against their corresponding
protocol files (.prot) using metadata from @TEST_SPEC blocks.
"""

import subprocess as sp
import os
import time
import tempfile
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
import shutil
import re

import base as b
import sdrl.course
from sdrl.protocolchecker import CheckRule, ProtocolExtractor


PROGRAM_FILE_EXCLUDE_SUFFIXES = {
    '.md', '.markdown', '.yaml', '.yml', '.txt', '.json', '.prot',
    '.cfg', '.conf', '.ini', '.xml', '.html'
}

def filter_program_check_annotations(content: str) -> str:
    """Remove @TEST_SPEC blocks before rendering."""
    lines: list[str] = []
    skip_program_check = False
    for raw_line in content.split('\n'):
        line = raw_line.rstrip()
        if skip_program_check:
            # End of @TEST_SPEC block (blank line)
            if not line.strip():
                skip_program_check = False
                continue
            continue
        if line.strip() == "@TEST_SPEC":
            skip_program_check = True
            continue
        lines.append(line)
    return '\n'.join(lines)

@dataclass
class ProgramCheckHeader:
    """Metadata for program checking from @TEST_SPEC block in .prot file."""
    lang: Optional[str] = None           # e.g., "apt-get install -y golang-go\napt-get install -y make"
    deps: Optional[str] = None           # e.g., "pip install fastapi\npip install uvicorn"
    files: Optional[str] = None          # additional files for multi-file programs
    unknown_keys: List[str] = field(default_factory=list)

    def get_lang_install_commands(self) -> List[str]:
        """Return list of install commands from lang."""
        if not self.lang:
            return []
        # Split by newlines and filter out empty lines
        commands = [line.strip() for line in self.lang.split('\n') if line.strip()]
        return commands

    def get_install_commands(self) -> List[str]:
        """Return list of install commands from deps.
        Each line in deps is a complete install command.
        Example: "pip install fastapi\npip install uvicorn" returns
        ["pip install fastapi", "pip install uvicorn"]
        """
        if not self.deps:
            return []
        # Split by newlines and filter out empty lines
        commands = [line.strip() for line in self.deps.split('\n') if line.strip()]
        return commands

class ProgramCheckHeaderExtractor:
    """Extracts and parses @TEST_SPEC blocks from .prot file content."""

    @staticmethod
    def extract_from_content(content: str) -> Optional[ProgramCheckHeader]:
        """Extract @TEST_SPEC block from protocol content."""
        lines = content.split('\n')
        in_block = False
        found_marker = False
        block_lines: List[str] = []
        for line in lines:
            stripped = line.strip()
            # Block start
            if stripped == "@TEST_SPEC":
                in_block = True
                found_marker = True
                continue
            # Block end (blank line)
            if in_block and not stripped:
                break
            # Collect block content
            if in_block:
                block_lines.append(line)
        # If @TEST_SPEC marker was found, return header even if empty
        if not found_marker:
            return None
        if not block_lines:
            return ProgramCheckHeader()
        return ProgramCheckHeaderExtractor._parse_header_block(block_lines)

    @staticmethod
    def _parse_header_block(block_lines: List[str]) -> ProgramCheckHeader:
        """Parse key=value pairs from @TEST_SPEC block."""
        header = ProgramCheckHeader()
        known_keys = {'lang', 'deps', 'files'}
        last_key = None  # Track the last key to handle multi-line deps
        for raw_line in block_lines:
            line = raw_line.strip()
            # Skip empty lines
            if not line:
                last_key = None
                continue
            # Parse key=value
            if '=' in line:
                key, _, value = line.partition('=')
                key = key.strip()
                value = value.strip()
                if key not in known_keys:
                    header.unknown_keys.append(key)
                    b.warning(f"Unknown @TEST_SPEC key: {key}")
                    last_key = None
                    continue
                setattr(header, key, value)
                last_key = key
            else:
                # Line without '=' - if last key was 'deps' or 'lang', append to that field
                if last_key == 'deps' and header.deps is not None:
                    header.deps += '\n' + line
                elif last_key == 'lang' and header.lang is not None:
                    header.lang += '\n' + line
                else:
                    b.warning(f"Invalid @TEST_SPEC line (missing '='): {line}")
                    last_key = None
        return header

    @staticmethod
    def extract_from_file(prot_filepath: str) -> Optional[ProgramCheckHeader]:
        """Extract @TEST_SPEC from a .prot file."""
        try:
            content = Path(prot_filepath).read_text(encoding='utf-8')
            return ProgramCheckHeaderExtractor.extract_from_content(content)
        except (FileNotFoundError, UnicodeDecodeError, OSError) as e:
            b.warning(f"Cannot read .prot file {prot_filepath}: {e}")
            return None


@dataclass
class CommandTest:
    """Single command test extracted from .prot file"""
    command: str                    # The command to run
    expected_output: str            # Expected output for this command
    has_errors: bool = False        # True if output contains Traceback/errors
    needs_interaction: bool = False # True if command needs user input
    has_redirection: bool = False   # True if command has >/< redirection
    check_rule: Optional[CheckRule] = None  # For regex mode validation (from @PROT_SPEC)


@dataclass
class ProgramTestConfig:
    """Configuration for testing a program (may contain multiple commands)."""
    program_path: Path
    program_name: str
    protocol_file: Path
    program_check_header: ProgramCheckHeader
    working_dir: Path
    command_tests: List[CommandTest] = field(default_factory=list)
    timeout: int = 30


@dataclass
class ProgramTestTarget:
    """Maps a protocol file to its program location."""
    protocol_file: Path
    program_check_header: ProgramCheckHeader
    program_file: Optional[Path] = None  # path to the actual program file


@dataclass
class ProtSpecBlockResult:
    """Result for a single @PROT_SPEC block within a .prot file."""
    block_index: int  # 0-indexed position of block in file
    command: str  # The command that was tested
    status: str  # "passed", "failed", "manual", "skip"
    error_message: str = ""
    manual_reason: str = ""


@dataclass
class ProgramTestResult:
    """Result of running and testing a program."""
    program_name: str
    success: bool
    protocol_file: str = ""  # Path to the .prot file (from configuration)
    program_file: str = ""  # Path to the program file
    additional_files: List[str] = field(default_factory=list)  # Files referenced via files=
    actual_output: str = ""
    expected_output: str = ""
    error_message: str = ""
    missing_dependencies: List[str] = field(default_factory=list)
    skipped: bool = False
    execution_time: float = 0.0
    exit_code: int = 0
    manual_reason: str = ""  # Human-readable reason for manual testing
    block_results: List[ProtSpecBlockResult] = field(default_factory=list)  # Per-block results

    def __str__(self) -> str:
        status = "PASS" if self.success else ("SKIP" if self.skipped else "FAIL")
        return f"{self.program_name}: {status}"

    def get_block_stats(self) -> dict:
        """Get statistics of block results."""
        stats = {
            'passed': 0,
            'failed': 0,
            'manual': 0,
            'skip': 0,
            'total': len(self.block_results)
        }
        for block in self.block_results:
            if block.status in stats:
                stats[block.status] += 1
        return stats


def _find_program_file(itree_root: Path, prot_file: Path) -> Optional[Path]:
    """Find the program file by matching stem with .prot file."""
    try:
        rel_path = prot_file.relative_to(prot_file.parents[2])  # Go up to altdir level
        program_dir = itree_root / rel_path.parent
        stem = prot_file.stem
        if not program_dir.exists():
            return None
        candidates = sorted([
            p for p in program_dir.iterdir()
            if p.is_file() and p.stem == stem
            and p.suffix.lower() not in PROGRAM_FILE_EXCLUDE_SUFFIXES
        ])
        return candidates[0] if candidates else None
    except (ValueError, IndexError):
        return None


def check_prot_file_completeness(filepath: str) -> bool:
    """Check if a file has @TEST_SPEC but no @PROT_SPEC. Returns True if incomplete."""
    try:
        content = Path(filepath).read_text(encoding='utf-8')
        has_test_spec = '@TEST_SPEC' in content
        has_prot_spec = '@PROT_SPEC' in content
        return has_test_spec and not has_prot_spec
    except (FileNotFoundError, OSError):
        return False


def validate_prot_files_completeness(course: sdrl.course.Coursebuilder) -> List[str]:
    """Check all .prot files have @PROT_SPEC if they have @TEST_SPEC."""
    warnings: List[str] = []
    altdir_path = Path(course.altdir).resolve()
    for prot_file in altdir_path.rglob('*.prot'):
        if check_prot_file_completeness(str(prot_file)):
            rel_path = prot_file.relative_to(altdir_path)
            warnings.append(
                f"Protocol file has @TEST_SPEC but no @PROT_SPEC: {rel_path}\n"
                f"  → This file will be skipped during program testing"
            )
    return warnings


def extract_program_test_targets(course: sdrl.course.Coursebuilder) -> List[ProgramTestTarget]:
    """Extract @TEST_SPEC blocks from .prot files in altdir."""
    targets: List[ProgramTestTarget] = []
    altdir_path = Path(course.altdir).resolve()
    itree_root = Path(course.itreedir).resolve()
    if not altdir_path.exists():
        b.error(f"altdir not found: {altdir_path}")
        return targets
    if not itree_root.exists():
        b.error(f"itreedir not found: {itree_root}")
        return targets
    extractor = ProgramCheckHeaderExtractor()
    # Walk through all .prot files in altdir
    for prot_file in altdir_path.rglob('*.prot'):
        try:
            content = prot_file.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError) as e:
            b.warning(f"Cannot read .prot file {prot_file}: {e}")
            continue
        header = extractor.extract_from_content(content)
        if not header:
            # No @TEST_SPEC block
            continue
        program_file = _find_program_file(itree_root, prot_file)
        targets.append(ProgramTestTarget(
            protocol_file=prot_file,
            program_check_header=header,
            program_file=program_file
        ))
    return targets


def check_test_spec_dependency_gaps(course) -> None:
    """Check for missing @TEST_SPEC in dependency chains between marked tasks.
    Standalone function suitable for calling during author build."""
    if not hasattr(course, 'altdir') or not hasattr(course, 'taskdict'):
        return
    targets = extract_program_test_targets(course)
    if not targets:
        return
    checker = ProgramChecker(course=course)
    marked_tasks: Dict[str, Any] = {}
    for target in targets:
        task_name = target.protocol_file.stem
        marked_tasks[task_name] = target
    task_deps: Dict[str, set] = {}
    for task_name in marked_tasks:
        if hasattr(course, 'get_all_assumed_tasks'):
            all_assumed = course.get_all_assumed_tasks(task_name)
            task_deps[task_name] = {t for t in all_assumed if t in marked_tasks}
        else:
            task_deps[task_name] = set()
    checker._check_dependency_chain_gaps(marked_tasks, task_deps)


class ProgramChecker:
    """Main program testing class for SeDriLa courses."""
    DEFAULT_TIMEOUT = 30
    def __init__(self, course_root: Path = None,
                 report_dir: str = None,
                 itreedir: Optional[Path] = None, chapterdir: Optional[Path] = None,
                 course: Optional[Any] = None, config_vars: Optional[Dict[str, str]] = None):
        """Initialize ProgramChecker."""
        self.course_root = course_root or Path.cwd()
        self.report_dir = report_dir or str(Path.cwd())
        self.results: List[ProgramTestResult] = []
        self.itreedir = itreedir
        self.chapterdir = chapterdir
        self.course = course
        # Extract altdir and itreedir paths (same as extract_program_test_targets uses)
        self._altdir_path = Path(course.altdir).resolve() if course else None
        self._itreedir_path = Path(course.itreedir).resolve() if course else None
        # Build config_vars from course object or use provided config_vars
        self.config_vars = self._build_config_vars(config_vars)

    def _build_config_vars(self, config_vars: Optional[Dict[str, str]]) -> Dict[str, str]:
        """Build configuration variables from course object or provided dict."""
        if config_vars:
            return {k: str(v) for k, v in config_vars.items()}
        vars_dict: Dict[str, str] = {}
        if self.course:
            if hasattr(self.course, 'configdict') and isinstance(self.course.configdict, dict):
                for key, value in self.course.configdict.items():
                    if isinstance(value, (str, int, float, Path)):
                        vars_dict[key] = str(value)
                    elif hasattr(value, '__fspath__'):  # Path-like objects
                        vars_dict[key] = str(value)
            for attr_name in dir(self.course):
                if attr_name.startswith('_'):
                    continue
                try:
                    value = getattr(self.course, attr_name)
                except (AttributeError, Exception):
                    # Some @property attributes may have broken getters; skip them
                    continue
                if callable(value) or isinstance(value, (dict, list)):
                    continue
                if isinstance(value, (str, int, float, Path)) or hasattr(value, '__fspath__'):
                    if attr_name not in vars_dict:  # Don't override configdict values
                        vars_dict[attr_name] = str(value)
        return vars_dict

    def _get_global_execution_order(self, configs: List[ProgramTestConfig]) -> List[ProgramTestConfig]:
        """Sort all configs globally by task dependency order (across all taskgroups)."""
        if not self.course or not hasattr(self.course, 'get_all_assumed_tasks'):
            return configs
        # Build mapping from program name to config
        all_tasks: Dict[str, ProgramTestConfig] = {}
        for config in configs:
            task_name = config.program_name
            all_tasks[task_name] = config
        # Build dependencies across all tasks
        task_deps: Dict[str, set[str]] = {}
        for task_name in all_tasks:
            all_assumed = self.course.get_all_assumed_tasks(task_name)
            deps_in_all = {t for t in all_assumed if t in all_tasks}
            task_deps[task_name] = deps_in_all
        # Check for missing @TEST_SPEC in dependency chains
        self._check_dependency_chain_gaps(all_tasks, task_deps)
        # Topological sort
        sorted_tasks: List[str] = []
        remaining = set(all_tasks.keys())
        while remaining:
            ready_tasks = {t for t in remaining if task_deps[t].isdisjoint(remaining)}
            if not ready_tasks:
                b.warning(f"Circular dependency detected, executing remaining tasks in arbitrary order: {remaining}")
                sorted_tasks.extend(sorted(remaining))
                break
            sorted_tasks.extend(sorted(ready_tasks))
            remaining -= ready_tasks
        return [all_tasks[t] for t in sorted_tasks]

    def _check_dependency_chain_gaps(self, marked_tasks: Dict[str, ProgramTestConfig],
                                     filtered_deps: Dict[str, set[str]]) -> None:
        """Warn about missing @TEST_SPEC markers in dependency chains."""
        if not hasattr(self.course, 'taskdict'):
            return
        marked_set = set(marked_tasks.keys())
        missing_with_path: Dict[str, List[str]] = {}
        for task_name in marked_set:
            deps_marked = filtered_deps[task_name]
            for marked_dep in deps_marked:
                path = self._find_shortest_path(task_name, marked_dep)
                if path and len(path) > 2:
                    for i in range(1, len(path) - 1):
                        intermediate = path[i]
                        if intermediate not in marked_set:
                            if intermediate not in missing_with_path or len(path) < len(missing_with_path[intermediate]):
                                missing_with_path[intermediate] = path
        for missing_task in sorted(missing_with_path.keys()):
            path = missing_with_path[missing_task]
            path_str = ' -> '.join(reversed(path))
            b.warning(
                f"Task '{missing_task}' is missing @TEST_SPEC but appears in dependency chain: {path_str}"
            )

    def _find_shortest_path(self, start: str, end: str) -> Optional[List[str]]:
        """Find shortest dependency path from start to end using BFS."""
        if start == end:
            return [start]
        if not hasattr(self.course, 'taskdict'):
            return None
        from collections import deque
        queue = deque([(start, [start])])
        visited = {start}
        while queue:
            current, path = queue.popleft()
            task_obj = self.course.taskdict.get(current)
            if not task_obj or not hasattr(task_obj, 'assumes'):
                continue
            for assumed in task_obj.assumes:
                if assumed == end:
                    return path + [assumed]
                if assumed not in visited:
                    visited.add(assumed)
                    queue.append((assumed, path + [assumed]))
        return None

    def build_configs_from_targets(self, targets: List[ProgramTestTarget],
                                   itree_root: Path) -> List[ProgramTestConfig]:
        """Build ProgramTestConfig objects from extracted targets."""
        configs: List[ProgramTestConfig] = []
        seen_pairs: set[Tuple[Path, Path]] = set()
        for target in targets:
            header = target.program_check_header
            prot_file = target.protocol_file
            # Find program file
            program_path = _find_program_file(itree_root, prot_file)
            if not program_path:
                b.warning(f"Cannot locate program file for {prot_file}")
                continue
            # Check for duplicates
            pair_key = (program_path, prot_file)
            if pair_key in seen_pairs:
                b.debug(f"Duplicate program test: {program_path}")
                continue
            seen_pairs.add(pair_key)
            # Parse commands from .prot file
            command_tests = self.parse_command_tests_from_prot(prot_file)
            if not command_tests:
                b.debug(f"No testable commands in {prot_file}")
                continue
            config = ProgramTestConfig(
                program_path=program_path,
                program_name=program_path.stem,
                protocol_file=prot_file,
                program_check_header=header,
                working_dir=program_path.parent,
                command_tests=command_tests,
                timeout=self.DEFAULT_TIMEOUT
            )
            configs.append(config)
        return configs

    def parse_command_tests_from_prot(self, prot_file: Path) -> List[CommandTest]:
        """Parse all command tests from .prot file."""
        if not self.has_prot_spec_blocks(prot_file):
            b.debug(f"No @PROT_SPEC blocks in {prot_file}")
            return []
        return self._parse_regex_mode(prot_file)

    def has_prot_spec_blocks(self, prot_file: Path) -> bool:
        """Check if .prot file contains @PROT_SPEC blocks."""
        try:
            content = prot_file.read_text(encoding='utf-8')
            return '@PROT_SPEC' in content
        except OSError:
            return False

    def _parse_regex_mode(self, prot_file: Path) -> List[CommandTest]:
        """Parse commands using ProtocolExtractor and attach CheckRule to each CommandTest."""
        extractor = ProtocolExtractor()
        protocol_file = extractor.extract_from_file(str(prot_file))
        command_tests: List[CommandTest] = []
        for entry in protocol_file.entries:
            command_test = CommandTest(
                command=entry.command,
                expected_output=entry.output,
                check_rule=entry.check_rule
            )
            command_tests.append(command_test)
        return command_tests

    def _cleanup_generated_files(self, working_dir: Path, program_name: str) -> None:
        """Clean up files generated during program testing."""
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
                    for pycache_dir in working_dir.rglob(pattern):
                        if pycache_dir.is_dir():
                            shutil.rmtree(pycache_dir)
                            b.debug(f"Cleaned up directory: {pycache_dir.name}")
                else:
                    for file_path in working_dir.glob(pattern):
                        if file_path.is_file():
                            file_path.unlink()
                            b.debug(f"Cleaned up generated file: {file_path.name}")
        except (OSError, shutil.Error) as exc:
            b.debug(f"Error during cleanup for {program_name}: {exc}")

    def _create_command_test(self, command: str, output: str) -> Optional[CommandTest]:
        """Create a CommandTest from command and expected output."""
        if not command.strip():
            return None
        has_errors = bool(re.search(r'(Traceback|Error|error|failed)', output))
        needs_interaction = bool(re.search(r'[<>|&]', command))
        has_redirection = bool(re.search(r'[<>]', command))
        return CommandTest(
            command=command,
            expected_output=output,
            has_errors=has_errors,
            needs_interaction=needs_interaction,
            has_redirection=has_redirection
        )

    def _substitute_variables_in_path(self, path: str) -> str:
        """Substitute all $variable_name references in path using config_vars."""
        import re
        pattern = r'\$([a-zA-Z_][a-zA-Z0-9_]*)'
        variables = re.findall(pattern, path)
        if not variables:
            return path
        result_path = path
        for var_name in set(variables):  # Use set to avoid duplicate processing
            if var_name not in self.config_vars:
                raise ValueError(
                    f"Variable ${var_name} found in path '{path}' but not defined in configuration. "
                    f"Available variables: {', '.join(sorted(self.config_vars.keys()))}"
                )
            var_value = self.config_vars[var_name]
            var_pattern = f'${var_name}'
            # Split path at the variable
            parts = result_path.split(var_pattern)
            if len(parts) != 2:
                raise ValueError(f"Invalid path format with {var_pattern}: {path}")
            pre_path = parts[0]   # e.g., "../../../"
            post_path = parts[1]  # e.g., "/Sprachen/Go/go-test.go"
            # Reconstruct: variable path + post_path
            abs_var_path = Path(var_value).resolve()
            abs_full_path = (abs_var_path / post_path.lstrip('/')).resolve()
            result_path = str(abs_full_path)
        return result_path

    def _read_files_file(self, prot_file: Path) -> Tuple[Dict[str, str], Optional[Path]]:
        """Read .files file from altdir (same directory as .prot file)."""
        prot_name = prot_file.stem  # e.g., "go-test" from "go-test.prot"
        files_filename = f"{prot_name}.files"
        # Look for .files file in the same directory as .prot file (in altdir)
        files_file_path = prot_file.parent / files_filename
        if not files_file_path.exists():
            return {}, None
        try:
            result = {}
            for line in files_file_path.read_text(encoding='utf-8').split('\n'):
                line = line.strip()
                if line:
                    short_name = Path(line).name
                    result[short_name] = line
            return result, files_file_path.parent
        except (OSError, UnicodeDecodeError) as e:
            b.warning(f"Cannot read .files file {files_file_path}: {e}")
            return {}, None

    def _build_file_name_mapping(self, config: ProgramTestConfig) -> Dict[str, str]:
        """Build mapping from file names to absolute paths."""
        mapping: Dict[str, str] = {}
        abs_program_path = config.program_path.resolve()
        mapping[abs_program_path.name] = str(abs_program_path)
        if config.program_check_header.files:
            # Read .files file and get its directory
            files_content, files_file_dir = self._read_files_file(config.protocol_file)
            if not files_file_dir:
                raise ValueError(f"files= field specified but .files file not found for {config.protocol_file}")
            for file_name in config.program_check_header.files.split(','):
                file_name = file_name.strip()
                if not file_name:
                    continue
                if file_name not in files_content:
                    raise ValueError(f"File '{file_name}' declared in files= but not found in .files file for {config.protocol_file}")
                rel_path = files_content[file_name]
                # Determine how to resolve the path
                if '$' in rel_path:
                    # Path has variables, substitute them
                    abs_path_str = self._substitute_variables_in_path(rel_path)
                    abs_path = Path(abs_path_str)
                elif '/' not in rel_path and '\\' not in rel_path:
                    # Simple filename (no path separators), relative to .files file's directory
                    abs_path = (files_file_dir / rel_path).resolve()
                else:
                    # Path with slashes but no variables, relative to .files directory
                    abs_path = (files_file_dir / rel_path).resolve()
                mapping[file_name] = str(abs_path)
        return mapping

    def _substitute_file_names_in_command(self, command: str, file_mapping: Dict[str, str]) -> str:
        """Replace file names in command with their full paths."""
        result = command
        # Sort by length (longest first) to avoid partial replacements
        for file_name in sorted(file_mapping.keys(), key=len, reverse=True):
            full_path = file_mapping[file_name]
            result = re.sub(r'\b' + re.escape(file_name) + r'\b', full_path, result)
        return result

    def _create_isolated_test_context(self, config: ProgramTestConfig) -> Tuple[Path, Optional[Dict[str, str]]]:
        """Create an isolated temporary directory for testing."""
        temp_dir = Path(tempfile.mkdtemp(prefix=f'sedrila_test_{config.program_name}_'))
        try:
            if config.program_path.exists():
                shutil.copy2(config.program_path, temp_dir / config.program_path.name)
            file_mapping = {}
            if config.program_check_header.files:
                original_mapping = self._build_file_name_mapping(config)
                for file_name, original_path in original_mapping.items():
                    src_path = Path(original_path)
                    if src_path.exists():
                        dst_path = temp_dir / src_path.name
                        shutil.copy2(src_path, dst_path)
                        file_mapping[file_name] = str(dst_path)
            return temp_dir, file_mapping if file_mapping else None
        except (ValueError, OSError) as e:
            try:
                shutil.rmtree(temp_dir)
            except OSError:
                pass
            raise e

    def test_program(self, config: ProgramTestConfig) -> ProgramTestResult:
        """Execute tests for a single program in an isolated context."""
        # Calculate relative paths for reporting (relative to altdir's grandparent)
        common_parent = self._altdir_path.parent.parent
        prot_file_abs = Path(config.protocol_file).resolve()
        program_file_abs = Path(config.program_path).resolve()
        prot_file_display = str(prot_file_abs.relative_to(common_parent))
        program_file_display = str(program_file_abs.relative_to(common_parent))
        # Collect additional files and convert to relative paths
        additional_files = []
        if config.program_check_header.files:
            files_content, files_file_dir = self._read_files_file(config.protocol_file)
            for file_name in config.program_check_header.files.split(','):
                file_name = file_name.strip()
                if file_name in files_content:
                    rel_path = files_content[file_name]
                    if '$' in rel_path:
                        abs_path = Path(self._substitute_variables_in_path(rel_path)).resolve()
                    else:
                        abs_path = (files_file_dir / rel_path).resolve()
                    additional_files.append(str(abs_path.relative_to(common_parent)))
        result = ProgramTestResult(
            program_name=config.program_name,
            success=False,
            protocol_file=prot_file_display,
            program_file=program_file_display,
            additional_files=additional_files
        )
        start_time = time.time()
        temp_dir = None
        try:
            temp_dir, file_mapping = self._create_isolated_test_context(config)
            self._cleanup_generated_files(temp_dir, config.program_name)
            # Execute commands and validate based on check_rule
            has_auto_test = False
            manual_reasons = []
            block_results = []
            for block_idx, command_test in enumerate(config.command_tests):
                try:
                    rule = command_test.check_rule
                    # Check if this block has a spec
                    if rule is None or (not rule.output_re and rule.exitcode is None):
                        # Manual or skip block
                        manual_reason = rule.manual_text if rule and rule.manual_text else "No automated checks specified"
                        status = "manual" if rule else "skip"
                        block_results.append(ProtSpecBlockResult(
                            block_index=block_idx,
                            command=command_test.command,
                            status=status,
                            manual_reason=manual_reason
                        ))
                        manual_reasons.append(manual_reason)
                        continue  # Skip this block, continue with next
                    has_auto_test = True
                    # Substitute file names only if mapping exists
                    if file_mapping:
                        substituted_command = self._substitute_file_names_in_command(command_test.command, file_mapping)
                    else:
                        substituted_command = command_test.command
                    actual_output, actual_exitcode = self._run_command(
                        substituted_command,
                        temp_dir,
                        config.timeout
                    )
                    # Validate output_re if specified
                    block_passed = True
                    block_error = ""
                    if rule.output_re:
                        validation_result = self._validate_output_regex(
                            actual_output,
                            command_test.expected_output,
                            rule
                        )
                        if not validation_result['success']:
                            block_passed = False
                            block_error = validation_result['error_message']
                            result.actual_output = actual_output
                            result.expected_output = command_test.expected_output
                            result.error_message = block_error
                            result.exit_code = actual_exitcode
                    # Validate exitcode if specified
                    if block_passed and rule.exitcode is not None:
                        if actual_exitcode != rule.exitcode:
                            block_passed = False
                            block_error = f"Exit code mismatch: expected {rule.exitcode}, got {actual_exitcode}"
                            result.actual_output = actual_output
                            result.error_message = block_error
                            result.exit_code = actual_exitcode
                    # Record block result
                    block_results.append(ProtSpecBlockResult(
                        block_index=block_idx,
                        command=command_test.command,
                        status="passed" if block_passed else "failed",
                        error_message=block_error
                    ))
                    # If this block failed, stop and return failure
                    if not block_passed:
                        result.block_results = block_results
                        return result
                except (TimeoutError, Exception) as e:
                    # Set error message based on exception type
                    if isinstance(e, TimeoutError):
                        result.error_message = f"Timeout executing: {command_test.command}"
                    else:
                        result.error_message = str(e)
                    # Record failed block and return
                    block_results.append(ProtSpecBlockResult(
                        block_index=block_idx,
                        command=command_test.command,
                        status="failed",
                        error_message=result.error_message
                    ))
                    result.block_results = block_results
                    return result
            result.block_results = block_results
            # After processing all blocks, check if any auto test was executed
            if not has_auto_test:
                result.skipped = True
                result.manual_reason = "; ".join(manual_reasons) if manual_reasons else "No automated checks specified"
                return result
            result.success = True
        except Exception as e:
            result.error_message = str(e)
        finally:
            # Clean up isolated test context
            if temp_dir:
                try:
                    shutil.rmtree(temp_dir)
                except Exception as e:
                    b.warning(f"Failed to clean up temp directory {temp_dir}: {e}")
            result.execution_time = time.time() - start_time
        return result

    def _validate_output_regex(self, actual_output: str, expected_output: str,
                              check_rule: CheckRule) -> Dict[str, Any]:
        """Validate output using regex pattern from CheckRule."""
        if not check_rule.output_re or not check_rule.output_re.strip():
            return {'success': False, 'error_message': "No output_re pattern in @PROT_SPEC block"}
        try:
            match = re.compile(check_rule.output_re).search(actual_output)
            if match:
                return {'success': True, 'error_message': None}
            return {'success': False, 'error_message': f"Output does not match regex pattern: {check_rule.output_re}"}
        except re.error as e:
            return {'success': False, 'error_message': f"Invalid regex pattern '{check_rule.output_re}': {e}"}

    def _run_command(self, command: str, working_dir: Path, timeout: int) -> Tuple[str, int]:
        """Run a command and return (output, exitcode)."""
        env = os.environ.copy()
        try:
            result = sp.run(
                command,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                shell=True,  # Allow shell interpretation for commands
                env=env
            )
            return result.stdout + result.stderr, result.returncode
        except sp.TimeoutExpired:
            raise TimeoutError(f"Command timed out after {timeout}s: {command}")

    def run_tests(self, configs: List[ProgramTestConfig], show_progress: bool = False,
                  batch_mode: bool = False) -> List[ProgramTestResult]:
        """Run all program tests with global dependency order (no parallel execution)."""
        if not configs:
            return []
        # Global topological sort across all tasks
        sorted_configs = self._get_global_execution_order(configs)
        # Serial execution of all tasks
        results = []
        total = len(sorted_configs)
        if batch_mode:
            b.info(f"Testing {total} programs...")
        for i, config in enumerate(sorted_configs, 1):
            if show_progress and not batch_mode:
                b.info(f"Testing {config.program_name} ({i}/{total})...")
            result = self.test_program(config)
            results.append(result)
            if show_progress and not batch_mode:
                # Classify based on block content
                if self._has_failed_blocks(result):
                    status = "✗ FAIL"
                elif self._has_manual_blocks(result):
                    status = "⊙ MANUAL"
                else:
                    status = "✓ PASS"
                b.info(f"  {status}")
        return results

    def collect_deps_by_task(self, targets: List[ProgramTestTarget]) -> Dict[str, List[str]]:
        """Collect dependency install commands grouped by task name."""
        task_deps: Dict[str, List[str]] = {}
        for target in targets:
            program_name = target.protocol_file.stem  # e.g., "go-maps" from "go-maps.prot"
            header = target.program_check_header
            commands = header.get_install_commands()
            task_deps[program_name] = commands if commands else []
        return task_deps

    def test_all_programs(self, targets: List[ProgramTestTarget], itree_root: Optional[Path] = None,
                         show_progress: bool = True, batch_mode: bool = False) -> List[ProgramTestResult]:
        """Test all programs from targets."""
        if itree_root is None:
            if self.itreedir:
                itree_root = self.itreedir
            elif 'itreedir' in self.config_vars:
                itree_root = Path(self.config_vars['itreedir'])
            else:
                b.error("itreedir not provided and not configured in ProgramChecker")
                return []
        if not itree_root.exists():
            b.error(f"itreedir not found: {itree_root}")
            return []
        if not itree_root.is_dir():
            b.error(f"itreedir is not a directory: {itree_root}")
            return []
        configs = self.build_configs_from_targets(targets, itree_root)
        if show_progress and not batch_mode:
            b.info(f"Found {len(configs)} programs to test")
        results = self.run_tests(configs, show_progress=show_progress, batch_mode=batch_mode)
        self.results = results
        return results

    def _format_files_for_report(self, result: ProgramTestResult) -> str:
        """Format files list for report table (each file on separate line using markdown line breaks)."""
        files = []
        if result.protocol_file:
            files.append(result.protocol_file)
        if result.program_file:
            files.append(result.program_file)
        files.extend(result.additional_files)
        return "<br>".join([f"`{f}`" for f in files if f])

    def _format_block_stats_for_report(self, result: ProgramTestResult) -> str:
        """Format block statistics for report table."""
        if not result.block_results:
            return "N/A"
        stats = result.get_block_stats()
        parts = []
        if stats['passed'] > 0:
            parts.append(f"{stats['passed']} passed")
        if stats['failed'] > 0:
            parts.append(f"{stats['failed']} failed")
        if stats['manual'] > 0:
            parts.append(f"{stats['manual']} manual")
        if stats['skip'] > 0:
            parts.append(f"{stats['skip']} skip")
        return "<br>".join(parts) if parts else "0 blocks"

    def _has_manual_blocks(self, result: ProgramTestResult) -> bool:
        """Check if result has any manual blocks."""
        return any(b.status == 'manual' for b in result.block_results)

    def _has_failed_blocks(self, result: ProgramTestResult) -> bool:
        """Check if result has any failed blocks."""
        return not result.success and not result.skipped

    def generate_reports(self, results: List[ProgramTestResult], batch_mode: bool = False):
        """Generate markdown report from test results."""
        if not results:
            b.warning("No test results to report")
            return
        from datetime import datetime
        report_lines = []
        report_lines.append("# Program Test Report\n\n")
        report_lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        # Classify results based on block content
        failed_results = [r for r in results if self._has_failed_blocks(r)]
        manual_results = [r for r in results if self._has_manual_blocks(r) and not self._has_failed_blocks(r)]
        passed_skip_results = [r for r in results if not self._has_failed_blocks(r) and not self._has_manual_blocks(r)]
        total = len(results)
        failed_count = len(failed_results)
        manual_count = len(manual_results)
        passed_skip_count = len(passed_skip_results)
        fail_rate = (failed_count / total * 100) if total > 0 else 0.0
        manual_rate = (manual_count / total * 100) if total > 0 else 0.0
        passed_skip_rate = (passed_skip_count / total * 100) if total > 0 else 0.0
        # Calculate block-level statistics
        total_blocks = sum(len(r.block_results) for r in results)
        blocks_passed = sum(sum(1 for b in r.block_results if b.status == 'passed') for r in results)
        blocks_failed = sum(sum(1 for b in r.block_results if b.status == 'failed') for r in results)
        blocks_manual = sum(sum(1 for b in r.block_results if b.status == 'manual') for r in results)
        blocks_skip = sum(sum(1 for b in r.block_results if b.status == 'skip') for r in results)
        report_lines.append("## Summary\n\n")
        report_lines.append("### Program-Level Statistics\n\n")
        report_lines.append(f"- **Total programs:** {total}\n")
        report_lines.append(f"- **Failed:** {failed_count} ({fail_rate:.1f}%)\n")
        report_lines.append(f"- **Manual test required:** {manual_count} ({manual_rate:.1f}%)\n")
        report_lines.append(f"- **Passed and skipped:** {passed_skip_count} ({passed_skip_rate:.1f}%)\n\n")
        if total_blocks > 0:
            report_lines.append("### Block-Level Statistics\n\n")
            report_lines.append(f"- **Total @PROT_SPEC blocks:** {total_blocks}\n")
            report_lines.append(f"- **Passed:** {blocks_passed}\n")
            report_lines.append(f"- **Failed:** {blocks_failed}\n")
            report_lines.append(f"- **Manual:** {blocks_manual}\n")
            report_lines.append(f"- **Skip:** {blocks_skip}\n\n")
        # Failed Tests section
        if failed_count > 0:
            report_lines.append("## Failed Tests\n\n")
            report_lines.append("| Test | Files | @PROT_SPEC Blocks | Error |\n")
            report_lines.append("|------|-------|-------------------|-------|\n")
            for r in failed_results:
                error_msg = r.error_message.replace('\n', ' ').replace('|', '\\|')[:100]
                files_str = self._format_files_for_report(r)
                blocks_str = self._format_block_stats_for_report(r)
                report_lines.append(f"| `{r.program_name}` | {files_str} | {blocks_str} | {error_msg} |\n")
            report_lines.append("\n")
            report_lines.append("### Failed Tests Detail\n\n")
            for r in failed_results:
                report_lines.append(f"#### {r.program_name}\n\n")
                report_lines.append(f"- **Error:** {r.error_message}\n")
                if r.expected_output:
                    report_lines.append(f"- **Expected output:**\n```\n{r.expected_output[:500]}\n```\n")
                if r.actual_output:
                    report_lines.append(f"- **Actual output:**\n```\n{r.actual_output[:500]}\n```\n")
                report_lines.append("\n")
        # Manual Test Required section
        if manual_count > 0:
            report_lines.append("## Manual Tests\n\n")
            report_lines.append("| Test | Files | @PROT_SPEC Blocks | Reason |\n")
            report_lines.append("|------|-------|-------------------|--------|\n")
            for r in manual_results:
                # Extract manual reason from block results
                manual_reasons = [b.manual_reason for b in r.block_results if b.status == 'manual' and b.manual_reason]
                reason = "; ".join(manual_reasons) if manual_reasons else r.manual_reason
                reason = reason.replace('\n', ' ').replace('|', '\\|')
                files_str = self._format_files_for_report(r)
                blocks_str = self._format_block_stats_for_report(r)
                report_lines.append(f"| `{r.program_name}` | {files_str} | {blocks_str} | {reason} |\n")
            report_lines.append("\n")
        # Passed and Skipped Tests section
        if passed_skip_count > 0:
            report_lines.append("## Passed and skiped Tests\n\n")
            report_lines.append("| Test | Files | @PROT_SPEC Blocks | Execution Time |\n")
            report_lines.append("|------|-------|-------------------|----------------|\n")
            for r in passed_skip_results:
                files_str = self._format_files_for_report(r)
                blocks_str = self._format_block_stats_for_report(r)
                report_lines.append(f"| `{r.program_name}` | {files_str} | {blocks_str} | {r.execution_time:.2f}s |\n")
            report_lines.append("\n")
        report_path = Path(self.report_dir) / "program_test_report.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, 'w') as f:
            f.write(''.join(report_lines))
        b.info(f"Report written to {report_path}")
        # Print batch summary if requested
        if batch_mode and failed_count > 0:
            b.warning(f"Failed {failed_count} programs:")
            for r in failed_results:
                b.warning(f"  - {r.program_name}: {r.error_message}")

