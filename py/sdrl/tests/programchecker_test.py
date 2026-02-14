# pytest tests for programchecker
import tempfile
import textwrap
from pathlib import Path

import sdrl.programchecker as programchecker


def _dedent(payload: str) -> str:
    return textwrap.dedent(payload).lstrip()


# Test data constants
PROGRAM_CHECK_BASIC = _dedent("""
    @TEST_SPEC
    lang=apt-get install -y python3-pip
    deps=pip install fastapi
""")

PROGRAM_CHECK_MULTILINE = _dedent("""
    @TEST_SPEC
    lang=apt-get install -y golang-go
    apt-get install -y make
    deps=go get github.com/lib/pq
    go get github.com/spf13/cobra
""")

PROT_SPEC_BASIC = _dedent("""
    @PROT_SPEC
    command_re=^python test\\.py$
    output_re=^Success$

    user@host /tmp 10:00:00 1
    $ python test.py
    Success
""")


def test_extracts_program_check_from_content():
    """Verify @TEST_SPEC block extraction from protocol content."""
    content = PROGRAM_CHECK_BASIC + "\n" + PROT_SPEC_BASIC
    header = programchecker.ProgramCheckHeaderExtractor.extract_from_content(content)
    assert header is not None
    assert header.lang == "apt-get install -y python3-pip"
    assert header.deps == "pip install fastapi"


def test_parses_multiline_lang_and_deps():
    """Verify multi-line lang and deps commands are combined."""
    content = PROGRAM_CHECK_MULTILINE + "\n" + PROT_SPEC_BASIC
    header = programchecker.ProgramCheckHeaderExtractor.extract_from_content(content)
    assert header.lang is not None
    assert "apt-get install -y golang-go" in header.lang
    assert "apt-get install -y make" in header.lang
    assert "\n" in header.lang, "Multi-line lang should contain newline"
    assert header.deps is not None
    assert "go get github.com/lib/pq" in header.deps
    assert "go get github.com/spf13/cobra" in header.deps


def test_get_install_commands_splits_deps():
    """Verify get_install_commands() splits deps by newline."""
    header = programchecker.ProgramCheckHeader(
        deps="pip install fastapi\npip install uvicorn"
    )
    commands = header.get_install_commands()
    assert len(commands) == 2, f"Expected 2 commands, got {len(commands)}"
    assert "pip install fastapi" in commands
    assert "pip install uvicorn" in commands


def test_find_program_file_by_matching_stem():
    """Verify program file is found by matching .prot stem."""
    with tempfile.TemporaryDirectory() as tmpdir:
        altdir_task = Path(tmpdir) / "altdir" / "ch" / "Python" / "basics"
        itreedir_task = Path(tmpdir) / "itreedir" / "Python" / "basics"
        altdir_task.mkdir(parents=True)
        itreedir_task.mkdir(parents=True)
        prot_file = altdir_task / "test.prot"
        prot_file.write_text(PROGRAM_CHECK_BASIC)
        prog_file = itreedir_task / "test.py"
        prog_file.write_text("print('test')")
        (itreedir_task / "test.txt").write_text("not a program")
        itreedir_root = Path(tmpdir) / "itreedir"
        found = programchecker._find_program_file(itreedir_root, prot_file)
        assert found == prog_file, f"Expected {prog_file}, got {found}"


def test_filter_program_check_annotations():
    """Verify @TEST_SPEC blocks are removed from content."""
    content = PROGRAM_CHECK_BASIC + "\n" + PROT_SPEC_BASIC + "\n$ echo done\ndone"
    filtered = programchecker.filter_program_check_annotations(content)
    assert "@TEST_SPEC" not in filtered
    assert "apt-get install" not in filtered
    assert "$ python test.py" in filtered
    assert "$ echo done" in filtered


def test_program_execution_with_regex_validation():
    """Real integration test: execute a program and validate with regex."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        altdir = tmpdir_path / "altdir" / "ch" / "Python" / "basics"
        altdir.mkdir(parents=True)
        prog_file = altdir / "hello.py"
        prog_file.write_text("print('Hello World 123')")
        prot_file = altdir / "hello.prot"
        prot_file.write_text(_dedent("""
            @TEST_SPEC

            @PROT_SPEC
            command_re=^python hello\\.py$
            output_re=Hello World \\d+
            exitcode=0

            user@host /tmp 10:00:00 1
            $ python hello.py
            Hello World 123
        """))
        header = programchecker.ProgramCheckHeaderExtractor.extract_from_file(str(prot_file))
        checker = programchecker.ProgramChecker(
            report_dir=str(tmpdir_path)
        )
        checker._altdir_path = tmpdir_path / "altdir"
        command_tests = checker.parse_command_tests_from_prot(prot_file)
        config = programchecker.ProgramTestConfig(
            program_path=prog_file,
            program_name="hello",
            protocol_file=prot_file,
            program_check_header=header,
            command_tests=command_tests
        )
        result = checker.test_program(config)
        # Verify result - when successful, regex matched correctly
        assert result.success, f"Program execution failed: {result.error_message}"
        assert result.program_name == "hello"


def test_program_execution_failure():
    """Real integration test: program fails when output or exitcode doesn't match."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        altdir = tmpdir_path / "altdir" / "ch" / "Python" / "basics"
        altdir.mkdir(parents=True)
        # --- Case 1: output_re mismatch ---
        prog_file = altdir / "test.py"
        prog_file.write_text("print('Goodbye World')")
        prot_file = altdir / "test.prot"
        prot_file.write_text(_dedent("""
            @TEST_SPEC

            @PROT_SPEC
            command_re=^python test\\.py$
            output_re=^Hello World$

            user@host /tmp 10:00:00 1
            $ python test.py
            Hello World
        """))
        header = programchecker.ProgramCheckHeaderExtractor.extract_from_file(str(prot_file))
        checker = programchecker.ProgramChecker(
            report_dir=str(tmpdir_path)
        )
        checker._altdir_path = tmpdir_path / "altdir"
        command_tests = checker.parse_command_tests_from_prot(prot_file)
        config = programchecker.ProgramTestConfig(
            program_path=prog_file,
            program_name="test",
            protocol_file=prot_file,
            program_check_header=header,
            command_tests=command_tests
        )
        result = checker.test_program(config)
        assert not result.success, "Expected test to fail due to output mismatch"
        assert "does not match regex" in result.error_message or \
               "Output does not match" in result.error_message
        # --- Case 2: exitcode mismatch ---
        prog_file2 = altdir / "exittest.py"
        prog_file2.write_text("print('OK')")  # exits with 0
        prot_file2 = altdir / "exittest.prot"
        prot_file2.write_text(_dedent("""
            @TEST_SPEC

            @PROT_SPEC
            command_re=^python exittest\\.py$
            exitcode=42

            user@host /tmp 10:00:00 1
            $ python exittest.py
            OK
        """))
        header2 = programchecker.ProgramCheckHeaderExtractor.extract_from_file(str(prot_file2))
        command_tests2 = checker.parse_command_tests_from_prot(prot_file2)
        config2 = programchecker.ProgramTestConfig(
            program_path=prog_file2,
            program_name="exittest",
            protocol_file=prot_file2,
            program_check_header=header2,
            command_tests=command_tests2
        )
        result2 = checker.test_program(config2)
        assert not result2.success, "Expected test to fail due to exitcode mismatch"
        assert "Exit code mismatch" in result2.error_message
