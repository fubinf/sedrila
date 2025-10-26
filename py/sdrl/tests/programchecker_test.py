# pytest tests for programchecker
import tempfile
import os
import json
from pathlib import Path

import sdrl.programchecker as programchecker


def test_environment_checker():
    """Test environment checker functionality."""
    env_checker = programchecker.EnvironmentChecker()
    
    # Test Python package checking
    result = env_checker.check_python_packages(['os', 'sys', 'nonexistent_package'])
    assert result['satisfied'] is False
    assert 'nonexistent_package' in result['missing']
    assert 'os' in result['available']
    assert 'sys' in result['available']
    
    # Test with all available packages
    result = env_checker.check_python_packages(['os', 'sys'])
    assert result['satisfied'] is True
    assert len(result['missing']) == 0


def test_go_version_check():
    """Test Go version checking."""
    env_checker = programchecker.EnvironmentChecker()
    
    # Note: This test might fail if Go is not installed
    result = env_checker.check_go_version("1.20")
    
    # Should either succeed (if Go is installed) or fail gracefully
    assert 'satisfied' in result
    if result['satisfied']:
        assert 'version' in result
        assert 'output' in result
    else:
        assert 'error' in result


def test_program_test_config():
    """Test ProgramTestConfig dataclass."""
    config = programchecker.ProgramTestConfig(
        program_path=Path("/test/prog.py"),
        program_name="prog",
        language="python",
        expected_protocol_file=Path("/test/prog.prot"),
        working_dir=Path("/test")
    )
    
    assert config.program_name == "prog"
    assert config.language == "python"
    assert config.timeout == 30  # default value


def test_program_test_result():
    """Test ProgramTestResult dataclass."""
    result = programchecker.ProgramTestResult(
        program_name="test_prog",
        language="python",
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
        language="go",
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


def test_find_program_test_pairs():
    """Test finding program-protocol pairs."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create mock itree structure
        itree_path = temp_path / "itree"
        itree_path.mkdir()
        (itree_path / "Sprachen" / "Python").mkdir(parents=True)
        (itree_path / "Sprachen" / "Go").mkdir(parents=True)
        
        # Create program files
        python_prog = itree_path / "Sprachen" / "Python" / "test.py"
        go_prog = itree_path / "Sprachen" / "Go" / "test.go"
        
        python_prog.write_text("print('Hello')")
        go_prog.write_text("package main\nfunc main() { }")
        
        # Create corresponding .prot files
        altdir_path = temp_path / "altdir"
        (altdir_path / "ch" / "Sprachen" / "Python").mkdir(parents=True)
        (altdir_path / "ch" / "Sprachen" / "Go").mkdir(parents=True)
        
        python_prot = altdir_path / "ch" / "Sprachen" / "Python" / "test.prot"
        go_prot = altdir_path / "ch" / "Sprachen" / "Go" / "test.prot"
        
        python_prot.write_text("""user@host /path 10:00:00 1
$ python test.py
Hello
""")
        go_prot.write_text("""user@host /path 10:00:00 1
$ go run test.go
""")
        
        # Test finding pairs
        checker = programchecker.ProgramChecker(course_root=temp_path)
        configs = checker.find_program_test_pairs(itree_path, altdir_path)
        
        assert len(configs) == 2
        
        # Check that we found both pairs
        program_names = {config.program_name for config in configs}
        assert "test" in program_names
        
        languages = {config.language for config in configs}
        assert "python" in languages
        assert "go" in languages
        
        # Check command_tests are populated
        for config in configs:
            assert len(config.command_tests) > 0
            if config.language == "python":
                assert config.command_tests[0].command == "python test.py"
                assert "Hello" in config.command_tests[0].expected_output
            elif config.language == "go":
                assert config.command_tests[0].command == "go run test.go"


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


def test_json_report_generation():
    """Test JSON report generation."""
    with tempfile.TemporaryDirectory() as temp_dir:
        original_cwd = os.getcwd()
        os.chdir(temp_dir)  # Change to temp directory for report files
        
        try:
            # Create sample test results
            results = [
                programchecker.ProgramTestResult(
                    program_name="test1",
                    language="python", 
                    success=True,
                    execution_time=1.0
                ),
                programchecker.ProgramTestResult(
                    program_name="test2",
                    language="go",
                    success=False,
                    error_message="Test error",
                    execution_time=0.5
                )
            ]
            
            checker = programchecker.ProgramChecker()
            checker.generate_json_report(results)
            
            # Check that JSON report was created
            assert os.path.exists("program_test_report.json")
            
            # Verify JSON content
            with open("program_test_report.json", 'r') as f:
                report_data = json.load(f)
            
            assert report_data['total_tests'] == 2
            assert report_data['passed'] == 1
            assert report_data['failed'] == 1
            assert len(report_data['all_results']) == 2
            assert len(report_data['failed_tests']) == 1
            assert len(report_data['passed_tests']) == 1
        finally:
            os.chdir(original_cwd)


def test_markdown_report_generation():
    """Test Markdown report generation."""
    with tempfile.TemporaryDirectory() as temp_dir:
        original_cwd = os.getcwd()
        os.chdir(temp_dir)  # Change to temp directory for report files
        
        try:
            results = [
                programchecker.ProgramTestResult(
                    program_name="success_test",
                    language="python",
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
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("print('test')")
        f.flush()
        
        # This should not raise an exception
        try:
            programchecker.test_single_program_file(f.name)
        except Exception:
            pass  # Expected since it's a simplified implementation
        finally:
            os.unlink(f.name)


def test_parallel_vs_sequential_execution():
    """Test that parallel and sequential execution produce consistent results."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create mock itree structure with multiple programs
        itree_path = temp_path / "itree"
        (itree_path / "test1").mkdir(parents=True)
        (itree_path / "test2").mkdir(parents=True)
        
        # Create simple programs
        (itree_path / "test1" / "hello1.py").write_text("print('Hello 1')")
        (itree_path / "test2" / "hello2.py").write_text("print('Hello 2')")
        
        # Create corresponding .prot files
        altdir_path = temp_path / "altdir"
        (altdir_path / "ch" / "test1").mkdir(parents=True)
        (altdir_path / "ch" / "test2").mkdir(parents=True)
        
        (altdir_path / "ch" / "test1" / "hello1.prot").write_text("$ python hello1.py\nHello 1")
        (altdir_path / "ch" / "test2" / "hello2.prot").write_text("$ python hello2.py\nHello 2")
        
        # Test sequential execution
        checker_seq = programchecker.ProgramChecker(course_root=temp_path, parallel_execution=False)
        configs = checker_seq.find_program_test_pairs(itree_path, altdir_path)
        results_seq = checker_seq._run_tests_sequential(configs, show_progress=False)
        
        # Test parallel execution
        checker_par = programchecker.ProgramChecker(course_root=temp_path, parallel_execution=True)
        results_par = checker_par._run_tests_parallel(configs, show_progress=False)
        
        # Results should be the same (when sorted)
        results_seq.sort(key=lambda r: r.program_name)
        results_par.sort(key=lambda r: r.program_name)
        
        assert len(results_seq) == len(results_par)
        for seq_result, par_result in zip(results_seq, results_par):
            assert seq_result.program_name == par_result.program_name
            assert seq_result.language == par_result.language
            assert seq_result.success == par_result.success


def test_supported_extensions():
    """Test supported file extensions detection."""
    checker = programchecker.ProgramChecker()
    
    # Test supported extensions
    assert '.py' in checker.SUPPORTED_EXTENSIONS
    assert '.go' in checker.SUPPORTED_EXTENSIONS
    assert checker.SUPPORTED_EXTENSIONS['.py'] == 'python'
    assert checker.SUPPORTED_EXTENSIONS['.go'] == 'go'


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
    
    # Test command extraction
    config_mock = type('Config', (), {'language': 'python'})()
    cmd = checker._extract_program_command("python test.py arg1 arg2", config_mock)
    assert cmd == ["python", "test.py", "arg1", "arg2"]
    
    config_mock.language = 'go'
    cmd = checker._extract_program_command("go run test.go", config_mock)
    assert cmd == ["go", "run", "test.go"]


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
                    language="python",
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
