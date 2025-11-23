# pytest tests
import os
import tempfile
import types
import yaml
import zipfile
from textwrap import dedent # for code formatting

import sdrl.macros as macros
import sdrl.snippetchecker as snippetchecker

def _prepare_relative_file(base_dir: str, relative_path: str, content: str | None = None) -> str:
    """Ensure the relative file exists (and optionally write content)."""
    path = os.path.join(base_dir, relative_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if content is not None:
        with open(path, 'w', encoding='utf-8') as handle:
            handle.write(content)
    return path


def _macro_text(filespec: str, snippet_id: str) -> str:
    """Return the literal macro text for a filespec + snippet combination."""
    filespec_display = filespec.rstrip(':')
    return f"[SNIPPET::{filespec_display}::{snippet_id}]"


def _create_macrocall(
    task_file: str,
    filespec: str,
    snippet_id: str,
    macro_text: str | None = None
    ) -> tuple[types.SimpleNamespace, macros.Macrocall]:
    """Create a Macrocall along with its markdown mock object."""
    text = macro_text or _macro_text(filespec, snippet_id)
    md_mock = types.SimpleNamespace(includefiles=set())
    macrocall = macros.Macrocall(
        md=md_mock,
        filename=task_file,
        partname="lesson_task",
        macrocall_text=text,
        macroname="SNIPPET",
        arg1=filespec,
        arg2=snippet_id
    )
    return md_mock, macrocall


class MockCourse:
    """Mock course object for testing snippet functionality."""
    def __init__(
        self,
        configfile: str,
        chapterdir: str = "ch",
        altdir: str = "altdir"
    ):
        base_dir = os.path.dirname(configfile)
        self.configfile = configfile
        self.chapterdir = chapterdir
        self.altdir = altdir
        self.itreedir = os.path.join(base_dir, "itreedir")
        self.targetdir_i = os.path.join(base_dir, "out", "instructor")


def _create_test_config(
    base_dir: str,
    chapterdir: str = "ch",
    altdir: str = "altdir"
    ) -> str:
    """Create a minimal sedrila.yaml config file for testing."""
    config = {
        'title': 'Test Course',
        'name': 'test-course',
        'chapterdir': chapterdir,
        'altdir': altdir,
        'stages': ['draft', 'alpha', 'beta'],
        'instructors': [],
        'allowed_attempts': '2',
        'chapters': []
    }
    config_path = os.path.join(base_dir, 'sedrila.yaml')
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f)
    return config_path


def test_snippet_extraction():
    """Test basic snippet extraction from solution files with inline comment syntax."""
    sample_content = """# Example solution file
    def helper_function():
        return "helper"

    # SNIPPET::basic_loop
    for i in range(10):
        print(f"Number: {i}")
    # ENDSNIPPET

    def another_function():
        pass

    # SNIPPET::function_example lang=python
    def calculate_sum(a, b):
        return a + b

    result = calculate_sum(5, 3)
    print(result)
    # ENDSNIPPET

    # Rest of the file
    print("End of file")
    """
    
    extractor = snippetchecker.SnippetExtractor()
    snippets, errors = extractor.extract_snippets_from_content(sample_content, "test.py", collect_errors=False)
    assert len(errors) == 0, f"Expected no errors, got {len(errors)}: {errors}"
    assert len(snippets) == 2, f"Expected 2 snippets, got {len(snippets)}"
    snippet1 = snippets[0]
    assert snippet1.snippet_id == "basic_loop", f"Expected 'basic_loop', got '{snippet1.snippet_id}'"
    assert "for i in range(10):" in snippet1.content, "Expected loop content in snippet"
    assert snippet1.language is None, "First snippet should have no language specified"
    snippet2 = snippets[1]
    assert snippet2.snippet_id == "function_example", f"Expected 'function_example', got '{snippet2.snippet_id}'"
    assert "def calculate_sum(a, b):" in snippet2.content, "Expected function content in snippet"
    assert snippet2.language == "python", f"Expected language 'python', got '{snippet2.language}'"


def test_snippet_reference_extraction_macro():
    """Test extraction of snippet references from SNIPPET macros."""
    sample_content = f"""Intro text
    {_macro_text("ALT:", "basic_loop")}
    Inline example {_macro_text("ALT:examples/demo.py", "function_example")}
    Relative reuse {_macro_text("lesson/solution.py", "helper_example")}
    """

    ref_extractor = snippetchecker.SnippetReferenceExtractor()
    references = ref_extractor.extract_references_from_content(sample_content, "task.md")
    assert len(references) == 3, "Should find three snippet references"
    assert references[0].snippet_id == "basic_loop"
    assert references[0].filespec == "ALT:"
    assert references[1].snippet_id == "function_example"
    assert references[1].filespec == "ALT:examples/demo.py"
    assert references[2].snippet_id == "helper_example"
    assert references[2].filespec == "lesson/solution.py"


def test_snippet_validation_success():
    """Test successful snippet validation when SNIPPET macro references are valid."""
    solution_content = """# SNIPPET::test_snippet
    def test_function():
        return "Hello, World!"
    # ENDSNIPPET
    """
    task_content = _macro_text("ALT:", "test_snippet")
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = _create_test_config(temp_dir)
        _prepare_relative_file(temp_dir, os.path.join("altdir", "lesson", "task.md"), solution_content)
        task_file = _prepare_relative_file(
            temp_dir,
            os.path.join("ch", "lesson", "task.md"),
            task_content
        )
        mock_course = MockCourse(config_path)
        validator = snippetchecker.SnippetValidator()
        results = validator.validate_file_references(task_file, mock_course)
        assert len(results) == 1, f"Expected 1 result, got {len(results)}"
        result = results[0]
        assert result.success, f"Validation should succeed, got error: {result.error_message}"
        assert result.snippet is not None, "Should have snippet details"
        assert result.snippet.snippet_id == "test_snippet", "Should have correct snippet ID"
        assert "def test_function():" in result.snippet.content, "Should have correct snippet content"


def test_snippet_validation_missing_file():
    """Test snippet validation when referenced file doesn't exist."""
    with tempfile.TemporaryDirectory() as temp_dir:
        task_file = _prepare_relative_file(
            temp_dir,
            os.path.join("ch", "lesson", "task.md"),
            _macro_text("ALT:", "missing_snippet")
        )
        config_path = _create_test_config(temp_dir)
        mock_course = MockCourse(config_path)
        validator = snippetchecker.SnippetValidator()
        results = validator.validate_file_references(task_file, mock_course)
        assert len(results) == 1, f"Expected 1 result, got {len(results)}"
        result = results[0]
        assert not result.success, "Validation should fail for missing file"
        assert "not found" in result.error_message.lower(), f"Error should mention missing file: {result.error_message}"


def test_snippet_validation_missing_snippet():
    """Test snippet validation when snippet ID doesn't exist in file."""
    solution_content = """<!-- SNIPPET::other_snippet -->
    def other_function():
        pass
    <!-- ENDSNIPPET -->
    """
    task_content = _macro_text("ALT:", "missing_snippet")
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = _create_test_config(temp_dir)
        _prepare_relative_file(temp_dir, os.path.join("altdir", "lesson", "task.md"), solution_content)
        task_file = _prepare_relative_file(
            temp_dir,
            os.path.join("ch", "lesson", "task.md"),
            task_content
        )
        mock_course = MockCourse(config_path)
        validator = snippetchecker.SnippetValidator()
        results = validator.validate_file_references(task_file, mock_course)
        assert len(results) == 1, f"Expected 1 result, got {len(results)}"
        result = results[0]
        assert not result.success, "Validation should fail for missing snippet"
        assert "missing_snippet" in result.error_message, f"Error should mention missing snippet: {result.error_message}"
        assert "other_snippet" in result.error_message, f"Error should list available snippets: {result.error_message}"


def test_snippet_marker_validation():
    """Test validation of snippet markers in files."""
    # Valid content
    valid_content = """# Valid file
    # SNIPPET::snippet1
    code here
    # ENDSNIPPET

    // SNIPPET::snippet2 lang=python
    more code
    // ENDSNIPPET
    """
    # Invalid content (unclosed snippet)
    invalid_content = """# Invalid file
    # SNIPPET::unclosed_snippet
    code here
    code there
    # This snippet is never closed
    """
    validator = snippetchecker.SnippetValidator()
    # valid
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', encoding='utf-8') as f:
        f.write(valid_content)
        f.flush()
        os.fsync(f.fileno())
        valid_file = f.name
        errors = validator._validate_snippet_markers_in_file(valid_file)
        assert len(errors) == 0, f"Expected no errors for valid content, got {len(errors)}: {errors}"
    # invalid
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', encoding='utf-8') as f:
        f.write(invalid_content)
        f.flush()
        os.fsync(f.fileno())
        invalid_file = f.name
        errors = validator._validate_snippet_markers_in_file(invalid_file)
        assert len(errors) > 0, f"Expected errors for invalid content, got {len(errors)}"


def test_nested_and_overlapping_snippets():
    """Test handling of nested and overlapping snippet markers."""
    # nested snippets (should support both snippets)
    nested_content = dedent(
        """\
        # File with nested snippets
        # SNIPPET::outer
        outer code
        // SNIPPET::inner
        inner code
        // ENDSNIPPET::inner
        more outer code
        # ENDSNIPPET::outer
        """
    )
    # overlapping snippets (should report errors)
    overlapping_content = dedent(
        """\
        # File with overlapping snippets
        # SNIPPET::first
        first code
        # SNIPPET::second
        overlapping code
        # ENDSNIPPET::first
        more second code
        # ENDSNIPPET::second
        """
    )
    extractor = snippetchecker.SnippetExtractor()
    nested_snippets, nested_errors = extractor.extract_snippets_from_content(
        nested_content,
        "nested.py",
        collect_errors=True
    )
    snippet_ids = {s.snippet_id for s in nested_snippets}
    assert nested_errors == [], f"Nested snippets should not raise errors: {nested_errors}"
    assert snippet_ids == {"outer", "inner"}, f"Expected both snippets, got {snippet_ids}"
    overlapping_snippets, overlap_errors = extractor.extract_snippets_from_content(
        overlapping_content,
        "overlapping.py",
        collect_errors=True
    )
    assert isinstance(overlapping_snippets, list), "Should return list of snippets"
    assert overlap_errors, "Overlapping snippets should report errors"
    error_text = " ".join(overlap_errors).lower()
    assert "mismatch" in error_text, f"Expected mismatch error message, got: {overlap_errors}"


def test_multiple_references_in_single_file():
    """Test handling multiple snippet references in a single task file."""
    task_content = """# Complex Task

    First, implement the helper:
    [SNIPPET::ALT:utils.py::helper]

    Then use it in the main function:
    [SNIPPET::ALT:solution.py::main_function]

    And add error handling:
    [SNIPPET::ALT:solution.py::error_handling]

    Finally, test it:
    [SNIPPET::tests.py::test_case]
    """
    ref_extractor = snippetchecker.SnippetReferenceExtractor()
    references = ref_extractor.extract_references_from_content(task_content, "complex_task.md")
    assert len(references) == 4, f"Expected 4 references, got {len(references)}"
    # Check all references are found
    expected_refs = [
        ("helper", "ALT:utils.py"),
        ("main_function", "ALT:solution.py"),
        ("error_handling", "ALT:solution.py"),
        ("test_case", "tests.py")
    ]
    actual_refs = [(r.snippet_id, r.filespec) for r in references]
    for expected in expected_refs:
        assert expected in actual_refs, f"Expected reference {expected} not found in {actual_refs}"


def test_directory_validation():
    """Test validation of all snippets in a directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create multiple files with various snippet scenarios
        valid_file = os.path.join(temp_dir, "valid.py")
        with open(valid_file, 'w') as f:
            f.write("""<!-- SNIPPET::valid_snippet -->
    def valid_function():
        pass
    <!-- ENDSNIPPET -->
    """)
        invalid_file = os.path.join(temp_dir, "invalid.py")
        with open(invalid_file, 'w') as f:
            f.write("""<!-- SNIPPET::unclosed_snippet -->
    def broken_function():
        pass
    # Missing end marker
    """)
        # File without snippets
        no_snippet_file = os.path.join(temp_dir, "no_snippets.py")
        with open(no_snippet_file, 'w') as f:
            f.write("""def normal_function():
                pass
            """)
        validator = snippetchecker.SnippetValidator()
        file_errors = validator.validate_directory_snippets(temp_dir)
        assert valid_file not in file_errors or not file_errors[valid_file], "Valid file should have no errors"
        assert invalid_file in file_errors and file_errors[invalid_file], "Invalid file should have errors"
        assert no_snippet_file not in file_errors or not file_errors[no_snippet_file], "File without snippets should have no errors"


def test_snippet_macro_expansion_records_dependency():
    """[SNIPPET::...] should expand and record includefiles just like INCLUDE."""
    solution_content = """# SNIPPET::macro_snip
    def from_macro():
        return 7 * 6
    # ENDSNIPPET
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        answer_file = _prepare_relative_file(temp_dir, os.path.join("altdir", "lesson", "task.md"), solution_content)
        task_file = _prepare_relative_file(temp_dir, os.path.join("ch", "lesson", "task.md"), "Task content")
        config_path = _create_test_config(temp_dir)
        course = MockCourse(config_path)
        md_mock, macrocall = _create_macrocall(task_file, "ALT:", "macro_snip")
        result = snippetchecker.expand_snippet_macro(course, macrocall)
        assert "return 7 * 6" in result
        expected_path = os.path.normpath(answer_file)
        assert expected_path in md_mock.includefiles


def test_snippet_macro_itree_zip_extraction():
    """ITREE snippets should work even if the configured itreedir is a zip file."""
    snippet_source = """# SNIPPET::zip_snip
    print("from zip")
    # ENDSNIPPET
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        chapter_rel_path = os.path.join("ch", "Basis", "IDE", "task.md")
        task_file = _prepare_relative_file(temp_dir, chapter_rel_path, "Task content")
        os.makedirs(os.path.join(temp_dir, "out", "instructor"), exist_ok=True)
        config_path = _create_test_config(temp_dir)
        zip_path = os.path.join(temp_dir, "itree.zip") # Write zipped itreedir
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr("Basis/IDE/code.py", snippet_source)
        course = types.SimpleNamespace(
            configfile=config_path,
            chapterdir="ch",
            altdir="altdir",
            itreedir="itree.zip",
            targetdir_i="out/instructor"
        )
        itree_filespec = "ITREE:/Basis/IDE/code.py"
        errors = []
        snippet, fullpath = snippetchecker._load_snippet(
            "zip_snip",
            itree_filespec,
            task_file,
            course,
            notify_error=errors.append
        )
        assert not errors, f"Unexpected errors: {errors}"
        assert snippet is not None, "Should load snippet from zipped itreedir"
        assert 'print("from zip")' in snippet.content
        expected_extracted = os.path.join(temp_dir, "out", "instructor", "itree", "Basis", "IDE", "code.py")
        assert os.path.exists(expected_extracted), "Expected extracted itree file"
        assert os.path.normpath(fullpath) == os.path.normpath(expected_extracted)


def test_snippet_macro_with_lang_wraps_code_block():
    """Snippet with lang metadata should be wrapped in fenced block."""
    solution_content = dedent(
        """\
        # SNIPPET::macro_lang lang=python
        print("wrapped")
        # ENDSNIPPET
        """
    )
    with tempfile.TemporaryDirectory() as temp_dir:
        _prepare_relative_file(temp_dir, os.path.join("altdir", "lesson", "task.md"), solution_content)
        task_file = _prepare_relative_file(temp_dir, os.path.join("ch", "lesson", "task.md"), "Task content")
        config_path = _create_test_config(temp_dir)
        course = MockCourse(config_path)
        _, macrocall = _create_macrocall(task_file, "ALT:", "macro_lang")
        result = snippetchecker.expand_snippet_macro(course, macrocall)
        expected = "```python\nprint(\"wrapped\")\n```"
        assert result == expected


def test_snippet_macro_lang_skips_existing_fence():
    """Snippets that already contain fenced blocks should not be double wrapped."""
    solution_content = dedent(
        """\
        # SNIPPET::macro_lang_fenced lang=python
        ```python
        print("already fenced")
        ```
        # ENDSNIPPET
        """
    )
    with tempfile.TemporaryDirectory() as temp_dir:
        _prepare_relative_file(temp_dir, os.path.join("altdir", "lesson", "task.md"), solution_content)
        task_file = _prepare_relative_file(temp_dir, os.path.join("ch", "lesson", "task.md"), "Task content")
        config_path = _create_test_config(temp_dir)
        course = MockCourse(config_path)
        _, macrocall = _create_macrocall(task_file, "ALT:", "macro_lang_fenced")
        result = snippetchecker.expand_snippet_macro(course, macrocall)
        expected = "```python\nprint(\"already fenced\")\n```"
        assert result == expected


def test_snippet_macro_without_lang_wraps_code_block():
    """Snippet without lang metadata should still be fenced."""
    solution_content = dedent(
        """\
        # SNIPPET::macro_plain
        print("plain")
        # ENDSNIPPET
        """
    )
    with tempfile.TemporaryDirectory() as temp_dir:
        _prepare_relative_file(temp_dir, os.path.join("altdir", "lesson", "task.md"), solution_content)
        task_file = _prepare_relative_file(temp_dir, os.path.join("ch", "lesson", "task.md"), "Task content")
        config_path = _create_test_config(temp_dir)
        course = MockCourse(config_path)
        _, macrocall = _create_macrocall(task_file, "ALT:", "macro_plain")
        result = snippetchecker.expand_snippet_macro(course, macrocall)
        expected = "```\nprint(\"plain\")\n```"
        assert result == expected


def test_snippet_macro_plain_skips_existing_fence():
    """Pre-fenced snippets without lang metadata should remain unchanged."""
    solution_content = dedent(
        """\
        # SNIPPET::macro_plain_fenced
        ```python
        print("already fenced plain")
        ```
        # ENDSNIPPET
        """
    )
    with tempfile.TemporaryDirectory() as temp_dir:
        _prepare_relative_file(temp_dir, os.path.join("altdir", "lesson", "task.md"), solution_content)
        task_file = _prepare_relative_file(temp_dir, os.path.join("ch", "lesson", "task.md"), "Task content")
        config_path = _create_test_config(temp_dir)
        course = MockCourse(config_path)
        _, macrocall = _create_macrocall(task_file, "ALT:", "macro_plain_fenced")
        result = snippetchecker.expand_snippet_macro(course, macrocall)
        expected = "```python\nprint(\"already fenced plain\")\n```"
        assert result == expected


def test_snippet_macro_missing_file():
    """Missing snippet file should trigger macro error."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = _create_test_config(temp_dir)
        course = MockCourse(config_path)
        task_file = _prepare_relative_file(temp_dir, os.path.join("ch", "lesson", "task.md"), "Task content")
        filespec = "ALT:lesson/missing.py"
        _, macrocall = _create_macrocall(task_file, filespec, "missing_snippet")
        errors = []
        macrocall.error = errors.append
        result = snippetchecker.expand_snippet_macro(course, macrocall)
        assert result == ""
        assert errors, "Expected error for missing file"
        assert "File not found" in errors[0]


def test_snippet_macro_missing_snippet_id():
    """Missing snippet in existing file should trigger error."""
    solution_content = """# SNIPPET::existing_snippet
    def exists():
        return 1
    # ENDSNIPPET
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        _prepare_relative_file(temp_dir, os.path.join("altdir", "lesson", "task.md"), solution_content)
        task_file = _prepare_relative_file(temp_dir, os.path.join("ch", "lesson", "task.md"), "Task content")
        config_path = _create_test_config(temp_dir)
        course = MockCourse(config_path)
        _, macrocall = _create_macrocall(task_file, "ALT:", "missing_snippet")
        errors = []
        macrocall.error = errors.append
        result = snippetchecker.expand_snippet_macro(course, macrocall)
        assert result == ""
        assert errors, "Expected error for missing snippet"
        assert "missing_snippet" in errors[0]


def test_snippet_macro_invalid_path_prefix():
    """ITREE prefix without configured itreedir should error."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = _create_test_config(temp_dir)
        course = MockCourse(config_path)
        course.itreedir = None
        task_file = _prepare_relative_file(temp_dir, os.path.join("ch", "lesson", "task.md"), "Task content")
        filespec = "ITREE:foo.py"
        _, macrocall = _create_macrocall(task_file, filespec, "snippet")
        errors = []
        macrocall.error = errors.append
        result = snippetchecker.expand_snippet_macro(course, macrocall)
        assert result == ""
        assert errors, "Expected error for invalid filespec"
        assert "ITREE" in errors[0]


def test_snippet_with_special_characters():
    """Test snippet extraction with special characters in content."""
    content = """# Solution
    # SNIPPET::special_chars
    def test():
        return "Special: <>&\"'äöü 日本語"
    # ENDSNIPPET
    """
    extractor = snippetchecker.SnippetExtractor()
    snippets, errors = extractor.extract_snippets_from_content(content, "test.py", collect_errors=False)
    assert len(snippets) == 1
    assert len(errors) == 0
    assert "äöü" in snippets[0].content
    assert "日本語" in snippets[0].content
    assert "&" in snippets[0].content
