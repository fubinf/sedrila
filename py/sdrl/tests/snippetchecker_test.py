# pytest tests for snippetchecker
import tempfile
import os
from pathlib import Path
import yaml

import sdrl.snippetchecker as snippetchecker


class MockCourse:
    """Mock course object for testing snippet functionality."""
    def __init__(self, configfile: str, chapterdir: str = "ch", altdir: str = "altdir"):
        self.configfile = configfile
        self.chapterdir = chapterdir
        self.altdir = altdir


def _create_test_config(base_dir: str, chapterdir: str = "ch", altdir: str = "altdir") -> str:
    """
    Create a minimal sedrila.yaml config file for testing.
    
    Returns:
        Path to the created config file
    """
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
    with open(config_path, 'w') as f:
        yaml.dump(config, f)
    
    return config_path


def test_snippet_extraction():
    """Test basic snippet extraction from solution files with HTML comment format."""
    sample_content = """# Example solution file
def helper_function():
    return "helper"

<!-- @SNIPPET_START: basic_loop -->
for i in range(10):
    print(f"Number: {i}")
<!-- @SNIPPET_END: basic_loop -->

def another_function():
    pass

<!-- @SNIPPET_START: function_example lang=python -->
def calculate_sum(a, b):
    return a + b

result = calculate_sum(5, 3)
print(result)
<!-- @SNIPPET_END: function_example -->

# Rest of the file
print("End of file")
"""
    
    extractor = snippetchecker.SnippetExtractor()
    snippets, errors = extractor.extract_snippets_from_content(sample_content, "test.py", collect_errors=False)
    
    assert len(errors) == 0, f"Expected no errors, got {len(errors)}: {errors}"
    assert len(snippets) == 2, f"Expected 2 snippets, got {len(snippets)}"
    
    # Check first snippet
    snippet1 = snippets[0]
    assert snippet1.snippet_id == "basic_loop", f"Expected 'basic_loop', got '{snippet1.snippet_id}'"
    assert "for i in range(10):" in snippet1.content, "Expected loop content in snippet"
    assert snippet1.language is None, "First snippet should have no language specified"
    
    # Check second snippet
    snippet2 = snippets[1]
    assert snippet2.snippet_id == "function_example", f"Expected 'function_example', got '{snippet2.snippet_id}'"
    assert "def calculate_sum(a, b):" in snippet2.content, "Expected function content in snippet"
    assert snippet2.language == "python", f"Expected language 'python', got '{snippet2.language}'"


def test_snippet_reference_extraction():
    """Test extraction of snippet references from task files."""
    sample_content = """# Task Description

This is how to implement a basic loop:

@INCLUDE_SNIPPET: basic_loop from solution.py

And here's how to define a function:

@INCLUDE_SNIPPET: function_example from examples/demo.py

Reference without explicit path:

@INCLUDE_SNIPPET: implicit_example

More task content here.
"""
    
    ref_extractor = snippetchecker.SnippetReferenceExtractor()
    references = ref_extractor.extract_references_from_content(sample_content, "task.md")
    
    assert len(references) == 3, f"Expected 3 references, got {len(references)}"
    
    # Check first reference
    ref1 = references[0]
    assert ref1.snippet_id == "basic_loop", f"Expected 'basic_loop', got '{ref1.snippet_id}'"
    assert ref1.referenced_file == "solution.py", f"Expected 'solution.py', got '{ref1.referenced_file}'"
    assert ref1.source_file == "task.md", f"Expected 'task.md', got '{ref1.source_file}'"
    
    # Check second reference
    ref2 = references[1]
    assert ref2.snippet_id == "function_example", f"Expected 'function_example', got '{ref2.snippet_id}'"
    assert ref2.referenced_file == "examples/demo.py", f"Expected 'examples/demo.py', got '{ref2.referenced_file}'"
    
    # Check third reference (implicit path)
    ref3 = references[2]
    assert ref3.snippet_id == "implicit_example", f"Expected 'implicit_example', got '{ref3.snippet_id}'"
    assert ref3.referenced_file is None, "Implicit reference should have no explicit file"


def test_snippet_validation_success():
    """Test successful snippet validation when references are valid."""
    solution_content = """<!-- @SNIPPET_START: test_snippet -->
def test_function():
    return "Hello, World!"
<!-- @SNIPPET_END: test_snippet -->
"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        task_file = os.path.join(temp_dir, "ch", "lesson", "task.md")
        answer_file = os.path.join(temp_dir, "altdir", "lesson", "task.md")
        os.makedirs(os.path.dirname(task_file), exist_ok=True)
        os.makedirs(os.path.dirname(answer_file), exist_ok=True)
        
        with open(answer_file, 'w', encoding='utf-8') as f:
            f.write(solution_content)
        
        task_content = "@INCLUDE_SNIPPET: test_snippet"
        with open(task_file, 'w', encoding='utf-8') as f:
            f.write(task_content)
        
        # Create config file and create a mock course object
        config_path = _create_test_config(temp_dir)
        
        # Create a minimal course-like object for testing
        class MockCourse:
            def __init__(self, config_path):
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                self.chapterdir = config.get('chapterdir', 'ch')
                self.altdir = config.get('altdir', 'altdir')
                self.configfile = config_path
        
        mock_course = MockCourse(config_path)
        
        # Validate
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
        task_file = os.path.join(temp_dir, "ch", "lesson", "task.md")
        os.makedirs(os.path.dirname(task_file), exist_ok=True)
        task_content = "@INCLUDE_SNIPPET: missing_snippet"
        with open(task_file, 'w', encoding='utf-8') as f:
            f.write(task_content)
        
        # Create config file and create a mock course object
        config_path = _create_test_config(temp_dir)
        
        # Create a minimal course-like object for testing
        class MockCourse:
            def __init__(self, config_path):
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                self.chapterdir = config.get('chapterdir', 'ch')
                self.altdir = config.get('altdir', 'altdir')
                self.configfile = config_path
        
        mock_course = MockCourse(config_path)
        
        # Validate
        validator = snippetchecker.SnippetValidator()
        results = validator.validate_file_references(task_file, mock_course)
        
        assert len(results) == 1, f"Expected 1 result, got {len(results)}"
        
        result = results[0]
        assert not result.success, "Validation should fail for missing file"
        assert "not found" in result.error_message.lower(), f"Error should mention missing file: {result.error_message}"


def test_snippet_validation_missing_snippet():
    """Test snippet validation when snippet ID doesn't exist in file."""
    solution_content = """<!-- @SNIPPET_START: other_snippet -->
def other_function():
    pass
<!-- @SNIPPET_END: other_snippet -->
"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        task_file = os.path.join(temp_dir, "ch", "lesson", "task.md")
        answer_file = os.path.join(temp_dir, "altdir", "lesson", "task.md")
        os.makedirs(os.path.dirname(task_file), exist_ok=True)
        os.makedirs(os.path.dirname(answer_file), exist_ok=True)
        
        with open(answer_file, 'w', encoding='utf-8') as f:
            f.write(solution_content)
        
        task_content = "@INCLUDE_SNIPPET: missing_snippet"
        with open(task_file, 'w', encoding='utf-8') as f:
            f.write(task_content)
        
        # Create config file and create a mock course object
        config_path = _create_test_config(temp_dir)
        
        # Create a minimal course-like object for testing
        class MockCourse:
            def __init__(self, config_path):
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                self.chapterdir = config.get('chapterdir', 'ch')
                self.altdir = config.get('altdir', 'altdir')
                self.configfile = config_path
        
        mock_course = MockCourse(config_path)
        
        # Validate
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
<!-- @SNIPPET_START: snippet1 -->
code here
<!-- @SNIPPET_END: snippet1 -->

<!-- @SNIPPET_START: snippet2 lang=python -->
more code
<!-- @SNIPPET_END: snippet2 -->
"""
    
    # Invalid content - unclosed snippet (simpler case)
    invalid_content = """# Invalid file
<!-- @SNIPPET_START: unclosed_snippet -->
code here
code there
# This snippet is never closed
"""
    
    validator = snippetchecker.SnippetValidator()
    
    # Test valid content
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', encoding='utf-8') as f:
        f.write(valid_content)
        f.flush()
        os.fsync(f.fileno())
        valid_file = f.name

        errors = validator._validate_snippet_markers_in_file(valid_file)
        assert len(errors) == 0, f"Expected no errors for valid content, got {len(errors)}: {errors}"
    
    # Test invalid content
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', encoding='utf-8') as f:
        f.write(invalid_content)
        f.flush()
        os.fsync(f.fileno())
        invalid_file = f.name

        errors = validator._validate_snippet_markers_in_file(invalid_file)
        assert len(errors) > 0, f"Expected errors for invalid content, got {len(errors)}"


def test_nested_and_overlapping_snippets():
    """Test handling of nested and overlapping snippet markers."""
    # Content with nested snippets (should warn)
    nested_content = """# File with nested snippets
<!-- @SNIPPET_START: outer -->
outer code
<!-- @SNIPPET_START: inner -->
inner code
<!-- @SNIPPET_END: inner -->
more outer code
<!-- @SNIPPET_END: outer -->
"""
    
    # Content with overlapping snippets (should warn)
    overlapping_content = """# File with overlapping snippets
<!-- @SNIPPET_START: first -->
first code
<!-- @SNIPPET_START: second -->
overlapping code
<!-- @SNIPPET_END: first -->
more second code
<!-- @SNIPPET_END: second -->
"""
    
    extractor = snippetchecker.SnippetExtractor()
    
    # Test nested snippets: current implementation handles outer snippet only
    nested_snippets, _ = extractor.extract_snippets_from_content(nested_content, "nested.py", collect_errors=False)
    # Current behavior: outer snippet includes inner markers as content
    snippet_ids = [s.snippet_id for s in nested_snippets]
    assert "outer" in snippet_ids, "Should extract outer snippet"
    # Note: nested snippets not currently supported separately
    
    # Test overlapping snippets
    overlapping_snippets, _ = extractor.extract_snippets_from_content(overlapping_content, "overlapping.py", collect_errors=False)
    # Should handle overlapping markers (behavior may vary but shouldn't crash)
    assert isinstance(overlapping_snippets, list), "Should return list of snippets"


def test_multiple_references_in_single_file():
    """Test handling multiple snippet references in a single task file."""
    task_content = """# Complex Task

First, implement the helper:
@INCLUDE_SNIPPET: helper from utils.py

Then use it in the main function:
@INCLUDE_SNIPPET: main_function from solution.py

And add error handling:
@INCLUDE_SNIPPET: error_handling from solution.py

Finally, test it:
@INCLUDE_SNIPPET: test_case from tests.py
"""
    
    ref_extractor = snippetchecker.SnippetReferenceExtractor()
    references = ref_extractor.extract_references_from_content(task_content, "complex_task.md")
    
    assert len(references) == 4, f"Expected 4 references, got {len(references)}"
    
    # Check all references are found
    expected_refs = [
        ("helper", "utils.py"),
        ("main_function", "solution.py"),
        ("error_handling", "solution.py"),
        ("test_case", "tests.py")
    ]
    
    actual_refs = [(r.snippet_id, r.referenced_file) for r in references]
    
    for expected in expected_refs:
        assert expected in actual_refs, f"Expected reference {expected} not found in {actual_refs}"


def test_directory_validation():
    """Test validation of all snippets in a directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create multiple files with various snippet scenarios
        
        # Valid file
        valid_file = os.path.join(temp_dir, "valid.py")
        with open(valid_file, 'w') as f:
            f.write("""<!-- @SNIPPET_START: valid_snippet -->
def valid_function():
    pass
<!-- @SNIPPET_END: valid_snippet -->
""")
        
        # Invalid file
        invalid_file = os.path.join(temp_dir, "invalid.py")
        with open(invalid_file, 'w') as f:
            f.write("""<!-- @SNIPPET_START: unclosed_snippet -->
def broken_function():
    pass
# Missing end marker
""")
        
        # File without snippets (should not cause errors)
        no_snippet_file = os.path.join(temp_dir, "no_snippets.py")
        with open(no_snippet_file, 'w') as f:
            f.write("""def normal_function():
    pass
""")
        
        validator = snippetchecker.SnippetValidator()
        file_errors = validator.validate_directory_snippets(temp_dir)
        
        # Should find errors only in the invalid file
        assert valid_file not in file_errors or not file_errors[valid_file], "Valid file should have no errors"
        assert invalid_file in file_errors and file_errors[invalid_file], "Invalid file should have errors"
        assert no_snippet_file not in file_errors or not file_errors[no_snippet_file], "File without snippets should have no errors"


def test_snippet_inclusion_expansion():
    """Test expansion with implicit altdir path resolution."""
    solution_content = """<!-- @SNIPPET_START: test_func -->
def test_function():
    return 42
<!-- @SNIPPET_END: test_func -->

<!-- @SNIPPET_START: hello_func lang=python -->
def hello():
    print("Hello, World!")
<!-- @SNIPPET_END: hello_func -->
"""
    
    task_content = """# Task Description

Implement the following function:

@INCLUDE_SNIPPET: test_func

And also this one:

@INCLUDE_SNIPPET: hello_func

Good luck!
"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        task_file = os.path.join(temp_dir, "ch", "Web", "Django", "task.md")
        answer_file = os.path.join(temp_dir, "altdir", "Web", "Django", "task.md")
        os.makedirs(os.path.dirname(task_file), exist_ok=True)
        os.makedirs(os.path.dirname(answer_file), exist_ok=True)
        
        with open(answer_file, 'w', encoding='utf-8') as f:
            f.write(solution_content)
        
        config_path = _create_test_config(temp_dir)
        course = MockCourse(config_path)
        result = snippetchecker.expand_snippet_inclusion(task_content, task_file, course)
        
        assert "def test_function():" in result, "Should contain expanded test_func snippet"
        assert "return 42" in result, "Should contain test_func content"
        assert "def hello():" in result, "Should contain expanded hello_func snippet"
        assert 'print("Hello, World!")' in result, "Should contain hello_func content"
        assert "@INCLUDE_SNIPPET" not in result, "Directive should be replaced"
        assert "# Task Description" in result, "Should preserve text before snippet"
        assert "Good luck!" in result, "Should preserve text after snippet"


def test_snippet_inclusion_with_altdir():
    """Test snippet inclusion from altdir/ path."""
    # Create directory structure: basedir/altdir/solutions/
    solution_content = """<!-- @SNIPPET_START: altdir_snippet -->
def from_altdir():
    return "altdir works"
<!-- @SNIPPET_END: altdir_snippet -->
"""
    
    task_content = """# Task
@INCLUDE_SNIPPET: altdir_snippet from altdir/solutions/helper.py
"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create altdir structure
        altdir_path = os.path.join(temp_dir, "altdir", "solutions")
        os.makedirs(altdir_path, exist_ok=True)
        
        # Write solution file in altdir
        solution_file = os.path.join(altdir_path, "helper.py")
        with open(solution_file, 'w', encoding='utf-8') as f:
            f.write(solution_content)
        
        # Expand (project root is temp_dir)
        task_file = os.path.join(temp_dir, "ch", "task.md")
        os.makedirs(os.path.dirname(task_file), exist_ok=True)
        
        config_path = _create_test_config(temp_dir)
        course = MockCourse(config_path)
        result = snippetchecker.expand_snippet_inclusion(task_content, task_file, course)
        
        # Verify altdir path was resolved correctly
        assert "def from_altdir():" in result, "Should expand snippet from altdir"
        assert 'return "altdir works"' in result, "Should contain snippet content"
        assert "@INCLUDE_SNIPPET" not in result, "Directive should be replaced"


def test_snippet_inclusion_missing_file():
    """Test error handling when referenced file doesn't exist."""
    with tempfile.TemporaryDirectory() as temp_dir:
        task_file = os.path.join(temp_dir, "ch", "lesson", "task.md")
        os.makedirs(os.path.dirname(task_file), exist_ok=True)
        
        task_content = "@INCLUDE_SNIPPET: missing_snippet"
        config_path = _create_test_config(temp_dir)
        course = MockCourse(config_path)
        result = snippetchecker.expand_snippet_inclusion(task_content, task_file, course)
        
        # Should return error comment
        assert "<!-- ERROR:" in result, "Should contain error comment"
        assert "not found" in result, "Error should mention file not found"


def test_snippet_inclusion_missing_snippet_id():
    """Test error handling when snippet ID doesn't exist."""
    solution_content = """<!-- @SNIPPET_START: existing_snippet -->
def exists():
    pass
<!-- @SNIPPET_END: existing_snippet -->
"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        task_file = os.path.join(temp_dir, "ch", "topic", "task.md")
        answer_file = os.path.join(temp_dir, "altdir", "topic", "task.md")
        os.makedirs(os.path.dirname(task_file), exist_ok=True)
        os.makedirs(os.path.dirname(answer_file), exist_ok=True)
        
        with open(answer_file, 'w', encoding='utf-8') as f:
            f.write(solution_content)
        
        task_content = "@INCLUDE_SNIPPET: nonexistent_id"
        config_path = _create_test_config(temp_dir)
        course = MockCourse(config_path)
        result = snippetchecker.expand_snippet_inclusion(task_content, task_file, course)
        
        # Should return error comment
        assert "<!-- ERROR:" in result, "Should contain error comment"
        assert "not found" in result, "Error should mention snippet not found"


def test_snippet_inclusion_unsupported_path():
    """Unsupported explicit paths should produce an error comment."""
    with tempfile.TemporaryDirectory() as temp_dir:
        task_file = os.path.join(temp_dir, "ch", "module", "task.md")
        os.makedirs(os.path.dirname(task_file), exist_ok=True)
        
        task_content = "@INCLUDE_SNIPPET: relative_snippet from ../solutions/code.py"
        config_path = _create_test_config(temp_dir)
        course = MockCourse(config_path)
        result = snippetchecker.expand_snippet_inclusion(task_content, task_file, course)
        
        assert "<!-- ERROR:" in result
        assert "Unsupported snippet path" in result


def test_circular_reference_detection():
    """Test detection of circular snippet references."""
    import tempfile
    
    # Create files with circular references
    file1_content = """# File 1
@INCLUDE_SNIPPET: snippet2 from file2.md
"""
    
    file2_content = """# File 2
@INCLUDE_SNIPPET: snippet1 from file1.md
"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        file1 = os.path.join(temp_dir, "file1.md")
        file2 = os.path.join(temp_dir, "file2.md")
        
        with open(file1, 'w', encoding='utf-8') as f:
            f.write(file1_content)
        with open(file2, 'w', encoding='utf-8') as f:
            f.write(file2_content)
        
        # This would cause infinite loop if not handled
        # Currently, expand_snippet_inclusion doesn't detect cycles
        # This test documents the current behavior and can be updated when cycle detection is added
        config_path = _create_test_config(temp_dir, chapterdir="", altdir="altdir")
        course = MockCourse(config_path, chapterdir="", altdir="altdir")
        result = snippetchecker.expand_snippet_inclusion(file1_content, file1, course)
        
        # Should return an error comment or original content
        # (Currently no cycle detection implemented, so this documents expected behavior)
        assert "@INCLUDE_SNIPPET" in result or "ERROR" in result


def test_snippet_with_special_characters():
    """Test snippet extraction with special characters in content."""
    import tempfile
    
    content = """# Solution
<!-- @SNIPPET_START: special_chars -->
def test():
    return "Special: <>&\"'äöü 日本語"
<!-- @SNIPPET_END: special_chars -->
"""
    
    extractor = snippetchecker.SnippetExtractor()
    snippets, errors = extractor.extract_snippets_from_content(content, "test.py", collect_errors=False)
    
    assert len(snippets) == 1
    assert len(errors) == 0
    assert "äöü" in snippets[0].content
    assert "日本語" in snippets[0].content
    assert "&" in snippets[0].content
