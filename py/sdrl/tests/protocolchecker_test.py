# pytest tests for protocolchecker
import tempfile
import os

import sdrl.protocolchecker as protocolchecker


def test_basic_extraction():
    """Test basic protocol file extraction."""
    sample_content = """# Example protocol file
user@host /home/user 10:00:00 1
$ ls -la
total 16
drwxr-xr-x 2 user user 4096 Jan 1 12:00 .
drwxr-xr-x 3 user user 4096 Jan 1 12:00 ..
-rw-r--r-- 1 user user  123 Jan 1 12:00 file.txt

user@host /home/user 10:01:00 2
$ cat file.txt
Hello World
This is a test file.

user@host /home/user 10:02:00 3
$ echo "Done"
Done
"""
    
    extractor = protocolchecker.ProtocolExtractor()
    protocol = extractor.extract_from_content(sample_content)
    
    assert protocol.total_entries == 3, f"Expected 3 entries, got {protocol.total_entries}"
    
    # Check first entry
    assert protocol.entries[0].command == "ls -la", f"Expected 'ls -la', got '{protocol.entries[0].command}'"
    assert "total 16" in protocol.entries[0].output, "Expected output should contain 'total 16'"
    
    # Check second entry
    assert protocol.entries[1].command == "cat file.txt", f"Expected 'cat file.txt', got '{protocol.entries[1].command}'"
    assert "Hello World" in protocol.entries[1].output, "Expected output should contain 'Hello World'"
    
    # Check third entry
    assert protocol.entries[2].command == 'echo "Done"', f"Expected 'echo \"Done\"', got '{protocol.entries[2].command}'"
    assert protocol.entries[2].output.strip() == "Done", f"Expected 'Done', got '{protocol.entries[2].output.strip()}'"


def test_annotation_parsing():
    """Test protocol check annotation parsing."""
    sample_content = """# @PROT_CHECK: command=exact, output=flexible
user@host /home/user 10:00:00 1
$ ls -la
total 16
drwxr-xr-x 2 user user 4096 Jan 1 12:00 .

# @PROT_CHECK: command=regex, regex=echo.*test, output=skip
user@host /home/user 10:01:00 2
$ echo "test message"
test message

# @PROT_CHECK: command=multi_variant, variants="pwd|ls", output=exact
user@host /home/user 10:02:00 3
$ pwd
/home/user
"""
    
    extractor = protocolchecker.ProtocolExtractor()
    protocol = extractor.extract_from_content(sample_content)
    
    assert protocol.total_entries == 3, f"Expected 3 entries, got {protocol.total_entries}"
    
    # Check first entry annotation
    rule1 = protocol.entries[0].check_rule
    assert rule1 is not None, "First entry should have a check rule"
    assert rule1.command_type == "exact", f"Expected command_type 'exact', got '{rule1.command_type}'"
    assert rule1.output_type == "flexible", f"Expected output_type 'flexible', got '{rule1.output_type}'"
    
    # Check second entry annotation
    rule2 = protocol.entries[1].check_rule
    assert rule2 is not None, "Second entry should have a check rule"
    assert rule2.command_type == "regex", f"Expected command_type 'regex', got '{rule2.command_type}'"
    assert rule2.regex_pattern == "echo.*test", f"Expected regex 'echo.*test', got '{rule2.regex_pattern}'"
    assert rule2.output_type == "skip", f"Expected output_type 'skip', got '{rule2.output_type}'"
    
    # Check third entry annotation
    rule3 = protocol.entries[2].check_rule
    assert rule3 is not None, "Third entry should have a check rule"
    assert rule3.command_type == "multi_variant", f"Expected command_type 'multi_variant', got '{rule3.command_type}'"
    assert rule3.variants == ["pwd", "ls"], f"Expected variants ['pwd', 'ls'], got {rule3.variants}"


def test_validation():
    """Test protocol annotation validation."""
    # Valid annotations
    valid_content = """# @PROT_CHECK: command=exact, output=flexible
user@host /home/user 10:00:00 1
$ ls -la
file1 file2

# @PROT_CHECK: command=regex, regex=echo.*test, output=skip
user@host /home/user 10:01:00 2
$ echo "test"
test
"""
    
    # Invalid annotations
    invalid_content = """# @PROT_CHECK: command=invalid_type, output=flexible
user@host /home/user 10:00:00 1
$ ls -la
file1 file2

# @PROT_CHECK: command=regex, output=skip
user@host /home/user 10:01:00 2
$ echo "test"
test
"""
    
    validator = protocolchecker.ProtocolValidator()
    
    # Test valid content
    with tempfile.NamedTemporaryFile(mode='w', suffix='.prot', delete=False) as f:
        f.write(valid_content)
        valid_file = f.name
    
    try:
        errors = validator.validate_file(valid_file)
        assert len(errors) == 0, f"Expected no errors for valid content, got {len(errors)}: {errors}"
    finally:
        os.unlink(valid_file)
    
    # Test invalid content
    with tempfile.NamedTemporaryFile(mode='w', suffix='.prot', delete=False) as f:
        f.write(invalid_content)
        invalid_file = f.name
    
    try:
        errors = validator.validate_file(invalid_file)
        assert len(errors) > 0, f"Expected errors for invalid content, got {len(errors)}"
    finally:
        os.unlink(invalid_file)


def test_comparison():
    """Test protocol file comparison."""
    # Author file with annotations
    author_content = """# @PROT_CHECK: command=exact, output=flexible
author@server /home/author 10:00:00 1
$ ls -la
total 16
drwxr-xr-x 2 user user 4096 Jan 1 12:00 .
-rw-r--r-- 1 user user  123 Jan 1 12:00 file.txt

# @PROT_CHECK: command=regex, regex=echo.*test, output=skip
author@server /home/author 10:01:00 2
$ echo "test message"
test message

author@server /home/author 10:02:00 3
$ pwd
/home/user
"""
    
    # Student file - should match
    student_content = """student@laptop /home/student 14:30:00 1
$ ls -la
total 16
drwxr-xr-x 2 user user 4096 Jan 1 12:00 .

-rw-r--r-- 1 user user  123 Jan 1 12:00 file.txt

student@laptop /home/student 14:31:00 2
$ echo "test 123"
different output here

student@laptop /home/student 14:32:00 3
$ pwd
/home/user
"""
    
    # Create temporary files
    with tempfile.NamedTemporaryFile(mode='w', suffix='.prot', delete=False) as f:
        f.write(author_content)
        author_file = f.name
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.prot', delete=False) as f:
        f.write(student_content)
        student_file = f.name
    
    try:
        checker = protocolchecker.ProtocolChecker()
        results = checker.compare_files(student_file, author_file)
        
        assert len(results) == 3, f"Expected 3 results, got {len(results)}"
        
        # First entry - should pass (flexible output matching)
        assert results[0].success, f"First entry should pass with flexible output matching"
        
        # Second entry - should pass (skip output, regex command match)
        assert results[1].success, f"Second entry should pass (skip output, regex command)"
        assert results[1].requires_manual_check, f"Second entry should require manual check"
        
        # Third entry - should pass (exact match)
        assert results[2].success, f"Third entry should pass with exact match"
        
    finally:
        os.unlink(author_file)
        os.unlink(student_file)


def test_protocol_with_prompt_lines():
    """Test protocol files with prompt lines (user@host directory time sequence)."""
    sample_content = """# @PROT_CHECK: command=exact, output=flexible
navi@Navi /MA/MyDoc/http_test 12:19:00 123
$ ls -la
total 16
drwxr-xr-x 2 user user 4096 Jan 1 12:00 .
drwxr-xr-x 3 user user 4096 Jan 1 12:00 ..
-rw-r--r-- 1 user user  123 Jan 1 12:00 file.txt

# @PROT_CHECK: command=regex, regex=echo.*test, output=skip
user@host /home/user 14:30:00 456
$ echo "test message"
test message

# @PROT_CHECK: command=exact, output=exact
admin@server /var/log 09:15:00 789
$ pwd
/var/log
"""
    
    extractor = protocolchecker.ProtocolExtractor()
    protocol = extractor.extract_from_content(sample_content)
    
    assert protocol.total_entries == 3, f"Expected 3 entries, got {protocol.total_entries}"
    
    # Check first entry
    assert protocol.entries[0].command == "ls -la", f"Expected 'ls -la', got '{protocol.entries[0].command}'"
    assert "total 16" in protocol.entries[0].output, "Expected output should contain 'total 16'"
    rule1 = protocol.entries[0].check_rule
    assert rule1 is not None, "First entry should have a check rule"
    assert rule1.command_type == "exact", f"Expected command_type 'exact', got '{rule1.command_type}'"
    
    # Check second entry
    assert protocol.entries[1].command == 'echo "test message"', f"Expected 'echo \"test message\"', got '{protocol.entries[1].command}'"
    rule2 = protocol.entries[1].check_rule
    assert rule2 is not None, "Second entry should have a check rule"
    assert rule2.command_type == "regex", f"Expected command_type 'regex', got '{rule2.command_type}'"
    assert rule2.output_type == "skip", f"Expected output_type 'skip', got '{rule2.output_type}'"
    
    # Check third entry
    assert protocol.entries[2].command == "pwd", f"Expected 'pwd', got '{protocol.entries[2].command}'"
    assert protocol.entries[2].output.strip() == "/var/log", f"Expected '/var/log', got '{protocol.entries[2].output.strip()}'"


def test_comparison_with_prompt_lines():
    """Test protocol comparison when files have prompt lines."""
    # Author file with prompt lines and annotations
    author_content = r"""# @PROT_CHECK: command=regex, regex=nc.*POST-form\.crlf, output=skip
navi@Navi /MA/MyDoc/http_test 12:19:00 123
$ nc httpbin.org 80 <http-POST-form.crlf
HTTP/1.1 200 OK
Date: Mon, 04 Aug 2025 09:59:21 GMT
Content-Type: application/json

# @PROT_CHECK: command=exact, output=flexible
user@host /home/user 14:30:00 456
$ ls -la
total 16
drwxr-xr-x 2 user user 4096 Jan 1 12:00 .
"""
    
    # Student file with different prompt lines but matching commands
    student_content = """student@laptop /different/path 10:00:00 1
$ nc httpbin.org 80 <http-POST-form.crlf
HTTP/1.1 200 OK
Date: Different Date
Content-Type: application/json

another@machine /another/path 11:00:00 2
$ ls -la
  total 16  
  drwxr-xr-x 2 user user 4096 Jan 1 12:00 .  
"""
    
    # Create temporary files
    with tempfile.NamedTemporaryFile(mode='w', suffix='.prot', delete=False) as f:
        f.write(author_content)
        author_file = f.name
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.prot', delete=False) as f:
        f.write(student_content)
        student_file = f.name
    
    try:
        checker = protocolchecker.ProtocolChecker()
        results = checker.compare_files(student_file, author_file)
        
        assert len(results) == 2, f"Expected 2 results, got {len(results)}"
        
        # First entry - should pass (regex command match, skip output)
        assert results[0].success, f"First entry should pass with regex command matching"
        
        # Second entry - should pass (exact command match, flexible output)
        assert results[1].success, f"Second entry should pass with flexible output matching"
        
    finally:
        os.unlink(author_file)
        os.unlink(student_file)


def test_command_line_integration():
    """Test command line integration by importing the modules."""
    try:
        # Test importing author module (should work without errors now)
        import sdrl.subcmd.author as author
        
        # Test importing instructor module
        import sdrl.subcmd.instructor as instructor
        
        # Test that new functions exist
        assert hasattr(author, 'validate_single_protocol_file'), "Author should have validate_single_protocol_file function"
        assert hasattr(instructor, 'check_protocol_files'), "Instructor should have check_protocol_files function"
        
    except ImportError as e:
        raise


