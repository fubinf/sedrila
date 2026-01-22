"""
Program testing functionality for SeDriLa courses.

Automatically tests exemplary programs from itreedir against their corresponding
protocol files (.prot) using metadata from @PROGRAM_CHECK blocks.
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
    """Remove @PROGRAM_CHECK blocks before rendering."""
    lines: list[str] = []
    skip_program_check = False
    for raw_line in content.split('\n'):
        line = raw_line.rstrip()
        if skip_program_check:
            # End of @PROGRAM_CHECK block (blank line)
            if not line.strip():
                skip_program_check = False
                continue
            continue
        if line.strip() == "@PROGRAM_CHECK":
            skip_program_check = True
            continue
        lines.append(line)
    return '\n'.join(lines)

@dataclass
class ProgramCheckHeader:
    """Metadata for program checking from @PROGRAM_CHECK block in .prot file."""
    lang: Optional[str] = None           # e.g., "apt-get install -y golang-go\napt-get install -y make"
    deps: Optional[str] = None           # e.g., "pip install fastapi\npip install uvicorn"
    typ: Optional[str] = None            # e.g., "exact", "regex", "manual"
    manual_reason: Optional[str] = None  # reason for manual testing (for typ=manual)
    files: Optional[str] = None          # additional files for multi-file programs
    unknown_keys: List[str] = field(default_factory=list)

    def is_valid(self) -> bool:
        """Check if header has required fields and valid values."""
        if self.typ is None:
            return False
        if self.typ not in ('manual', 'regex'):
            return False
        if self.typ == 'manual' and not self.manual_reason:
            return False
        return True

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
    """Extracts and parses @PROGRAM_CHECK blocks from .prot file content."""

    @staticmethod
    def extract_from_content(content: str) -> Optional[ProgramCheckHeader]:
        """Extract @PROGRAM_CHECK block from protocol content."""
        lines = content.split('\n')
        in_block = False
        block_lines: List[str] = []
        for line in lines:
            stripped = line.strip()
            # Block start
            if stripped == "@PROGRAM_CHECK":
                in_block = True
                continue
            # Block end (blank line)
            if in_block and not stripped:
                break
            # Collect block content
            if in_block:
                block_lines.append(line)
        if not block_lines:
            return None
        return ProgramCheckHeaderExtractor._parse_header_block(block_lines)

    @staticmethod
    def _parse_header_block(block_lines: List[str]) -> ProgramCheckHeader:
        """Parse key=value pairs from @PROGRAM_CHECK block."""
        header = ProgramCheckHeader()
        known_keys = {'lang', 'deps', 'typ', 'manual_reason', 'files'}
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
                    b.warning(f"Unknown @PROGRAM_CHECK key: {key}")
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
                    b.warning(f"Invalid @PROGRAM_CHECK line (missing '='): {line}")
                    last_key = None
        return header

    @staticmethod
    def extract_from_file(prot_filepath: str) -> Optional[ProgramCheckHeader]:
        """Extract @PROGRAM_CHECK from a .prot file."""
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
    taskgroup: str
    command_tests: List[CommandTest] = field(default_factory=list)
    timeout: int = 30


@dataclass
class ProgramTestTarget:
    """Maps a protocol file to its program location."""
    protocol_file: Path
    program_check_header: ProgramCheckHeader
    taskgroup: str  # e.g., "Go", "Python", "Frameworks"
    program_file: Optional[Path] = None  # path to the actual program file


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
    skip_category: str = ""  # e.g., "manual", "missing_deps"
    manual_reason: str = ""  # Human-readable reason for manual testing
    typ: str = "exact"  # Test mode: "exact", "regex", or "manual"

    def __str__(self) -> str:
        status = "PASS" if self.success else ("SKIP" if self.skipped else "FAIL")
        return f"{self.program_name}: {status}"


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


def _extract_taskgroup_from_path(prot_file: Path, altdir_path: Path) -> str:
    """Extract taskgroup name from .prot file path."""
    rel_path = prot_file.relative_to(altdir_path)
    parent_dirs = rel_path.parent.parts
    return parent_dirs[-1]


def extract_program_test_targets(course: sdrl.course.Coursebuilder) -> List[ProgramTestTarget]:
    """Extract @PROGRAM_CHECK blocks from .prot files in altdir, optionally filtered by taskgroup.
    If the environment variable SDRL_TASKGROUP is set, only extracts targets from that taskgroup.
    This enables automatic taskgroup filtering in multi-container CI environments without CLI parameters.
    """
    targets: List[ProgramTestTarget] = []
    altdir_path = Path(course.altdir).resolve()
    itree_root = Path(course.itreedir).resolve()
    if not altdir_path.exists():
        b.error(f"altdir not found: {altdir_path}")
        return targets
    if not itree_root.exists():
        b.error(f"itreedir not found: {itree_root}")
        return targets
    # Check for SDRL_TASKGROUP environment variable for automatic filtering
    only_taskgroup = os.getenv('SDRL_TASKGROUP')
    if only_taskgroup:
        b.debug(f"SDRL_TASKGROUP environment variable set: filtering to taskgroup '{only_taskgroup}'")
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
            # No @PROGRAM_CHECK block
            continue
        if not header.is_valid():
            b.warning(f"@PROGRAM_CHECK block in {prot_file} missing required fields "
                     f"(typ={header.typ}, manual_reason={header.manual_reason if header.typ == 'manual' else 'N/A'})")
            continue
        taskgroup = _extract_taskgroup_from_path(prot_file, altdir_path)
        # Filter by taskgroup if SDRL_TASKGROUP is set
        if only_taskgroup and taskgroup != only_taskgroup:
            continue
        program_file = _find_program_file(itree_root, prot_file)
        targets.append(ProgramTestTarget(
            protocol_file=prot_file,
            program_check_header=header,
            taskgroup=taskgroup,
            program_file=program_file
        ))
    return targets


class ProgramChecker:
    """Main program testing class for SeDriLa courses."""
    DEFAULT_TIMEOUT = 30
    def __init__(self, course_root: Path = None, parallel_execution: bool = True,
                 report_dir: str = None, max_workers: Optional[int] = None,
                 itreedir: Optional[Path] = None, chapterdir: Optional[Path] = None,
                 course: Optional[Any] = None, config_vars: Optional[Dict[str, str]] = None,
                 taskgroup_paths: Optional[Dict[str, str]] = None):
        """Initialize ProgramChecker."""
        self.course_root = course_root or Path.cwd()
        self.report_dir = report_dir or str(Path.cwd())
        self.results: List[ProgramTestResult] = []
        self.parallel_execution = parallel_execution
        self.max_workers = self._determine_max_workers(max_workers)
        self.itreedir = itreedir
        self.chapterdir = chapterdir
        self.course = course
        self.taskgroup_paths = taskgroup_paths or {}
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

    @staticmethod
    def _determine_max_workers(override: Optional[int]) -> int:
        """Resolve worker count from override or environment variable."""
        default_workers = 4
        if override is not None:
            if override < 1:
                b.warning("max_workers must be >= 1; using default 4")
                return default_workers
            return override
        env_value = os.getenv("SDRL_PROGCHECK_MAX_WORKERS")
        if not env_value:
            return default_workers
        try:
            parsed = int(env_value)
            if parsed < 1:
                raise ValueError("value must be >= 1")
            return parsed
        except ValueError:
            b.warning(f"Invalid SDRL_PROGCHECK_MAX_WORKERS='{env_value}', using default")
            return default_workers

    def get_taskgroup_execution_order(self, taskgroup: str, configs: List[ProgramTestConfig]) -> List[ProgramTestConfig]:
        """Sort configs within a taskgroup by task dependency order."""
        if not self.course or not hasattr(self.course, 'get_all_assumed_tasks'):
            return configs
        # Extract task names from configs (map program name to task name)
        taskgroup_tasks: Dict[str, ProgramTestConfig] = {}
        for config in configs:
            task_name = config.program_name
            taskgroup_tasks[task_name] = config
        task_deps: Dict[str, set[str]] = {}
        for task_name in taskgroup_tasks:
            all_assumed = self.course.get_all_assumed_tasks(task_name)
            deps_in_group = {t for t in all_assumed if t in taskgroup_tasks}
            task_deps[task_name] = deps_in_group
        sorted_tasks: List[str] = []
        remaining = set(taskgroup_tasks.keys())
        while remaining:
            ready_tasks = {t for t in remaining if task_deps[t].isdisjoint(remaining)}
            if not ready_tasks:
                b.warning(f"Circular dependency detected in taskgroup {taskgroup}, "
                         f"executing remaining tasks in arbitrary order: {remaining}")
                sorted_tasks.extend(sorted(remaining))
                break
            sorted_tasks.extend(sorted(ready_tasks))
            remaining -= ready_tasks
        return [taskgroup_tasks[t] for t in sorted_tasks]

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
            if header.typ == 'manual':
                # Manual tests don't need parsing
                command_tests = []
            else:
                command_tests = self.parse_command_tests_from_prot(prot_file, typ=header.typ)
                if not command_tests:
                    b.debug(f"No testable commands in {prot_file}")
                    continue
            config = ProgramTestConfig(
                program_path=program_path,
                program_name=program_path.stem,
                protocol_file=prot_file,
                program_check_header=header,
                working_dir=program_path.parent,
                taskgroup=target.taskgroup,
                command_tests=command_tests,
                timeout=self.DEFAULT_TIMEOUT
            )
            configs.append(config)
        return configs

    def parse_command_tests_from_prot(self, prot_file: Path, typ: str = 'regex') -> List[CommandTest]:
        """Parse all command tests from .prot file."""
        if typ == 'manual':
            # Manual tests don't need parsing
            return []
        # Always use regex mode for parsing
        if not self.has_prot_spec_blocks(prot_file):
            b.debug(f"No @PROT_SPEC blocks in {prot_file}, cannot parse regex mode")
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
                    # Simple filename (no path separators), relative to .prot file's directory
                    abs_path = (config.protocol_file.parent / rel_path).resolve()
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
            additional_files=additional_files,
            typ=config.program_check_header.typ or 'exact'
        )
        start_time = time.time()
        temp_dir = None
        try:
            if config.program_check_header.typ == 'manual':
                result.skipped = True
                result.skip_category = 'manual'
                result.manual_reason = config.program_check_header.manual_reason or "Manual testing required"
                return result
            temp_dir, file_mapping = self._create_isolated_test_context(config)
            self._cleanup_generated_files(temp_dir, config.program_name)
            # Execute commands for all program types (except manual which already returned)
            for command_test in config.command_tests:
                try:
                    # Substitute file names only if mapping exists
                    if file_mapping:
                        substituted_command = self._substitute_file_names_in_command(command_test.command, file_mapping)
                    else:
                        substituted_command = command_test.command
                    actual = self._run_command(
                        substituted_command,
                        temp_dir,
                        config.timeout,
                        taskgroup=config.taskgroup
                    )
                    # Regex mode: use output_re pattern matching
                    if command_test.check_rule is None or not command_test.check_rule.output_re:
                        raise ValueError(f"No @PROT_SPEC block found for command: {command_test.command}")
                    validation_result = self._validate_output_regex(
                        actual,
                        command_test.expected_output,
                        command_test.check_rule
                    )
                    if not validation_result['success']:
                        result.actual_output = actual
                        result.expected_output = command_test.expected_output
                        result.error_message = validation_result['error_message']
                        return result
                except TimeoutError:
                    result.error_message = f"Timeout executing: {command_test.command}"
                    return result
                except Exception as e:
                    result.error_message = str(e)
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

    def _run_command(self, command: str, working_dir: Path, timeout: int,
                     taskgroup: Optional[str] = None) -> str:
        """Run a command and return its output."""
        env = os.environ.copy()
        # If taskgroup is specified and has a path, modify PATH to use taskgroup bin
        if taskgroup and taskgroup in self.taskgroup_paths:
            lang_dir = self.taskgroup_paths[taskgroup]
            bin_dir = str(Path(lang_dir) / "bin")
            env['PATH'] = f"{bin_dir}:{env.get('PATH', '')}"
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
            return result.stdout + result.stderr
        except sp.TimeoutExpired:
            raise TimeoutError(f"Command timed out after {timeout}s: {command}")

    def run_tests(self, configs: List[ProgramTestConfig], show_progress: bool = False) -> List[ProgramTestResult]:
        """Run all program tests with per-taskgroup parallel execution."""
        if not configs:
            return []
        configs_by_taskgroup: Dict[str, List[ProgramTestConfig]] = {}
        for config in configs:
            if config.taskgroup not in configs_by_taskgroup:
                configs_by_taskgroup[config.taskgroup] = []
            configs_by_taskgroup[config.taskgroup].append(config)
        for taskgroup in configs_by_taskgroup:
            configs_by_taskgroup[taskgroup] = self.get_taskgroup_execution_order(
                taskgroup, configs_by_taskgroup[taskgroup]
            )
        num_taskgroups = len(configs_by_taskgroup)
        if self.parallel_execution and num_taskgroups > 1:
            return self._run_taskgroups_parallel(configs_by_taskgroup, show_progress)
        else:
            return self._run_taskgroups_sequential(configs_by_taskgroup, show_progress)

    def _run_taskgroups_sequential(self, configs_by_taskgroup: Dict[str, List[ProgramTestConfig]],
                                   show_progress: bool = False) -> List[ProgramTestResult]:
        """Run taskgroups sequentially (configs within each group are already sorted by dependency)."""
        results = []
        total_configs = sum(len(configs) for configs in configs_by_taskgroup.values())
        completed = 0
        for taskgroup, configs in sorted(configs_by_taskgroup.items()):
            if show_progress:
                b.info(f"Processing taskgroup: {taskgroup}")
            for config in configs:
                completed += 1
                if show_progress:
                    b.info(f"  Testing {config.program_name} ({completed}/{total_configs})...")
                result = self.test_program(config)
                results.append(result)
                if show_progress:
                    status = "✓ PASS" if result.success else ("⊘ SKIP" if result.skipped else "✗ FAIL")
                    b.info(f"    {status}")
        return results

    def _run_taskgroups_parallel(self, configs_by_taskgroup: Dict[str, List[ProgramTestConfig]],
                                 show_progress: bool = False) -> List[ProgramTestResult]:
        """Run taskgroups in parallel, with serial execution within each taskgroup."""
        results_lock = __import__('threading').Lock()
        all_results: List[ProgramTestResult] = []
        total_configs = sum(len(configs) for configs in configs_by_taskgroup.values())
        completed_count = [0]  # Use list for mutability in nested function

        def run_taskgroup(taskgroup: str, configs: List[ProgramTestConfig]) -> List[ProgramTestResult]:
            """Run all configs in a taskgroup sequentially."""
            taskgroup_results = []
            for config in configs:
                result = self.test_program(config)
                taskgroup_results.append(result)
                with results_lock:
                    completed_count[0] += 1
                    if show_progress:
                        status = "✓" if result.success else ("⊘" if result.skipped else "✗")
                        b.info(f"  {status} {config.program_name} ({completed_count[0]}/{total_configs})")
            return taskgroup_results
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(configs_by_taskgroup))) as executor:
            futures = {
                executor.submit(run_taskgroup, taskgroup, configs): taskgroup
                for taskgroup, configs in configs_by_taskgroup.items()
            }
            for future in as_completed(futures):
                taskgroup_results = future.result()
                all_results.extend(taskgroup_results)
        return all_results

    def run_single_task(self, configs: List[ProgramTestConfig], taskgroup: str, task_name: str) -> List[ProgramTestResult]:
        """Run tests for a single task within a taskgroup."""
        # Filter configs for this specific task in this taskgroup
        task_configs = [
            config for config in configs
            if config.taskgroup == taskgroup and config.program_name == task_name]
        if not task_configs:
            b.warning(f"No configs found for task '{task_name}' in taskgroup '{taskgroup}'")
            return []
        results = []
        for config in task_configs:
            result = self.test_program(config)
            results.append(result)
        return results

    def collect_lang_by_taskgroup(self, targets: List[ProgramTestTarget]) -> Dict[str, List[str]]:
        """Collect language install commands grouped by taskgroup."""
        taskgroup_langs: Dict[str, set] = {}
        for target in targets:
            header = target.program_check_header
            commands = header.get_lang_install_commands()
            if target.taskgroup not in taskgroup_langs:
                taskgroup_langs[target.taskgroup] = set()
            taskgroup_langs[target.taskgroup].update(commands)
        result = {}
        for taskgroup, commands_set in taskgroup_langs.items():
            result[taskgroup] = sorted(list(commands_set))
        return result

    def collect_deps_by_task(self, targets: List[ProgramTestTarget]) -> Dict[str, List[str]]:
        """Collect dependency install commands grouped by task name."""
        task_deps: Dict[str, List[str]] = {}
        for target in targets:
            program_name = target.protocol_file.stem  # e.g., "go-maps" from "go-maps.prot"
            header = target.program_check_header
            commands = header.get_install_commands()
            task_deps[program_name] = commands if commands else []
        return task_deps

    def collect_metadata_by_taskgroup(self, targets: List[ProgramTestTarget]) -> Dict[str, Any]:
        """Collect metadata grouped by taskgroup including lang and deps."""
        taskgroup_metadata: Dict[str, Dict[str, Any]] = {}
        for target in targets:
            taskgroup = target.taskgroup
            header = target.program_check_header
            program_name = target.protocol_file.stem
            # Initialize taskgroup if not exists
            if taskgroup not in taskgroup_metadata:
                taskgroup_metadata[taskgroup] = {
                    'lang': [],
                    'deps': [],
                    'tasks': []
                }
            lang_commands = header.get_lang_install_commands()
            for cmd in lang_commands:
                if cmd not in taskgroup_metadata[taskgroup]['lang']:
                    taskgroup_metadata[taskgroup]['lang'].append(cmd)
            dep_commands = header.get_install_commands()
            for cmd in dep_commands:
                if cmd not in taskgroup_metadata[taskgroup]['deps']:
                    taskgroup_metadata[taskgroup]['deps'].append(cmd)
            taskgroup_metadata[taskgroup]['tasks'].append({
                'program': program_name,
                'protocol': str(target.protocol_file)
            })
        return taskgroup_metadata

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
        if show_progress:
            b.info(f"Found {len(configs)} programs to test")
        results = self.run_tests(configs, show_progress=show_progress)
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

    def generate_reports(self, results: List[ProgramTestResult], batch_mode: bool = False):
        """Generate markdown report from test results."""
        if not results:
            b.warning("No test results to report")
            return
        from datetime import datetime
        report_lines = []
        report_lines.append("# Program Test Report\n\n")
        report_lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        worker_value = os.getenv("SDRL_PROGCHECK_MAX_WORKERS", str(self.max_workers))
        report_lines.append(f"**Run parameters:** max_workers = {worker_value}\n\n")
        total = len(results)
        passed = sum(1 for r in results if r.success)
        failed = sum(1 for r in results if not r.success and not r.skipped)
        skipped = sum(1 for r in results if r.skipped)
        pass_rate = (passed / total * 100) if total > 0 else 0.0
        fail_rate = (failed / total * 100) if total > 0 else 0.0
        skip_rate = (skipped / total * 100) if total > 0 else 0.0
        report_lines.append("## Summary\n\n")
        report_lines.append(f"- **Total programs:** {total}\n")
        report_lines.append(f"- **Passed:** {passed} ({pass_rate:.1f}%)\n")
        report_lines.append(f"- **Failed:** {failed} ({fail_rate:.1f}%)\n")
        report_lines.append(f"- **Skipped (manual test):** {skipped} ({skip_rate:.1f}%)\n\n")
        if failed > 0:
            report_lines.append("## Failed Tests\n\n")
            report_lines.append("| Test | Files | Error |\n")
            report_lines.append("|------|-------|-------|\n")
            for r in results:
                if not r.success and not r.skipped:
                    error_msg = r.error_message.replace('\n', ' ').replace('|', '\\|')[:100]
                    files_str = self._format_files_for_report(r)
                    report_lines.append(f"| `{r.program_name}` | {files_str} | {error_msg} |\n")
            report_lines.append("\n")

            report_lines.append("### Failed Tests Detail\n\n")
            for r in results:
                if not r.success and not r.skipped:
                    mode_label = f"[{r.typ.upper()}]" if r.typ else "[REGEX]"
                    report_lines.append(f"#### {r.program_name} {mode_label}\n\n")
                    report_lines.append(f"- **Error:** {r.error_message}\n")
                    if r.expected_output:
                        report_lines.append(f"- **Expected output:**\n```\n{r.expected_output[:500]}\n```\n")
                    if r.actual_output:
                        report_lines.append(f"- **Actual output:**\n```\n{r.actual_output[:500]}\n```\n")
                    report_lines.append("\n")
        if skipped > 0:
            report_lines.append("## Skipped Tests (Manual Testing Required)\n\n")
            report_lines.append("| Test | Files | Reason |\n")
            report_lines.append("|------|-------|--------|\n")
            for r in results:
                if r.skipped:
                    reason = r.manual_reason.replace('\n', ' ').replace('|', '\\|')
                    files_str = self._format_files_for_report(r)
                    report_lines.append(f"| `{r.program_name}` | {files_str} | {reason} |\n")
            report_lines.append("\n")
        if passed > 0:
            report_lines.append("## Passed Tests\n\n")
            report_lines.append("| Test | Files | Execution Time |\n")
            report_lines.append("|------|-------|----------------|\n")
            for r in results:
                if r.success:
                    files_str = self._format_files_for_report(r)
                    report_lines.append(f"| `{r.program_name}` | {files_str} | {r.execution_time:.2f}s |\n")
            report_lines.append("\n")
        report_path = Path(self.report_dir) / "program_test_report.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, 'w') as f:
            f.write(''.join(report_lines))
        b.info(f"Report written to {report_path}")
        # Print batch summary if requested
        if batch_mode and failed > 0:
            b.warning(f"Failed {failed} programs:")
            for r in results:
                if not r.success and not r.skipped:
                    b.warning(f"  - {r.program_name}: {r.error_message}")

    def run_tasks_with_dynamic_deps(self, targets: List[ProgramTestTarget], taskgroup: str,
                                     itree_root: Optional[Path] = None,
                                     show_progress: bool = True, batch_mode: bool = False) -> List[ProgramTestResult]:
        """Run tasks in a taskgroup with dynamic dependency installation."""
        if itree_root is None:
            if self.itreedir:
                itree_root = self.itreedir
        taskgroup_targets = [t for t in targets if t.taskgroup == taskgroup]
        configs = self.build_configs_from_targets(taskgroup_targets, itree_root)
        sorted_configs = self.get_taskgroup_execution_order(taskgroup, configs)
        # Get unique task names in order
        seen_tasks = set()
        task_names = []
        for config in sorted_configs:
            if config.program_name not in seen_tasks:
                task_names.append(config.program_name)
                seen_tasks.add(config.program_name)
        if show_progress:
            b.info(f"Running {len(task_names)} tasks in taskgroup '{taskgroup}' with dynamic dependencies")
            b.info(f"Task execution order: {', '.join(task_names)}")
        all_results = []
        for idx, task_name in enumerate(task_names, 1):
            if show_progress:
                b.info(f"\n[{idx}/{len(task_names)}] Checking task: {task_name}")
            task_results = self.run_single_task(
                configs=sorted_configs,
                taskgroup=taskgroup,
                task_name=task_name
            )
            all_results.extend(task_results)
            if show_progress:
                for result in task_results:
                    status = "✓ PASS" if result.success else ("⊘ SKIP" if result.skipped else "✗ FAIL")
                    b.info(f"  {status}: {result.program_name}")
        self.results = all_results
        return all_results

    def aggregate_and_merge_reports(self, reports_dir: Path, output_file: Optional[Path] = None) -> str:
        """
        Aggregate individual task reports into a single unified report.
        This is used in CI to merge reports from multiple containers/jobs into one final report.
        """
        import re
        from datetime import datetime
        from dataclasses import dataclass

        @dataclass
        class AggregatedResult:
            """Aggregated test result from parsing markdown."""
            program_name: str
            taskgroup: str
            typ: str
            success: bool
            skipped: bool
            execution_time: float = 0.0
            error_message: str = ""
            manual_reason: str = ""
            files: str = ""

        def parse_report(report_path: Path, taskgroup: str) -> List[AggregatedResult]:
            """Parse a markdown report file and extract test results."""
            results = []
            content = report_path.read_text()
            passed_section = re.search(r'## Passed Tests\n\n(.*?)(?=\n## |\Z)', content, re.DOTALL)
            if passed_section:
                table_rows = re.findall(r'\| `([^`]+)` \| (.*?) \| ([\d.]+)s \|', passed_section.group(1))
                for program_name, files, exec_time in table_rows:
                    results.append(AggregatedResult(
                        program_name=program_name,
                        taskgroup=taskgroup,
                        typ='regex',
                        success=True,
                        skipped=False,
                        execution_time=float(exec_time),
                        files=files
                    ))
            skipped_section = re.search(r'## Skipped Tests.*?\n\n(.*?)(?=\n## |\Z)', content, re.DOTALL)
            if skipped_section:
                table_rows = re.findall(r'\| `([^`]+)` \| (.*?) \| (.*?) \|', skipped_section.group(1))
                for program_name, files, reason in table_rows:
                    results.append(AggregatedResult(
                        program_name=program_name,
                        taskgroup=taskgroup,
                        typ='manual',
                        success=False,
                        skipped=True,
                        manual_reason=reason,
                        files=files
                    ))
            failed_section = re.search(r'## Failed Tests\n\n(.*?)(?=\n### |\n## |\Z)', content, re.DOTALL)
            if failed_section:
                table_rows = re.findall(r'\| `([^`]+)` \| (.*?) \| (.*?) \|', failed_section.group(1))
                for program_name, files, error in table_rows:
                    results.append(AggregatedResult(
                        program_name=program_name,
                        taskgroup=taskgroup,
                        typ='regex',
                        success=False,
                        skipped=False,
                        error_message=error,
                        files=files
                    ))
            return results
        all_results = []
        for report_dir in sorted(reports_dir.glob('program-check-report-*')):
            taskgroup = report_dir.name.replace('program-check-report-', '')
            report_file = report_dir / 'program_test_report.md'
            if report_file.exists():
                results = parse_report(report_file, taskgroup)
                all_results.extend(results)
                b.info(f"Parsed {len(results)} tests from taskgroup: {taskgroup}")
        if not all_results:
            b.warning("No test results found to aggregate!")
            return ""
        report_lines = []
        report_lines.append("# Program Test Report\n")
        report_lines.append(f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        report_lines.append("**Run parameters:** max_workers = 4\n\n")
        total = len(all_results)
        passed = sum(1 for r in all_results if r.success)
        failed = sum(1 for r in all_results if not r.success and not r.skipped)
        skipped = sum(1 for r in all_results if r.skipped)
        pass_rate = (passed / total * 100) if total > 0 else 0.0
        fail_rate = (failed / total * 100) if total > 0 else 0.0
        skip_rate = (skipped / total * 100) if total > 0 else 0.0
        report_lines.append("## Summary\n\n")
        report_lines.append(f"- **Total programs:** {total}\n")
        report_lines.append(f"- **Passed:** {passed} ({pass_rate:.1f}%)\n")
        report_lines.append(f"- **Failed:** {failed} ({fail_rate:.1f}%)\n")
        report_lines.append(f"- **Skipped (manual test):** {skipped} ({skip_rate:.1f}%)\n\n")
        if failed > 0:
            report_lines.append("## Failed Tests\n\n")
            report_lines.append("| Test | Files | Error |\n")
            report_lines.append("|------|-------|-------|\n")
            for r in all_results:
                if not r.success and not r.skipped:
                    error_msg = r.error_message.replace('\n', ' ').replace('|', '\\|')[:100]
                    report_lines.append(f"| `{r.program_name}` | {r.files} | {error_msg} |\n")
            report_lines.append("\n")
            report_lines.append("### Failed Tests Detail\n\n")
            for r in all_results:
                if not r.success and not r.skipped:
                    report_lines.append(f"#### {r.program_name} [REGEX]\n\n")
                    report_lines.append(f"- **Error:** {r.error_message}\n")
                    report_lines.append(f"- **Taskgroup:** {r.taskgroup}\n\n")
        if skipped > 0:
            report_lines.append("## Skipped Tests (Manual Testing Required)\n\n")
            report_lines.append("| Test | Files | Reason |\n")
            report_lines.append("|------|-------|--------|\n")
            for r in all_results:
                if r.skipped:
                    reason = r.manual_reason.replace('\n', ' ').replace('|', '\\|')
                    report_lines.append(f"| `{r.program_name}` | {r.files} | {reason} |\n")
            report_lines.append("\n")
        if passed > 0:
            report_lines.append("## Passed Tests\n\n")
            report_lines.append("| Test | Files | Execution Time |\n")
            report_lines.append("|------|-------|----------------|\n")
            for r in all_results:
                if r.success:
                    report_lines.append(f"| `{r.program_name}` | {r.files} | {r.execution_time:.2f}s |\n")
            report_lines.append("\n")
        unified_report = ''.join(report_lines)
        if output_file:
            output_file.write_text(unified_report)
            b.info(f"Merged report written to {output_file}")
        return unified_report


