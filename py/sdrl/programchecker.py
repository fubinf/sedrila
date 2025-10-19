"""
Program testing functionality for SeDriLa courses.

This module provides functionality to test exemplary programs from itree.zip
against their corresponding protocol files to ensure programs can run
successfully and produce expected output.
"""

import subprocess as sp
import json
import os
import tempfile
import time
import zipfile
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
import shutil
import re

import base as b

@dataclass
class ProgramTestingConfig:
    """Configuration loaded from programchecker.yaml"""
    skip_programs: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    partial_skip_programs: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    command_override: Dict[str, Dict[str, str]] = field(default_factory=dict)
    normal_test_programs: Dict[str, Dict[str, str]] = field(default_factory=dict)
    global_settings: Dict[str, Any] = field(default_factory=dict)

@dataclass
class CommandTest:
    """Single command test extracted from .prot file"""
    command: str                    # The command to run (e.g., "go run program.go")  
    expected_output: str           # Expected output for this command
    has_errors: bool = False       # True if output contains Traceback/errors
    needs_interaction: bool = False # True if command needs user input
    has_redirection: bool = False  # True if command has >/< redirection

@dataclass
class ProgramTestConfig:
    """Configuration for testing a program (may contain multiple commands)."""
    program_path: Path
    program_name: str
    language: str
    expected_protocol_file: Path
    working_dir: Path
    command_tests: List[CommandTest] = field(default_factory=list)
    timeout: int = 30
    
@dataclass
class ProgramTestResult:
    """Result of running and testing a program."""
    program_name: str
    language: str
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
    
    def __str__(self) -> str:
        status = "PASS" if self.success else ("SKIP" if self.skipped else "FAIL")
        return f"{self.program_name} ({self.language}): {status}"

class EnvironmentChecker:
    """Check if environment requirements for running programs are satisfied."""
    
    def check_python_packages(self, packages: List[str]) -> Dict[str, Any]:
        """Check if Python packages are installed."""
        missing = []
        available = []
        
        for pkg in packages:
            try:
                __import__(pkg)
                available.append(pkg)
            except ImportError:
                missing.append(pkg)
        
        return {
            "satisfied": len(missing) == 0,
            "missing": missing,
            "available": available
        }
    
    def check_go_version(self, required_version: str = "1.20") -> Dict[str, Any]:
        """Check Go version availability."""
        try:
            result = sp.run(['go', 'version'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                # Parse version info, e.g.: "go version go1.23.4 linux/amd64"
                version_match = re.search(r'go(\d+\.\d+)', result.stdout)
                if version_match:
                    version = version_match.group(1)
                    return {
                        "satisfied": True, 
                        "version": version,
                        "output": result.stdout.strip()
                    }
            return {"satisfied": False, "error": f"Go version parse failed: {result.stdout}"}
        except FileNotFoundError:
            return {"satisfied": False, "error": "Go not installed"}
        except sp.TimeoutExpired:
            return {"satisfied": False, "error": "Go version check timeout"}

class ProgramChecker:
    """Main program testing class for SeDriLa courses."""
    
    # Supported program file extensions and their languages
    SUPPORTED_EXTENSIONS = {
        '.py': 'python',
        '.go': 'go'
    }
    
    # Default timeout for program execution
    DEFAULT_TIMEOUT = 30
    
    def __init__(self, course_root: Path = None, parallel_execution: bool = True):
        """Initialize ProgramChecker.
        
        Args:
            course_root: Root directory of the course (defaults to current directory)
            parallel_execution: Whether to run tests in parallel (default: True)
        """
        self.course_root = course_root or Path.cwd()
        self.env_checker = EnvironmentChecker()
        self.results = []
        self.skipped_programs = []  # Track programs skipped by configuration
        self.parallel_execution = parallel_execution
        self.config = self._load_config()
        
    def _load_config(self) -> ProgramTestingConfig:
        """Load configuration from programchecker.yaml"""
        config_file = Path(__file__).parent / "programchecker.yaml"
        
        if not config_file.exists():
            b.warning(f"Configuration file not found: {config_file}")
            return ProgramTestingConfig()
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            
            # Convert lists to dictionaries for easier lookup
            config = ProgramTestingConfig()
            
            # Skip programs
            if 'skip_programs' in data:
                config.skip_programs = {
                    item['program_name']: item 
                    for item in data['skip_programs']
                }
            
            # Partial skip programs
            if 'partial_skip_programs' in data and data['partial_skip_programs']:
                config.partial_skip_programs = {
                    item['program_name']: item 
                    for item in data['partial_skip_programs']
                }
            
            # Command overrides
            if 'command_override' in data:
                config.command_override = {
                    item['program_name']: item 
                    for item in data['command_override']
                }
            
            # Normal test programs
            if 'normal_test_programs' in data:
                config.normal_test_programs = {
                    item['program_name']: item 
                    for item in data['normal_test_programs']
                }
            
            # Global settings
            config.global_settings = data.get('global_settings', {})
            
            b.info(f"Loaded configuration from {config_file}")
            return config
            
        except Exception as e:
            b.error(f"Failed to load configuration from {config_file}: {e}")
            return ProgramTestingConfig()
    
    def _should_skip_program(self, program_name: str) -> Tuple[bool, str]:
        """Check if program should be completely skipped."""
        if program_name in self.config.skip_programs:
            skip_info = self.config.skip_programs[program_name]
            return True, skip_info.get('reason', 'Configured to skip')
        return False, ""
    
    def _should_skip_command(self, program_name: str, command: str, output: str) -> Tuple[bool, str]:
        """Check if specific command should be skipped."""
        if program_name in self.config.partial_skip_programs:
            skip_info = self.config.partial_skip_programs[program_name]
            skip_keywords = skip_info.get('skip_commands_with', [])
            
            for keyword in skip_keywords:
                if keyword in output:
                    return True, skip_info.get('skip_reason', f'Contains {keyword}')
        return False, ""
    
    def _get_command_override(self, program_name: str, original_command: str) -> str:
        """Get overridden command if configured."""
        if program_name in self.config.command_override:
            override_info = self.config.command_override[program_name]
            if original_command == override_info.get('original_command'):
                return override_info.get('correct_command', original_command)
        return original_command
        
    def find_program_test_pairs(self, itree_path: Path, altdir_path: Path) -> List[ProgramTestConfig]:
        """Find all program-protocol file pairs for testing."""
        configs = []
        
        if not itree_path.exists():
            b.error(f"itree directory not found: {itree_path}")
            return configs
        
        # Check if itree is a zip file or directory
        if itree_path.is_file():
            # It's a zip file, need to extract
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                try:
                    with zipfile.ZipFile(itree_path, 'r') as zip_ref:
                        zip_ref.extractall(temp_path)
                except Exception as e:
                    b.error(f"Failed to extract {itree_path}: {e}")
                    return configs
                
                itree_root = temp_path
        else:
            # It's a directory, use directly
            itree_root = itree_path
        
        # Find all program files
        program_files = []
        for pattern in self.SUPPORTED_EXTENSIONS.keys():
            program_files.extend(itree_root.rglob(f'*{pattern}'))
        
        b.info(f"Found {len(program_files)} program files in itree directory")
        
        for program_file in program_files:
            # Determine language
            language = self.SUPPORTED_EXTENSIONS.get(program_file.suffix)
            if not language:
                b.debug(f"Unsupported file type: {program_file}")
                continue
            
            # Program name without extension
            program_name = program_file.stem
            
            # Find corresponding .prot file
            # Relative path: e.g. Sprachen/Go/go-basics.go -> altdir/ch/Sprachen/Go/go-basics.prot
            rel_path = program_file.relative_to(itree_root)
            prot_path = altdir_path / "ch" / rel_path.with_suffix('.prot')
            
            if prot_path.exists():
                # Check if this program should be completely skipped
                should_skip, skip_reason = self._should_skip_program(program_name)
                if should_skip:
                    b.info(f"Skipping {program_name}: {skip_reason}")
                    # Create a skipped result for this program
                    skipped_result = ProgramTestResult(
                        program_name=program_name,
                        language=language,
                        success=False,
                        skipped=True,
                        error_message=skip_reason,
                        skip_category="config_skip"
                    )
                    self.skipped_programs.append(skipped_result)
                    continue
                
                # Parse command tests from .prot file
                command_tests = self.parse_command_tests_from_prot(prot_path, program_file.name)
                
                if command_tests:
                    config = ProgramTestConfig(
                        program_path=program_file,
                        program_name=program_name,
                        language=language,
                        expected_protocol_file=prot_path,
                        working_dir=program_file.parent,
                        command_tests=command_tests
                    )
                    configs.append(config)
                    
                    # Log command analysis
                    total_commands = len(command_tests)
                    testable_commands = len([ct for ct in command_tests if not ct.has_errors and not ct.needs_interaction and not ct.has_redirection])
                    b.debug(f"Found test pair: {program_name} ({language}) <-> {prot_path.name} ({testable_commands}/{total_commands} testable commands)")
                else:
                    b.debug(f"No testable commands found in {prot_path} for {program_name}")
            else:
                b.debug(f"No .prot file found for {program_name} at {prot_path}")
        
        # Calculate total test pairs (including skipped ones)
        total_pairs = len(configs) + len(self.skipped_programs)
        b.info(f"Found {total_pairs} program-protocol test pairs ({len(configs)} to test, {len(self.skipped_programs)} skipped by config)")
        return configs
    
    def parse_command_tests_from_prot(self, prot_file: Path, program_name: str) -> List[CommandTest]:
        """Parse all command tests from .prot file.
        
        Args:
            prot_file: Path to .prot file
            program_name: Name of the program (e.g., "go-basics.go")
            
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
                    command_test = self._create_command_test(current_command, output_text, program_name)
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
                    command_test = self._create_command_test(current_command, output_text, program_name)
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
            command_test = self._create_command_test(current_command, output_text, program_name)
            if command_test:
                command_tests.append(command_test)
        
        return command_tests
    
    def _is_shell_prompt(self, line: str) -> bool:
        """Check if line is a shell prompt (user@host pattern)."""
        return '@' in line and any(x in line for x in ['$', '#', '~', '/'])
    
    def _create_command_test(self, command: str, output: str, program_name: str) -> Optional[CommandTest]:
        """Create CommandTest object and analyze its properties."""
        
        # Check if this is a recognizable program command
        is_python_cmd = 'python' in command or 'fastapi' in command
        is_go_cmd = 'go run' in command
        
        if not (is_python_cmd or is_go_cmd):
            # Filter out test frameworks (pytest, npm, etc.) and other non-executable commands
            return None
        
        # For standard execution commands, check if it relates to our program
        # For python: program_name should be in command
        # For go: any .go file in command is acceptable (allows main.go vs go-xxx.go mismatch)
        if is_python_cmd:
            if program_name not in command:
                return None
        elif is_go_cmd:
            # For go, just check that there's a .go file mentioned
            if '.go' not in command:
                return None
        
        # Check for various flags using both hardcoded logic and configuration
        has_errors = self._has_error_output(output)
        needs_interaction = self._needs_interaction(output)
        has_redirection = self._has_redirection(command)
        
        # Additional check for configured partial skip
        prog_name = program_name.replace('.py', '').replace('.go', '')
        should_skip_cmd, _ = self._should_skip_command(prog_name, command, output)
        if should_skip_cmd:
            has_errors = True  # Mark as having errors to skip it
        
        # Apply command override if configured
        final_command = self._get_command_override(prog_name, command)
        
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
        
        # Check environment first
        if config.language == 'go':
            go_status = self.env_checker.check_go_version("1.20")
            if not go_status['satisfied']:
                return ProgramTestResult(
                    program_name=config.program_name,
                    language=config.language,
                    success=False,
                    error_message=f"Go environment check failed: {go_status.get('error', 'Unknown error')}",
                    missing_dependencies=['go'],
                    skipped=True,
                    skip_category="runtime_skip"
                )
        
        # Skip tests with errors, interaction, or redirection
        if command_test.has_errors:
            return ProgramTestResult(
                program_name=config.program_name,
                language=config.language,
                success=False,
                error_message=f"Command contains error demonstration: {command_test.command[:50]}...",
                skipped=True,
                execution_time=time.time() - start_time,
                skip_category="runtime_skip"
            )
        
        if command_test.needs_interaction:
            return ProgramTestResult(
                program_name=config.program_name,
                language=config.language,
                success=False,
                error_message=f"Command needs interactive input: {command_test.command[:50]}...",
                skipped=True,
                execution_time=time.time() - start_time,
                skip_category="runtime_skip"
            )
        
        if command_test.has_redirection:
            return ProgramTestResult(
                program_name=config.program_name,
                language=config.language,
                success=False,
                error_message=f"Command has shell redirection: {command_test.command[:50]}...",
                skipped=True,
                execution_time=time.time() - start_time,
                skip_category="runtime_skip"
            )
        
        # Extract the actual program command (remove shell complexities)
        program_cmd = self._extract_program_command(command_test.command, config)
        if not program_cmd:
            return ProgramTestResult(
                program_name=config.program_name,
                language=config.language,
                success=False,
                error_message=f"Could not extract program command from: {command_test.command}",
                skipped=True,
                execution_time=time.time() - start_time,
                skip_category="runtime_skip"
            )
        
        # Execute program
        try:
            result = sp.run(
                program_cmd,
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
                language=config.language,
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
                language=config.language,
                success=False,
                error_message=f"Program execution timeout ({config.timeout}s)",
                execution_time=time.time() - start_time
            )
        except Exception as e:
            return ProgramTestResult(
                program_name=config.program_name,
                language=config.language,
                success=False,
                error_message=f"Execution error: {str(e)}",
                execution_time=time.time() - start_time
            )
    
    def _extract_program_command(self, command_line: str, config: ProgramTestConfig) -> Optional[List[str]]:
        """Extract the actual program command from shell command line."""
        # Handle different program types
        if config.language == 'go':
            if 'go run' in command_line:
                # Extract: "go run program.go args..." -> ["go", "run", "program.go", "args..."]
                parts = command_line.split()
                if len(parts) >= 3 and parts[0] == 'go' and parts[1] == 'run':
                    # If .prot uses main.go but actual file is different, use actual file
                    go_file_in_cmd = parts[2]
                    if go_file_in_cmd == 'main.go' and config.program_path.name != 'main.go':
                        parts[2] = config.program_path.name
                    return parts[:3]  # Just "go run program.go" for now, ignore additional args
        elif config.language == 'python':
            # Handle python and fastapi commands
            if 'python' in command_line:
                # Extract: "python program.py args..." -> ["python", "program.py", "args..."]
                parts = command_line.split()
                python_idx = -1
                for i, part in enumerate(parts):
                    if 'python' in part:
                        python_idx = i
                        break
                
                if python_idx >= 0 and python_idx + 1 < len(parts):
                    # For now, include all arguments to allow proper testing
                    return parts[python_idx:]
            elif 'fastapi' in command_line:
                # Extract: "fastapi dev program.py" -> ["fastapi", "dev", "program.py"]  
                parts = command_line.split()
                if len(parts) >= 3 and parts[0] == 'fastapi':
                    return parts[:3]  # Just "fastapi dev program.py"
        
        return None
    
    def _cleanup_generated_files(self, working_dir: Path, program_name: str) -> None:
        """Clean up files generated during program testing.
        
        Args:
            working_dir: Directory where the program was executed
            program_name: Name of the program (for logging)
        """
        # List of file patterns that are typically generated during testing
        cleanup_patterns = [
            '*.db',      # SQLite databases
            '*.sqlite',  # SQLite databases (alternative extension)
            '*.sqlite3', # SQLite databases (alternative extension)
            '*.log',     # Log files
            '*.tmp',     # Temporary files
            '__pycache__', # Python cache directories
            '*.pyc',     # Python compiled files
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
                language=config.language,
                success=False,
                error_message="No command tests found in .prot file",
                skipped=True,
                execution_time=time.time() - start_time,
                skip_category="runtime_skip"
            )
        
        # Check if this is a partial skip program
        is_partial_skip = config.program_name in self.config.partial_skip_programs
        partial_skip_info = self.config.partial_skip_programs.get(config.program_name, {})
        
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
                    skip_reason = partial_skip_info.get("skip_reason", "error demonstration")
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
                    "skip_reason": partial_skip_info.get("skip_reason", ""),
                    "testable_note": partial_skip_info.get("testable_note", "")
                }
            
            # Clean up generated files even when all commands are skipped
            self._cleanup_generated_files(config.working_dir, config.program_name)
            
            return ProgramTestResult(
                program_name=config.program_name,
                language=config.language,
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
            language=config.language,
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
                "skip_reason": partial_skip_info.get("skip_reason", "") if is_partial_skip else "",
                "testable_note": partial_skip_info.get("testable_note", "") if is_partial_skip else ""
            }
        
        # Add info about multiple commands even for normal programs
        if len(tested_cmd_infos) > 1 and not final_result.partial_skip_details:
            final_result.partial_skip_details = {
                "tested_commands": tested_cmd_infos,
                "skipped_commands": skipped_commands
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
    
    def test_all_programs(self, show_progress: bool = False) -> List[ProgramTestResult]:
        """Test all programs found in itree."""
        # Find itree directory and altdir
        itree_path = self.course_root / "altdir" / "itree.zip"
        altdir = self.course_root / "altdir"
        
        # Debug: print paths for troubleshooting
        if show_progress:
            b.debug(f"Course root: {self.course_root}")
            b.debug(f"Looking for itree at: {itree_path}")
            b.debug(f"Looking for altdir at: {altdir}")
        
        if not itree_path.exists():
            b.error(f"itree directory not found at {itree_path}")
            return []
        
        if not altdir.exists():
            b.error(f"altdir not found at {altdir}")
            return []
        
        # Get all test configurations
        configs = self.find_program_test_pairs(itree_path, altdir)
        
        # Calculate total programs (testable + skipped)
        total_programs = len(configs) + len(self.skipped_programs)
        
        if total_programs == 0:
            b.warning("No program-protocol test pairs found")
            return []
        
        results = []
        
        b.info(f"Starting program tests for {total_programs} programs...")
        b.info(f"  - {len(configs)} programs to test")
        b.info(f"  - {len(self.skipped_programs)} programs skipped by configuration")
        
        if self.parallel_execution and len(configs) > 1:
            results = self._run_tests_parallel(configs, show_progress)
        else:
            results = self._run_tests_sequential(configs, show_progress)
        
        # Combine test results with skipped programs for complete statistics
        all_results = results + self.skipped_programs
        self.results = all_results
        return all_results
    
    def _run_tests_sequential(self, configs: List[ProgramTestConfig], show_progress: bool) -> List[ProgramTestResult]:
        """Run tests sequentially."""
        results = []
        
        # Calculate offset for progress display (account for skipped programs)
        offset = len(self.skipped_programs)
        
        for i, config in enumerate(configs):
            if show_progress:
                # Adjust progress to account for total programs including skipped ones
                progress = f"[{i+1+offset}/{len(configs)+offset}]"
                b.info(f"{progress} Testing {config.program_name} ({config.language})...")
            
            result = self.run_program_test(config)
            results.append(result)
            
            if show_progress:
                status = "PASS" if result.success else ("SKIP" if result.skipped else "FAIL")
                b.info(f"{progress} {config.program_name}: {status}")
        
        return results
    
    def _run_tests_parallel(self, configs: List[ProgramTestConfig], show_progress: bool) -> List[ProgramTestResult]:
        """Run tests in parallel using ThreadPoolExecutor."""
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
                    
                    if show_progress:
                        progress = f"[{completed_count+offset}/{total_programs}]"
                        status = "PASS" if result.success else ("SKIP" if result.skipped else "FAIL")
                        b.info(f"{progress} {config.program_name}: {status}")
                        
                except Exception as e:
                    # Create a failed result for any exception during execution
                    error_result = ProgramTestResult(
                        program_name=config.program_name,
                        language=config.language,
                        success=False,
                        error_message=f"Test execution failed: {str(e)}"
                    )
                    results.append(error_result)
                    
                    if show_progress:
                        progress = f"[{completed_count+offset}/{total_programs}]"
                        b.error(f"{progress} {config.program_name}: ERROR - {str(e)}")
        
        # Sort results by program name for consistent output
        results.sort(key=lambda r: r.program_name)
        return results
    
    def generate_reports(self, results: List[ProgramTestResult] = None) -> None:
        """Generate test reports."""
        if results is None:
            results = self.results
        
        # Generate JSON report
        self.generate_json_report(results)
        
        # Generate Markdown report
        self.generate_markdown_report(results)
        
        # Print summary
        self.print_summary(results)
    
    def generate_json_report(self, results: List[ProgramTestResult]) -> None:
        """Generate JSON report."""
        failed_tests = [r for r in results if not r.success and not r.skipped]
        skipped_tests = [r for r in results if r.skipped]
        passed_tests = [r for r in results if r.success]
        
        report_data = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_tests": len(results),
            "passed": len(passed_tests),
            "failed": len(failed_tests),
            "skipped": len(skipped_tests),
            "total_execution_time": sum(r.execution_time for r in results),
            "failed_tests": [
                {
                    "program_name": r.program_name,
                    "language": r.language,
                    "error_message": r.error_message,
                    "execution_time": r.execution_time,
                }
                for r in failed_tests
            ],
            "skipped_tests": [
                {
                    "program_name": r.program_name,
                    "language": r.language,
                    "skip_reason": r.error_message,
                    "skip_category": r.skip_category,
                }
                for r in skipped_tests
            ],
            "passed_tests": [
                {
                    "program_name": r.program_name,
                    "language": r.language,
                    "execution_time": r.execution_time,
                }
                for r in passed_tests
            ],
            "all_results": [
                {
                    "program_name": r.program_name,
                    "language": r.language,
                    "success": r.success,
                    "skipped": r.skipped,
                    "execution_time": r.execution_time,
                    "exit_code": r.exit_code,
                    "error_message": r.error_message,
                    "missing_dependencies": r.missing_dependencies,
                    "actual_output_preview": r.actual_output[:200] if r.actual_output else "",
                    "expected_output_preview": r.expected_output[:200] if r.expected_output else ""
                }
                for r in results
            ]
        }
        
        report_file = "program_test_report.json"
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
            b.info(f"JSON report saved to: {report_file}")
        except Exception as e:
            b.error(f"Failed to save JSON report: {e}")
    
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
- **Skipped (config)**: {len(skipped_config)}
- **Skipped (runtime)**: {len(skipped_runtime)}
- **Success Rate**: {(len(passed_tests) / len(results) * 100):.1f}%

## Failed Tests
"""
        
        if failed_tests:
            for result in failed_tests:
                report_content += f"""
### {result.program_name} ({result.language})

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
        
        report_content += "\n## Skipped Tests (by configuration)\n"
        
        if skipped_config:
            for result in skipped_config:
                report_content += f"""
### {result.program_name} ({result.language})

- **Reason**: {result.error_message}

"""
        else:
            report_content += "\nNo tests skipped by configuration.\n"
        
        if skipped_runtime:
            report_content += "\n## Skipped Tests (at runtime)\n"
            for result in skipped_runtime:
                deps = f" [Missing: {', '.join(result.missing_dependencies)}]" if result.missing_dependencies else ""
                report_content += f"""
### {result.program_name} ({result.language})

- **Reason**: {result.error_message}{deps}

"""
        
        report_content += "\n## Passed Tests\n"
        
        if passed_tests:
            for result in passed_tests:
                report_content += f"""
### {result.program_name} ({result.language})

- **Execution Time**: {result.execution_time:.2f}s

"""
        else:
            report_content += "\nNo passed tests.\n"
        
        report_file = "program_test_report.md"
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report_content)
            b.info(f"Markdown report saved to: {report_file}")
        except Exception as e:
            b.error(f"Failed to save Markdown report: {e}")
    
    def print_summary(self, results: List[ProgramTestResult]) -> None:
        """Print test summary."""
        if not results:
            b.info("No program tests were executed.")
            return
        
        passed = sum(1 for r in results if r.success)
        failed = sum(1 for r in results if not r.success and not r.skipped)
        skipped_config = sum(1 for r in results if r.skipped and r.skip_category == "config_skip")
        skipped_partial = sum(1 for r in results if r.skip_category == "partial_skip")
        skipped_runtime = sum(1 for r in results if r.skipped and r.skip_category == "runtime_skip")
        total_time = sum(r.execution_time for r in results)
        
        b.info("=" * 60)
        b.info("PROGRAM TEST SUMMARY")
        b.info("=" * 60)
        b.info(f"Total Programs: {len(results)}")
        b.info(f"  - Passed:      {passed}")
        b.info(f"  - Failed:      {failed}")
        b.info(f"  - Skipped (config): {skipped_config}")
        b.info(f"  - Partial Skip: {skipped_partial}")
        b.info(f"  - Skipped (runtime): {skipped_runtime}")
        b.info(f"Success Rate: {(passed / len(results) * 100):.1f}%")
        if total_time > 0:
            b.info(f"Test Execution Time: {total_time:.2f}s")
        
        if failed > 0:
            b.info("")
            b.info("Failed Tests:")
            for result in results:
                if not result.success and not result.skipped:
                    b.info(f"  FAIL: {result.program_name} ({result.language}): {result.error_message}")
        
        if skipped_config > 0:
            b.info("")
            b.info("Skipped Tests (by configuration):")
            for result in results:
                if result.skipped and result.skip_category == "config_skip":
                    b.info(f"  SKIP: {result.program_name} ({result.language}): {result.error_message}")
        
        if skipped_partial > 0:
            b.info("")
            b.info("Partial Skip Tests (some commands tested, some skipped):")
            for result in results:
                if result.skip_category == "partial_skip" and result.partial_skip_details:
                    details = result.partial_skip_details
                    tested = details.get("tested_commands", [])
                    skipped = details.get("skipped_commands", [])
                    skip_reason = details.get("skip_reason", "")
                    testable_note = details.get("testable_note", "")
                    
                    status = "PASS" if result.success else "FAIL"
                    b.info(f"  {status}: {result.program_name} ({result.language})")
                    
                    if tested:
                        b.info(f"      ✓ Tested Commands ({len(tested)}):")
                        for cmd_info in tested:
                            b.info(f"        - [{cmd_info['status']}] {cmd_info['command']}")
                    
                    if skipped:
                        b.info(f"      ✗ Requires Manual Testing ({len(skipped)}):")
                        for cmd_info in skipped:
                            b.info(f"        - {cmd_info['command']}")
                        if skip_reason:
                            b.info(f"        Reason: {skip_reason}")
                    
                    if testable_note:
                        b.info(f"      Note: {testable_note}")
        
        if skipped_runtime > 0:
            b.info("")
            b.info("Skipped Tests (at runtime):")
            for result in results:
                if result.skipped and result.skip_category == "runtime_skip":
                    deps = ", ".join(result.missing_dependencies) if result.missing_dependencies else "N/A"
                    b.info(f"  SKIP: {result.program_name} ({result.language}): {result.error_message} [Missing: {deps}]")
        
        b.info("=" * 60)


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
        
        # Determine program name and language
        program_name = program_file.stem
        language = checker.SUPPORTED_EXTENSIONS.get(program_file.suffix)
        
        if not language:
            b.error(f"Unsupported file type: {program_file.suffix}")
            return
        
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
        
        # Parse command tests from .prot file
        command_tests = checker.parse_command_tests_from_prot(prot_path, program_file.name)
        
        if not command_tests:
            b.warning(f"No testable commands found in {prot_path}")
            return
        
        # Create test configuration
        config = ProgramTestConfig(
            program_path=program_file,
            program_name=program_name,
            language=language,
            expected_protocol_file=prot_path,
            working_dir=program_file.parent,
            command_tests=command_tests
        )
        
        # Run the test
        b.info(f"Running test for {program_name} ({language})")
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
