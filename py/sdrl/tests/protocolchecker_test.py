# pytest tests for protocolchecker
import tempfile
import textwrap

import sdrl.protocolchecker as protocolchecker


def _dedent(payload: str) -> str:
    return textwrap.dedent(payload).lstrip()


def test_extracts_spec_and_rules():
    """Verify @PROT_SPEC blocks are parsed and rules extracted."""
    sample_content = _dedent(
        """
        @PROT_SPEC
        command_re=^ls -la$
        output_re=^total
        manual=Please check the file count
            There should be at least 3 files
        extra=Additional notes
        user@host /home/user 10:00:00 1
        $ ls -la
        total 16
        file.txt

        user@host /home/user 10:01:00 2
        $ echo "done"
        done
        """
    )
    extractor = protocolchecker.ProtocolExtractor()
    protocol = extractor.extract_from_content(sample_content)
    assert protocol.total_entries == 2, f"Expected 2 entries, got {protocol.total_entries}"
    first = protocol.entries[0]
    assert first.command == "ls -la", f"Unexpected command {first.command}"
    assert "total 16" in first.output, f"Missing expected output in {first.output}"
    assert first.check_rule is not None, "check_rule should be populated"
    assert first.check_rule.command_re == "^ls -la$", f"Unexpected command_re {first.check_rule.command_re}"
    assert first.check_rule.output_re == "^total", f"Unexpected output_re {first.check_rule.output_re}"
    assert first.check_rule.manual_text == "Please check the file count\nThere should be at least 3 files", (
        f"Unexpected manual text {first.check_rule.manual_text}"
    )
    assert first.check_rule.extra_text == "Additional notes", f"Unexpected extra text {first.check_rule.extra_text}"


def test_validate_rejects_invalid_spec():
    """Ensure skip mixing and invalid regexes are rejected."""
    invalid_content = _dedent(
        """
        @PROT_SPEC
        skip=1
        command_re=^ls$
        user@host /tmp 10:00:00 1
        $ ls
        file

        @PROT_SPEC
        output_re=[unclosed
        user@host /tmp 10:01:00 2
        $ echo "x"
        x
        """
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".prot") as f:
        f.write(invalid_content)
        f.flush()
        errors = protocolchecker.ProtocolValidator().validate_file(f.name)
    assert any("skip cannot be combined" in e for e in errors), "Expected skip+regex error"
    assert any("Invalid output_re" in e for e in errors), "Expected invalid regex error"


def test_compare_respects_skip_manual_and_regex():
    """Comparison results should honor skip, manual, and regex rules."""
    author_content = _dedent(
        r"""
        @PROT_SPEC
        command_re=^echo ok$
        output_re=^OK$
        user@host /tmp 10:00:00 1
        $ echo ok
        OK

        @PROT_SPEC
        skip=1
        user@host /tmp 10:01:00 2
        $ should_be_skipped
        anything

        @PROT_SPEC
        manual=Manual review required
            Check whether the output contains a version number
        user@host /tmp 10:02:00 3
        $ echo version
        v1.2.3
        """
    )
    student_content = _dedent(
        """
        student@laptop /tmp 11:00:00 1
        $ echo ok
        OK

        student@laptop /tmp 11:01:00 2
        $ totally_different
        mismatched output

        student@laptop /tmp 11:02:00 3
        $ echo version
        wrong output
        """
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".prot") as author_f, tempfile.NamedTemporaryFile(
        mode="w", suffix=".prot"
    ) as student_f:
        author_f.write(author_content)
        author_f.flush()
        student_f.write(student_content)
        student_f.flush()
        results = protocolchecker.ProtocolChecker().compare_files(student_f.name, author_f.name)

    assert len(results) == 3, f"Expected 3 results, got {len(results)}"
    assert results[0].success, "First entry should succeed"
    assert not results[0].requires_manual_check, "First entry should not need manual review"
    assert results[1].success, "Skipped entry should succeed"
    assert not results[1].requires_manual_check, "Skipped entry should not require manual review"
    assert results[2].success, "Manual entry should succeed"
    assert results[2].requires_manual_check, "Manual entry should require manual review"
    assert "Manual review required" in (results[2].manual_check_note or ""), "Manual note missing expected text"

def test_filter_removes_spec_blocks():
    """Filtering should keep prompts and commands but drop spec blocks."""
    content = _dedent(
        """
        @PROT_SPEC
        command_re=^echo hi$
        user@host /tmp 10:00:00 1
        $ echo hi
        hi
        """
    )
    filtered = protocolchecker.filter_prot_check_annotations(content)
    assert "@PROT_SPEC" not in filtered, "Spec markers should be stripped"
    assert "command_re" not in filtered, "Spec body should be removed"
    assert "$ echo hi" in filtered, "Command should remain"
    assert "user@host" in filtered, "Prompt should remain"


def test_default_manual_when_no_spec():
    """Without specs we default to skip."""
    author_content = _dedent(
        """
        user@host /tmp 10:00:00 1
        $ echo expected
        expected
        """
    )
    student_content = _dedent(
        """
        student@host /tmp 10:00:00 1
        $ echo different
        different
        """
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".prot") as author_f, tempfile.NamedTemporaryFile(
        mode="w", suffix=".prot"
    ) as student_f:
        author_f.write(author_content)
        author_f.flush()
        student_f.write(student_content)
        student_f.flush()
        result = protocolchecker.ProtocolChecker().compare_files(student_f.name, author_f.name)[0]
    assert result.success, "Comparison should succeed without specs (default to skip)"
    assert not result.requires_manual_check, "Missing specs should default to skip (no manual review)"
    assert result.manual_check_note is None, "Skip mode should not have manual note"


def test_warns_when_manual_without_text():
    """Ensure manual without inline text or continuation lines triggers an error."""
    content_with_error = _dedent(
        """
        @PROT_SPEC
        manual=
        user@host /tmp 10:00:00 1
        $ echo test
        test
        """
    )
    content_ok_inline = _dedent(
        """
        @PROT_SPEC
        manual=Please inspect the output
        user@host /tmp 10:00:00 1
        $ echo test
        test
        """
    )
    content_ok_continuation = _dedent(
        """
        @PROT_SPEC
        manual=
            Please inspect the output
        user@host /tmp 10:00:00 1
        $ echo test
        test
        """
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".prot") as f:
        f.write(content_with_error)
        f.flush()
        errors = protocolchecker.ProtocolValidator().validate_file(f.name)
        assert any("manual requires inline text or continuation lines" in e for e in errors)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".prot") as f:
        f.write(content_ok_inline)
        f.flush()
        errors = protocolchecker.ProtocolValidator().validate_file(f.name)
        assert not any("manual requires" in e for e in errors)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".prot") as f:
        f.write(content_ok_continuation)
        f.flush()
        errors = protocolchecker.ProtocolValidator().validate_file(f.name)
        assert not any("manual requires" in e for e in errors)


def test_detects_unknown_keys():
    """Ensure unknown keys (like typos) are detected and reported."""
    content_with_typo = _dedent(
        """
        @PROT_SPEC
        sskp=1
        output_re=^result$
        user@host /tmp 10:00:00 1
        $ echo test
        result
        """
    )
    content_with_unknown = _dedent(
        """
        @PROT_SPEC
        unknown_key=value
        command_re=^ls$
        user@host /tmp 10:00:00 1
        $ ls
        file.txt
        """
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".prot") as f:
        f.write(content_with_typo)
        f.flush()
        errors = protocolchecker.ProtocolValidator().validate_file(f.name)
        assert any("Unknown key 'sskp'" in e for e in errors), f"Expected unknown key error, got: {errors}"
        assert any("Valid keys:" in e for e in errors), "Expected valid keys list in error message"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".prot") as f:
        f.write(content_with_unknown)
        f.flush()
        errors = protocolchecker.ProtocolValidator().validate_file(f.name)
        assert any("Unknown key 'unknown_key'" in e for e in errors), f"Expected unknown key error, got: {errors}"


def test_extra_without_checks_warns():
    """Ensure extra= without any checks produces a warning."""
    content_extra_only = _dedent(
        """
        @PROT_SPEC
        extra=This is additional info
        user@host /tmp 10:00:00 1
        $ echo test
        test
        """
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".prot") as f:
        f.write(content_extra_only)
        f.flush()
        errors = protocolchecker.ProtocolValidator().validate_file(f.name)
        assert any("extra= without command_re/output_re/skip/manual" in e for e in errors), \
            f"Expected warning about extra= without checks, got: {errors}"
