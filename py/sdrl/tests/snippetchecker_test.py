# pytest tests for snippetchecker
import tempfile
import os
from pathlib import Path

import sdrl.snippetchecker as snippetchecker


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

More task content here.
"""
    
    ref_extractor = snippetchecker.SnippetReferenceExtractor()
    references = ref_extractor.extract_references_from_content(sample_content, "task.md")
    
    assert len(references) == 2, f"Expected 2 references, got {len(references)}"
    
    # Check first reference
    ref1 = references[0]
    assert ref1.snippet_id == "basic_loop", f"Expected 'basic_loop', got '{ref1.snippet_id}'"
    assert ref1.referenced_file == "solution.py", f"Expected 'solution.py', got '{ref1.referenced_file}'"
    assert ref1.source_file == "task.md", f"Expected 'task.md', got '{ref1.source_file}'"
    
    # Check second reference
    ref2 = references[1]
    assert ref2.snippet_id == "function_example", f"Expected 'function_example', got '{ref2.snippet_id}'"
    assert ref2.referenced_file == "examples/demo.py", f"Expected 'examples/demo.py', got '{ref2.referenced_file}'"


def test_snippet_validation_success():
    """Test successful snippet validation when references are valid."""
    # Create temporary solution file
    solution_content = """# Solution file
<!-- @SNIPPET_START: test_snippet -->
def test_function():
    return "Hello, World!"
<!-- @SNIPPET_END: test_snippet -->
"""
    
    # Create temporary task file
    task_content = """# Task file
@INCLUDE_SNIPPET: test_snippet from solution.py
"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Write solution file
        solution_file = os.path.join(temp_dir, "solution.py")
        with open(solution_file, 'w', encoding='utf-8') as f:
            f.write(solution_content)
        
        # Write task file
        task_file = os.path.join(temp_dir, "task.md")
        with open(task_file, 'w', encoding='utf-8') as f:
            f.write(task_content)
        
        # Validate
        validator = snippetchecker.SnippetValidator()
        results = validator.validate_file_references(task_file, temp_dir)
        
        assert len(results) == 1, f"Expected 1 result, got {len(results)}"
        
        result = results[0]
        assert result.success, f"Validation should succeed, got error: {result.error_message}"
        assert result.snippet is not None, "Should have snippet details"
        assert result.snippet.snippet_id == "test_snippet", "Should have correct snippet ID"
        assert "def test_function():" in result.snippet.content, "Should have correct snippet content"


def test_snippet_validation_missing_file():
    """Test snippet validation when referenced file doesn't exist."""
    task_content = """# Task file
@INCLUDE_SNIPPET: missing_snippet from nonexistent.py
"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Write task file only (no solution file)
        task_file = os.path.join(temp_dir, "task.md")
        with open(task_file, 'w', encoding='utf-8') as f:
            f.write(task_content)
        
        # Validate
        validator = snippetchecker.SnippetValidator()
        results = validator.validate_file_references(task_file, temp_dir)
        
        assert len(results) == 1, f"Expected 1 result, got {len(results)}"
        
        result = results[0]
        assert not result.success, "Validation should fail for missing file"
        assert "not found" in result.error_message.lower(), f"Error should mention missing file: {result.error_message}"


def test_snippet_validation_missing_snippet():
    """Test snippet validation when snippet ID doesn't exist in file."""
    # Create solution file without the referenced snippet
    solution_content = """# Solution file
<!-- @SNIPPET_START: other_snippet -->
def other_function():
    pass
<!-- @SNIPPET_END: other_snippet -->
"""
    
    task_content = """# Task file
@INCLUDE_SNIPPET: missing_snippet from solution.py
"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Write solution file
        solution_file = os.path.join(temp_dir, "solution.py")
        with open(solution_file, 'w', encoding='utf-8') as f:
            f.write(solution_content)
        
        # Write task file
        task_file = os.path.join(temp_dir, "task.md")
        with open(task_file, 'w', encoding='utf-8') as f:
            f.write(task_content)
        
        # Validate
        validator = snippetchecker.SnippetValidator()
        results = validator.validate_file_references(task_file, temp_dir)
        
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
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
        f.write(valid_content)
        valid_file = f.name
    
    try:
        errors = validator._validate_snippet_markers_in_file(valid_file)
        assert len(errors) == 0, f"Expected no errors for valid content, got {len(errors)}: {errors}"
    finally:
        os.unlink(valid_file)
    
    # Test invalid content
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
        f.write(invalid_content)
        invalid_file = f.name
    
    try:
        errors = validator._validate_snippet_markers_in_file(invalid_file)
        assert len(errors) > 0, f"Expected errors for invalid content, got {len(errors)}"
    finally:
        os.unlink(invalid_file)


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
    
    # Test nested snippets - current implementation handles outer snippet only
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
    """Test expansion of @INCLUDE_SNIPPET directives in content."""
    # Create snippet definition file
    solution_content = """# Solution file
<!-- @SNIPPET_START: test_func -->
def test_function():
    return 42
<!-- @SNIPPET_END: test_func -->

<!-- @SNIPPET_START: hello_func lang=python -->
def hello():
    print("Hello, World!")
<!-- @SNIPPET_END: hello_func -->
"""
    
    # Create content with snippet references
    task_content = """# Task Description

Implement the following function:

@INCLUDE_SNIPPET: test_func from solution.py

And also this one:

@INCLUDE_SNIPPET: hello_func from solution.py

Good luck!
"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Write solution file
        solution_file = os.path.join(temp_dir, "solution.py")
        with open(solution_file, 'w', encoding='utf-8') as f:
            f.write(solution_content)
        
        # Expand snippet inclusions
        task_file = os.path.join(temp_dir, "task.md")
        result = snippetchecker.expand_snippet_inclusion(task_content, task_file, temp_dir)
        
        # Verify expansion worked
        assert "def test_function():" in result, "Should contain expanded test_func snippet"
        assert "return 42" in result, "Should contain test_func content"
        assert "def hello():" in result, "Should contain expanded hello_func snippet"
        assert 'print("Hello, World!")' in result, "Should contain hello_func content"
        
        # Verify directives were replaced
        assert "@INCLUDE_SNIPPET: test_func" not in result, "Directive should be replaced"
        assert "@INCLUDE_SNIPPET: hello_func" not in result, "Directive should be replaced"
        
        # Verify surrounding text is preserved
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
        
        # Expand (basedir is temp_dir, simulating project root)
        task_file = os.path.join(temp_dir, "ch", "task.md")
        os.makedirs(os.path.dirname(task_file), exist_ok=True)
        
        result = snippetchecker.expand_snippet_inclusion(task_content, task_file, temp_dir)
        
        # Verify altdir path was resolved correctly
        assert "def from_altdir():" in result, "Should expand snippet from altdir"
        assert 'return "altdir works"' in result, "Should contain snippet content"
        assert "@INCLUDE_SNIPPET" not in result, "Directive should be replaced"


def test_snippet_inclusion_missing_file():
    """Test error handling when referenced file doesn't exist."""
    task_content = """# Task
@INCLUDE_SNIPPET: missing_snippet from nonexistent.py
"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        task_file = os.path.join(temp_dir, "task.md")
        
        result = snippetchecker.expand_snippet_inclusion(task_content, task_file, temp_dir)
        
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
    
    task_content = """# Task
@INCLUDE_SNIPPET: nonexistent_id from solution.py
"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Write solution file
        solution_file = os.path.join(temp_dir, "solution.py")
        with open(solution_file, 'w', encoding='utf-8') as f:
            f.write(solution_content)
        
        task_file = os.path.join(temp_dir, "task.md")
        
        result = snippetchecker.expand_snippet_inclusion(task_content, task_file, temp_dir)
        
        # Should return error comment
        assert "<!-- ERROR:" in result, "Should contain error comment"
        assert "not found" in result, "Error should mention snippet not found"


def test_snippet_inclusion_relative_path():
    """Test snippet inclusion with relative path."""
    solution_content = """<!-- @SNIPPET_START: relative_snippet -->
def relative_function():
    return "relative"
<!-- @SNIPPET_END: relative_snippet -->
"""
    
    task_content = """# Task
@INCLUDE_SNIPPET: relative_snippet from ../solutions/code.py
"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create directory structure: temp_dir/tasks/task.md, temp_dir/solutions/code.py
        tasks_dir = os.path.join(temp_dir, "tasks")
        solutions_dir = os.path.join(temp_dir, "solutions")
        os.makedirs(tasks_dir, exist_ok=True)
        os.makedirs(solutions_dir, exist_ok=True)
        
        # Write solution file
        solution_file = os.path.join(solutions_dir, "code.py")
        with open(solution_file, 'w', encoding='utf-8') as f:
            f.write(solution_content)
        
        # Expand (task file is in tasks/ directory)
        task_file = os.path.join(tasks_dir, "task.md")
        
        result = snippetchecker.expand_snippet_inclusion(task_content, task_file, temp_dir)
        
        # Verify relative path resolution worked
        assert "def relative_function():" in result, "Should resolve relative path"
        assert 'return "relative"' in result, "Should contain snippet content"
