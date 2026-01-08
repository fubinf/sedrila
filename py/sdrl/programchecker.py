"""
Program testing functionality for SeDriLa courses.

Automatically tests exemplary programs from itreedir against their corresponding
protocol files (.prot) using metadata from @PROGRAM_CHECK blocks.
"""

import subprocess as sp
import os
import time
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
    lang: Optional[str] = None           # e.g., "Python 3.11", "Go 1.23"
    deps: Optional[str] = None           # e.g., "pip install fastapi\npip install uvicorn"
    typ: Optional[str] = None            # e.g., "direct", "manual"
    manual_reason: Optional[str] = None  # reason for manual testing (for typ=manual)
    files: Optional[str] = None          # additional files for multi-file programs
    unknown_keys: List[str] = field(default_factory=list)

    def is_valid(self) -> bool:
        """Check if header has required fields and valid values."""
        if self.lang is None or self.typ is None:
            return False
        if self.typ not in ('direct', 'manual'):
            return False
        if self.typ == 'manual' and not self.manual_reason:
            return False
        return True

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
                # Line without '=' - if last key was 'deps', append to deps
                if last_key == 'deps' and header.deps is not None:
                    header.deps += '\n' + line
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
        except Exception as e:
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
    skip_category: str = ""  # e.g., "manual", "missing_deps"
    manual_reason: str = ""  # Human-readable reason for manual testing

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


def extract_program_test_targets(course: sdrl.course.Coursebuilder) -> List[ProgramTestTarget]:
    """Extract all @PROGRAM_CHECK blocks from .prot files in altdir."""
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
            # No @PROGRAM_CHECK block
            continue
        if not header.is_valid():
            b.warning(f"@PROGRAM_CHECK block in {prot_file} missing required fields "
                     f"(lang={header.lang}, deps={header.deps}, typ={header.typ})")
            continue
        targets.append(ProgramTestTarget(
            protocol_file=prot_file,
            program_check_header=header
        ))
    return targets


def extract_languages_from_course(course: sdrl.course.Coursebuilder) -> Dict[str, str]:
    """Extract all programming languages and their versions from .prot files in altdir."""
    targets = extract_program_test_targets(course)
    lang_versions: Dict[str, List[str]] = {}
    for target in targets:
        if target.program_check_header.lang:
            lang_str = target.program_check_header.lang.strip()
            # Parse "Language version" format
            parts = lang_str.rsplit(None, 1)  # Split from right to get last word as version
            if len(parts) == 2:
                lang_name, version = parts
                if lang_name not in lang_versions:
                    lang_versions[lang_name] = []
                lang_versions[lang_name].append(version)
    # For each language, select the latest version
    result = {}
    for lang_name, versions in lang_versions.items():
        if not versions:
            continue
        # Select the latest version using semantic version comparison
        try:
            from packaging.version import parse as parse_version
            latest_version = max(versions, key=lambda v: parse_version(v))
        except (ImportError, Exception):
            # Fallback: simple numeric comparison (e.g., "1.23" > "1.20")
            def version_key(v: str) -> tuple:
                try:
                    return tuple(int(x) for x in v.split('.'))
                except ValueError:
                    return (0,)  # Fallback for non-numeric versions
            latest_version = max(versions, key=version_key)
        result[lang_name] = latest_version
    return result


class ProgramChecker:
    """Main program testing class for SeDriLa courses."""
    DEFAULT_TIMEOUT = 30
    def __init__(self, course_root: Path = None, parallel_execution: bool = True,
                 report_dir: str = None, max_workers: Optional[int] = None,
                 itreedir: Optional[Path] = None, chapterdir: Optional[Path] = None):
        """Initialize ProgramChecker."""
        self.course_root = course_root or Path.cwd()
        self.report_dir = report_dir or str(Path.cwd())
        self.results: List[ProgramTestResult] = []
        self.parallel_execution = parallel_execution
        self.max_workers = self._determine_max_workers(max_workers)
        self.itreedir = itreedir
        self.chapterdir = chapterdir

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

    def _save_command_test(self, command: Optional[str], output_lines: List[str],
                          command_tests: List[CommandTest]) -> None:
        """Helper to save a command test if command exists."""
        if command:
            output_text = '\n'.join(output_lines).strip()
            test = self._create_command_test(command, output_text)
            if test:
                command_tests.append(test)

    def parse_command_tests_from_prot(self, prot_file: Path) -> List[CommandTest]:
        """Parse all command tests from .prot file by extracting $ commands and their output."""
        try:
            content = prot_file.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError) as e:
            b.error(f"Cannot read {prot_file}: {e}")
            return []
        lines = content.split('\n')
        command_tests: List[CommandTest] = []
        current_command: Optional[str] = None
        current_output: List[str] = []
        for line in lines:
            stripped = line.strip()
            # Empty line or shell prompt: save current command if exists
            if not stripped or self._is_shell_prompt(stripped):
                self._save_command_test(current_command, current_output, command_tests)
                current_command = None
                current_output = []
                continue
            # Command line starting with $
            if stripped.startswith('$'):
                # Save previous command if exists
                self._save_command_test(current_command, current_output, command_tests)
                # Start new command
                current_command = stripped[1:].strip()
                current_output = []
                continue
            # Collect output for current command
            if current_command is not None:
                current_output.append(line)
        # Save final command if exists
        self._save_command_test(current_command, current_output, command_tests)
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

    def _is_shell_prompt(self, line: str) -> bool:
        """Check if line is a shell prompt (user@host format)."""
        # Pattern: user@host /path HH:MM:SS num
        prompt_pattern = r'^.+?[-\+\w]+@[-\+\w]+\s+[/~]\S*\s+\d\d:\d\d:\d\d\s+\d+'
        return bool(re.match(prompt_pattern, line))

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

    def _read_files_file(self, prot_file: Path) -> Tuple[Dict[str, str], Optional[Path]]:
        """Read .files file and return mapping of short names to relative paths, plus the file's directory."""
        if not self.chapterdir:
            return {}, None
        prot_name = prot_file.stem  # e.g., "go-test" from "go-test.prot"
        files_filename = f"{prot_name}.files"
        # Search within chapterdir (not project root, to avoid out/ directory)
        candidates = list(self.chapterdir.rglob(files_filename))
        for candidate in candidates:
            result = {}
            for line in candidate.read_text(encoding='utf-8').split('\n'):
                line = line.strip()
                if line:
                    short_name = Path(line).name
                    result[short_name] = line
            return result, candidate.parent
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
                # rel_path is relative to the .files file's directory
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

    def test_program(self, config: ProgramTestConfig) -> ProgramTestResult:
        """Execute tests for a single program."""
        result = ProgramTestResult(program_name=config.program_name, success=False)
        start_time = time.time()
        try:
            self._cleanup_generated_files(config.working_dir, config.program_name)
            if config.program_check_header.typ == 'manual':
                result.skipped = True
                result.skip_category = 'manual'
                result.manual_reason = config.program_check_header.manual_reason or "Manual testing required"
                return result
            # Build file mapping only if files= field is specified
            file_mapping = {}
            if config.program_check_header.files:
                file_mapping = self._build_file_name_mapping(config)
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
                        config.working_dir,
                        config.timeout
                    )
                    if actual.strip() != command_test.expected_output.strip():
                        result.actual_output = actual
                        result.expected_output = command_test.expected_output
                        result.error_message = f"Output mismatch for: {command_test.command}"
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
            self._cleanup_generated_files(config.working_dir, config.program_name)
            result.execution_time = time.time() - start_time
        return result

    def _run_command(self, command: str, working_dir: Path, timeout: int) -> str:
        """Run a command and return its output."""
        try:
            result = sp.run(
                command,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                shell=True  # Allow shell interpretation for commands
            )
            return result.stdout + result.stderr
        except sp.TimeoutExpired:
            raise TimeoutError(f"Command timed out after {timeout}s: {command}")

    def run_tests(self, configs: List[ProgramTestConfig], show_progress: bool = False) -> List[ProgramTestResult]:
        """Run all program tests."""
        if not configs:
            return []
        if self.parallel_execution and len(configs) > 1:
            return self._run_tests_parallel(configs, show_progress)
        else:
            return self._run_tests_sequential(configs, show_progress)

    def _run_tests_sequential(self, configs: List[ProgramTestConfig], show_progress: bool = False) -> List[ProgramTestResult]:
        """Run tests sequentially."""
        results = []
        for i, config in enumerate(configs, 1):
            if show_progress:
                b.info(f"Testing {config.program_name} ({i}/{len(configs)})...")
            result = self.test_program(config)
            results.append(result)
            if show_progress:
                status = "✓ PASS" if result.success else ("⊘ SKIP" if result.skipped else "✗ FAIL")
                b.info(f"  {status}")
        return results

    def _run_tests_parallel(self, configs: List[ProgramTestConfig], show_progress: bool = False) -> List[ProgramTestResult]:
        """Run tests in parallel."""
        results = []
        completed = 0
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_config = {
                executor.submit(self.test_program, config): config
                for config in configs
            }
            for future in as_completed(future_to_config):
                config = future_to_config[future]
                result = future.result()
                results.append(result)
                completed += 1
                if show_progress:
                    status = "✓" if result.success else ("⊘" if result.skipped else "✗")
                    b.info(f"  {status} {config.program_name} ({completed}/{len(configs)})")
        return results

    def collect_install_commands(self, targets: List[ProgramTestTarget]) -> List[str]:
        """Collect all install commands from @PROGRAM_CHECK blocks."""
        all_commands: List[str] = []
        for target in targets:
            header = target.program_check_header
            commands = header.get_install_commands()
            all_commands.extend(commands)
        seen = set()
        unique_commands = []
        for cmd in all_commands:
            if cmd not in seen:
                seen.add(cmd)
                unique_commands.append(cmd)
        return unique_commands

    def test_all_programs(self, targets: List[ProgramTestTarget], itree_root: Optional[Path] = None,
                         show_progress: bool = True, batch_mode: bool = False) -> List[ProgramTestResult]:
        """Test all programs from targets."""
        if itree_root is None:
            if self.itreedir:
                itree_root = self.itreedir
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
            report_lines.append("| Program | Error | Details |\n")
            report_lines.append("|---------|-------|---------||\n")
            for r in results:
                if not r.success and not r.skipped:
                    error_msg = r.error_message.replace('\n', ' ').replace('|', '\\|')[:100]
                    details = ""
                    if r.expected_output and r.actual_output:
                        details = f"Expected: `{r.expected_output[:50]}...`, Got: `{r.actual_output[:50]}...`"
                    report_lines.append(f"| `{r.program_name}` | {error_msg} | {details} |\n")
            report_lines.append("\n")
            report_lines.append("### Failed Tests Detail\n\n")
            for r in results:
                if not r.success and not r.skipped:
                    report_lines.append(f"#### {r.program_name}\n\n")
                    report_lines.append(f"- **Error:** {r.error_message}\n")
                    if r.expected_output:
                        report_lines.append(f"- **Expected output:**\n```\n{r.expected_output[:500]}\n```\n")
                    if r.actual_output:
                        report_lines.append(f"- **Actual output:**\n```\n{r.actual_output[:500]}\n```\n")
                    report_lines.append("\n")
        if skipped > 0:
            report_lines.append("## Skipped Tests (Manual Testing Required)\n\n")
            report_lines.append("| Program | Reason |\n")
            report_lines.append("|---------|--------|\n")
            for r in results:
                if r.skipped:
                    reason = r.manual_reason.replace('\n', ' ').replace('|', '\\|')
                    report_lines.append(f"| `{r.program_name}` | {reason} |\n")
            report_lines.append("\n")
        if passed > 0:
            report_lines.append("## Passed Tests\n\n")
            report_lines.append("| Program | Execution Time |\n")
            report_lines.append("|---------|----------------|\n")
            for r in results:
                if r.success:
                    report_lines.append(f"| `{r.program_name}` | {r.execution_time:.2f}s |\n")
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


