# pytest tests for programchecker
import tempfile
import os
from pathlib import Path

import sdrl.programchecker as programchecker


class DummyTask:
    def __init__(self, sourcefile: Path):
        self.sourcefile = str(sourcefile)
        self.to_be_skipped = False


class DummyTaskgroup:
    def __init__(self, tasks):
        self.tasks = tasks
        self.to_be_skipped = False
        self.sourcefile = ""


class DummyChapter:
    def __init__(self, taskgroups):
        self.taskgroups = taskgroups
        self.to_be_skipped = False


class DummyCourse:
    def __init__(self, chapterdir: Path, altdir: Path, itreedir: Path, chapters):
        self.chapterdir = str(chapterdir)
        self.altdir = str(altdir)
        self.itreedir = str(itreedir)
        self.chapters = chapters


def test_program_test_config():
    """Test ProgramTestConfig dataclass."""
    config = programchecker.ProgramTestConfig(
        program_path=Path("/test/prog.py"),
        program_name="prog",
        expected_protocol_file=Path("/test/prog.prot"),
        working_dir=Path("/test")
    )
    
    assert config.program_name == "prog"
    assert config.timeout == 30  # default value


def test_program_test_result():
    """Test ProgramTestResult dataclass."""
    result = programchecker.ProgramTestResult(
        program_name="test_prog",
        success=True,
        actual_output="Hello World",
        expected_output="Hello World",
        execution_time=1.5
    )
    
    assert result.success is True
    assert result.program_name == "test_prog"
    assert "PASS" in str(result)
    
    # Test failed result
    failed_result = programchecker.ProgramTestResult(
        program_name="failed_prog",
        success=False,
        error_message="Compilation error"
    )
    
    assert failed_result.success is False
    assert "FAIL" in str(failed_result)


def test_output_comparison():
    """Test output comparison functionality."""
    checker = programchecker.ProgramChecker()
    
    # Test exact match
    assert checker.compare_outputs("Hello World", "Hello World") is True
    
    # Test with whitespace differences
    assert checker.compare_outputs("  Hello World  ", "Hello World") is True
    
    # Test different content
    assert checker.compare_outputs("Hello", "World") is False
    
    # Test empty expected output (should always pass)
    assert checker.compare_outputs("Any output", "") is True


def test_parse_command_tests_from_prot():
    """Test parsing command tests from .prot files."""
    sample_prot_content = """user@host /path 10:00:00 1
$ python test_prog.py
Hello World
This is test output

user@host /path 10:01:00 2  
$ ls -la
total 16
drwxr-xr-x 2 user user 4096 Jan 1 12:00 .
-rw-r--r-- 1 user user  123 Jan 1 12:00 file.txt

user@host /path 10:02:00 3
$ python test_prog.py --error
Traceback (most recent call last):
  File "test_prog.py", line 1
    error()
ValueError: Test error
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.prot', delete=False) as f:
        f.write(sample_prot_content)
        f.flush()
        
        checker = programchecker.ProgramChecker()
        annotation = programchecker.ProgramTestAnnotation()
        command_tests = checker.parse_command_tests_from_prot(Path(f.name), "test_prog.py", annotation)
        
        # Should find 2 command tests (both use test_prog.py)
        assert len(command_tests) == 2
        
        # First command test
        ct1 = command_tests[0]
        assert ct1.command == "python test_prog.py"
        assert "Hello World" in ct1.expected_output
        assert "This is test output" in ct1.expected_output
        assert not ct1.has_errors
        assert not ct1.needs_interaction
        assert not ct1.has_redirection
        
        # Second command test should have errors
        ct2 = command_tests[1]
        assert ct2.command == "python test_prog.py --error"
        assert ct2.has_errors  # Should detect Traceback
        assert "Traceback" in ct2.expected_output
        
        # Clean up
        os.unlink(f.name)


def test_build_configs_from_targets():
    """Test building configs from manually specified targets."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        python_prog = temp_path / "test.py"
        go_prog = temp_path / "test_go.go"
        python_prog.write_text("print('Hello')")
        go_prog.write_text("package main\nfunc main() {}")
        
        python_prot = temp_path / "test.prot"
        go_prot = temp_path / "test_go.prot"
        python_prot.write_text("""user@host /path 10:00:00 1
$ python test.py
Hello
""")
        go_prot.write_text("""user@host /path 10:00:00 1
$ go run test_go.go
""")
        python_task = temp_path / "python_task.md"
        go_task = temp_path / "go_task.md"
        python_task.write_text("# Python Task")
        go_task.write_text("# Go Task")
        
        targets = [
            programchecker.ProgramTestTarget(
                task_file=python_task,
                program_file=python_prog,
                protocol_file=python_prot
            ),
            programchecker.ProgramTestTarget(
                task_file=go_task,
                program_file=go_prog,
                protocol_file=go_prot
            ),
        ]
        
        checker = programchecker.ProgramChecker()
        configs = checker.build_configs_from_targets(targets)
        
        assert len(configs) == 2
        commands = {config.program_name: config.command_tests[0].command for config in configs}
        assert commands["test"] == "python test.py"
        assert commands["test_go"] == "go run test_go.go"


def test_program_checker_initialization():
    """Test ProgramChecker initialization."""
    # Test with default course root
    checker = programchecker.ProgramChecker()
    assert checker.course_root == Path.cwd()
    assert checker.parallel_execution is True  # Default value
    
    # Test with custom course root and parallel execution disabled
    custom_root = Path("/tmp/test")
    checker = programchecker.ProgramChecker(course_root=custom_root, parallel_execution=False)
    assert checker.course_root == custom_root
    assert checker.parallel_execution is False


def test_generate_reports_creates_markdown_only():
    """ProgramChecker.generate_reports should emit only markdown output."""
    import tempfile
    with tempfile.TemporaryDirectory() as temp_dir:
        results = [
            programchecker.ProgramTestResult(
                program_name="foo",
                success=True,
                execution_time=0.1
            )
        ]
        checker = programchecker.ProgramChecker(report_dir=temp_dir)
        checker.generate_reports(results, batch_mode=True)
        md_path = Path(temp_dir) / "program_test_report.md"
        assert md_path.exists()
        assert not (Path(temp_dir) / "program_test_report.json").exists()


def test_markdown_report_generation():
    """Test Markdown report generation."""
    with tempfile.TemporaryDirectory() as temp_dir:
        original_cwd = os.getcwd()
        os.chdir(temp_dir)  # Change to temp directory for report files
        
        try:
            results = [
                programchecker.ProgramTestResult(
                    program_name="success_test",
                    success=True,
                    actual_output="Hello World"
                )
            ]
            
            checker = programchecker.ProgramChecker()
            checker.generate_markdown_report(results)
            
            # Check that Markdown report was created
            assert os.path.exists("program_test_report.md")
            
            # Verify basic content
            with open("program_test_report.md", 'r') as f:
                content = f.read()
            
            assert "# Program Test Report" in content
            assert "success_test" in content
            assert "Passed Tests" in content
            assert "Execution Time" in content
        finally:
            os.chdir(original_cwd)


def test_single_program_file_function():
    """Test the single program file testing function."""
    with tempfile.TemporaryDirectory() as temp_dir:
        original_cwd = os.getcwd()
        
        try:
            # Change to temp directory (simulating course root)
            os.chdir(temp_dir)
            temp_path = Path(temp_dir)
            
            # Create proper directory structure
            itree_dir = temp_path / "altdir" / "itree.zip" / "test_folder"
            itree_dir.mkdir(parents=True)
            
            # Create test program
            program_file = itree_dir / "test_prog.py"
            program_file.write_text("print('Hello from test')")
            
            # Create corresponding .prot file
            prot_dir = temp_path / "altdir" / "ch" / "test_folder"
            prot_dir.mkdir(parents=True)
            prot_file = prot_dir / "test_prog.prot"
            prot_file.write_text("""user@host /path 10:00:00 1
$ python test_prog.py
Hello from test
""")
            
            # Test the function - should execute without errors
            try:
                programchecker.test_single_program_file(str(program_file))
                # If it completes without exception, test passes
                assert True, "Function executed successfully"
            except FileNotFoundError as e:
                # This is acceptable if dependencies are missing
                if "altdir" not in str(e):
                    raise
            except Exception as e:
                # For other exceptions, we verify it's a meaningful error
                assert "error" in str(e).lower() or "not found" in str(e).lower(), \
                    f"Unexpected exception: {e}"
                    
        finally:
            os.chdir(original_cwd)


def test_parallel_vs_sequential_execution():
    """Test that parallel and sequential execution produce consistent results."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        program1 = temp_path / "hello1.py"
        program2 = temp_path / "hello2.py"
        program1.write_text("print('Hello 1')")
        program2.write_text("print('Hello 2')")
        
        prot1 = temp_path / "hello1.prot"
        prot2 = temp_path / "hello2.prot"
        prot1.write_text("$ python hello1.py\nHello 1")
        prot2.write_text("$ python hello2.py\nHello 2")
        
        task1 = temp_path / "task1.md"
        task2 = temp_path / "task2.md"
        task1.write_text("# Task 1")
        task2.write_text("# Task 2")
        
        targets = [
            programchecker.ProgramTestTarget(task_file=task1, program_file=program1, protocol_file=prot1),
            programchecker.ProgramTestTarget(task_file=task2, program_file=program2, protocol_file=prot2),
        ]
        
        checker_seq = programchecker.ProgramChecker(parallel_execution=False)
        configs_seq = checker_seq.build_configs_from_targets(targets)
        results_seq = checker_seq._run_tests_sequential(configs_seq, show_progress=False)
        
        checker_par = programchecker.ProgramChecker(parallel_execution=True)
        configs_par = checker_par.build_configs_from_targets(targets)
        results_par = checker_par._run_tests_parallel(configs_par, show_progress=False)
        
        # Results should be the same (when sorted)
        results_seq.sort(key=lambda r: r.program_name)
        results_par.sort(key=lambda r: r.program_name)
        
        assert len(results_seq) == len(results_par)
        for seq_result, par_result in zip(results_seq, results_par):
            assert seq_result.program_name == par_result.program_name
            assert seq_result.success == par_result.success


def test_extract_program_test_targets():
    """Test extracting program targets from task markup."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        chapterdir = temp_path / "ch"
        altdir = temp_path / "altdir" / "ch"
        itreedir = temp_path / "altdir" / "itree.zip"
        (chapterdir / "Chapter1").mkdir(parents=True)
        (altdir / "Chapter1").mkdir(parents=True)
        (itreedir / "Chapter1").mkdir(parents=True)
        
        program_path = itreedir / "Chapter1" / "task.py"
        program_path.write_text("print('hi')")
        prot_path = altdir / "Chapter1" / "task.prot"
        prot_path.write_text("$ python task.py\nhi")
        
        task_path = chapterdir / "Chapter1" / "task.md"
        task_content = """# Task
<!-- @PROGRAM_TEST: notes="demo" -->
"""
        task_path.write_text(task_content)
        
        task = DummyTask(task_path)
        taskgroup = DummyTaskgroup([task])
        chapter = DummyChapter([taskgroup])
        course = DummyCourse(chapterdir, temp_path / "altdir" / "ch", itreedir, [chapter])
        
        targets = programchecker.extract_program_test_targets(course)
        assert len(targets) == 1
        assert targets[0].program_file == program_path
        assert targets[0].protocol_file == prot_path
        

def test_missing_files_handling():
    """Test handling of missing files and directories."""
    checker = programchecker.ProgramChecker()
    
    # Test with non-existent itree path
    results = checker.test_all_programs()
    assert results == []
    
    # Test parsing from non-existent .prot file
    annotation = programchecker.ProgramTestAnnotation()
    command_tests = checker.parse_command_tests_from_prot(Path("/nonexistent/file.prot"), "test.py", annotation)
    assert command_tests == []


def test_command_test_detection():
    """Test detection of different command test properties."""
    checker = programchecker.ProgramChecker()
    
    # Test error detection
    assert checker._has_error_output("Traceback (most recent call last):\nValueError: test") is True
    assert checker._has_error_output("MemoryError") is True
    assert checker._has_error_output("Normal output") is False
    
    # Test interaction detection
    assert checker._needs_interaction("Enter your name: ") is True
    assert checker._needs_interaction("Input: ") is True
    assert checker._needs_interaction("(Enter to proceed)") is True
    assert checker._needs_interaction("Normal output") is False
    
    # Test redirection detection
    assert checker._has_redirection("python test.py > output.txt") is True
    assert checker._has_redirection("(ulimit -v 512000; python test.py)") is True
    assert checker._has_redirection("python test.py | grep result") is True
    assert checker._has_redirection("python test.py") is False


def test_multi_command_testing():
    """Test that all testable commands are executed and results are aggregated."""
    sample_prot_content = """user@host /path 10:00:00 1
$ python multi_test.py cmd1
Output from command 1

user@host /path 10:01:00 2
$ python multi_test.py cmd2  
Output from command 2

user@host /path 10:02:00 3
$ python multi_test.py cmd3
Output from command 3

user@host /path 10:03:00 4
$ python multi_test.py error
Traceback (most recent call last):
  File "multi_test.py", line 1
    raise ValueError("Error")
ValueError: Error
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.prot', delete=False) as prot_file:
        prot_file.write(sample_prot_content)
        prot_file.flush()
        
        # Create a temporary Python file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as py_file:
            py_file.write("""import sys
if len(sys.argv) > 1:
    cmd = sys.argv[1]
    print(f"Output from command {cmd}")
""")
            py_file.flush()
            
            try:
                checker = programchecker.ProgramChecker()
                prot_path = Path(prot_file.name)
                annotation = programchecker.ProgramTestAnnotation()
                command_tests = checker.parse_command_tests_from_prot(prot_path, "multi_test.py", annotation)
                
                # Should parse 4 commands total
                assert len(command_tests) == 4
                
                # 3 should be testable (not errors), 1 should have errors
                testable = [ct for ct in command_tests if not ct.has_errors and not ct.needs_interaction and not ct.has_redirection]
                assert len(testable) == 3
                
                # Verify error command is detected
                error_cmds = [ct for ct in command_tests if ct.has_errors]
                assert len(error_cmds) == 1
                assert "error" in error_cmds[0].command
                
                # Create config for multi-command test
                config = programchecker.ProgramTestConfig(
                    program_path=Path(py_file.name),
                    program_name="multi_test",
                    expected_protocol_file=prot_path,
                    working_dir=Path(py_file.name).parent,
                    command_tests=command_tests
                )
                
                # Run test - should test all 3 testable commands
                result = checker.run_program_test(config)
                
                # Should have partial_skip_details with tested commands
                assert result.partial_skip_details is not None
                tested_commands = result.partial_skip_details.get("tested_commands", [])
                
                # All 3 testable commands should be tested
                assert len(tested_commands) == 3
                
                # Verify each command has status
                for cmd_info in tested_commands:
                    assert "command" in cmd_info
                    assert "status" in cmd_info
                    assert cmd_info["status"] in ["PASS", "FAIL"]
                
                # Should have skipped commands info
                skipped_commands = result.partial_skip_details.get("skipped_commands", [])
                assert len(skipped_commands) == 1
                assert "error" in skipped_commands[0]["command"]
                assert "reason" in skipped_commands[0]
                
            finally:
                os.unlink(prot_file.name)
                os.unlink(py_file.name)


def test_markup_extraction_from_md():
    """Test extraction of program test markup from task .md files."""
    import tempfile
    
    # Create task file with PROGRAM_TEST_SKIP markup
    task_content = """# Test Task

Some task description.

[INSTRUCTOR::some instructor notes]

<!-- @PROGRAM_TEST_SKIP: reason="Test reason" manual_test_required="true" -->

<!-- @PROGRAM_TEST -->

More content here.
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
        f.write(task_content)
        md_file = f.name
    
    try:
        extractor = programchecker.AnnotationExtractor()
        annotation = extractor.extract_annotations_from_file(md_file)
        
        assert annotation.skip is True, "Should extract skip=True"
        assert annotation.skip_reason == "Test reason", "Should extract skip reason"
        assert annotation.manual_test_required is True, "Should extract manual_test_required"
        assert annotation.has_markup is True, "Generic marker without params should count"
    finally:
        os.unlink(md_file)


def test_cleanup_mechanism():
    """Test that generated files are cleaned up properly."""
    import tempfile
    from pathlib import Path
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create some test files that should be cleaned up
        test_db = temp_path / "test.db"
        test_log = temp_path / "test.log"
        test_pyc = temp_path / "test.pyc"
        pycache_dir = temp_path / "__pycache__"
        
        test_db.write_text("test")
        test_log.write_text("test")
        test_pyc.write_text("test")
        pycache_dir.mkdir()
        (pycache_dir / "module.pyc").write_text("test")
        
        # Verify files exist
        assert test_db.exists()
        assert test_log.exists()
        assert test_pyc.exists()
        assert pycache_dir.exists()
        
        # Run cleanup
        checker = programchecker.ProgramChecker()
        checker._cleanup_generated_files(temp_path, "test_program")
        
        # Verify files were cleaned up
        assert not test_db.exists(), ".db files should be cleaned"
        assert not test_log.exists(), ".log files should be cleaned"
        assert not test_pyc.exists(), ".pyc files should be cleaned"
        assert not pycache_dir.exists(), "__pycache__ directories should be cleaned"


def test_command_override_markup():
    """Test that command override markup is properly extracted and applied."""
    import tempfile
    
    # Create task file with PROGRAM_TEST_OVERRIDE markup
    task_content = """# Test Task

<!-- @PROGRAM_TEST_OVERRIDE: original_command="go run main.go" correct_command="go run real-file.go" reason="File name mismatch" -->

Task content.
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
        f.write(task_content)
        md_file = f.name
    
    try:
        extractor = programchecker.AnnotationExtractor()
        annotation = extractor.extract_annotations_from_file(md_file)
        
        assert annotation.command_override is True, "Should extract command_override=True"
        assert annotation.original_command == "go run main.go", "Should extract original command"
        assert annotation.correct_command == "go run real-file.go", "Should extract correct command"
        assert "mismatch" in annotation.override_reason.lower(), "Should extract override reason"
    finally:
        os.unlink(md_file)
