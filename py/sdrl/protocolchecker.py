"""
Command protocol checker for SeDriLa courses.

Based on docs/course_testing.md Section 2, this parses @PROT_SPEC blocks,
validates them, and compares author/student protocol files.
"""
import os
import re
import typing
from dataclasses import dataclass

import base as b
import mycrypt


@dataclass
class CheckRule:
    """Rule parsed from a single @PROT_SPEC block."""
    command_re: typing.Optional[str] = None
    output_re: typing.Optional[str] = None
    exitcode: typing.Optional[int] = None
    skip: bool = False
    manual: bool = False
    manual_text: typing.Optional[str] = None
    extra_text: typing.Optional[str] = None
    comment: typing.Optional[str] = None
    unknown_keys: typing.List[str] = None  # Track unknown key-value pairs for error reporting

    def __post_init__(self):
        if self.unknown_keys is None:
            self.unknown_keys = []


@dataclass
class ProtocolEntry:
    """Represents a single command execution entry in a protocol file."""
    command: str
    output: str
    line_number: int
    check_rule: typing.Optional[CheckRule] = None


@dataclass
class ProtocolFile:
    """Represents a complete protocol file with metadata."""
    filepath: str
    entries: list[ProtocolEntry]


@dataclass
class CheckResult:
    """Result of comparing a student entry with an author entry."""
    student_entry: typing.Optional[ProtocolEntry]
    author_entry: typing.Optional[ProtocolEntry]
    command_match: bool
    output_match: bool
    success: bool
    error_message: typing.Optional[str] = None
    requires_manual_check: bool = False
    manual_check_note: typing.Optional[str] = None


def filter_prot_check_annotations(content: str) -> str:
    """Remove @PROT_SPEC blocks before rendering."""
    lines: list[str] = []
    skipping = False
    extractor = ProtocolExtractor()
    for raw_line in content.split('\n'):
        line = raw_line.rstrip()
        if skipping:
            if extractor.prompt_regex.match(line):
                skipping = False
                lines.append(line)
            continue
        if line.strip() == "@PROT_SPEC":
            skipping = True
            continue
        lines.append(line)
    return '\n'.join(lines)


class ProtocolExtractor:
    """Extracts command entries from protocol files."""
    # Regex patterns for protocol format
    COMMAND_PATTERN = r'^\$\s+(.+)$'  # $ command only
    PROMPT_PATTERN = (
        r'(?P<front>^.*?)'
        r'(?P<userhost>[-\+\w]+@[-\+\w]+)'
        r'\s+(?P<dir>[/~]\S*)'
        r'\s+(?P<time>\d\d:\d\d:\d\d)'
        r'\s+(?P<num>\d+)'
        r'(?P<back>.*$)'
    )  # captures prompt components (front/environ, user@host, dir, time, counter, trailing text)
    def __init__(self):
        self.command_regex = re.compile(self.COMMAND_PATTERN)
        self.prompt_regex = re.compile(self.PROMPT_PATTERN)

    def extract_from_file(self, filepath: str) -> ProtocolFile:
        """Extract all command entries from a protocol file."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except (FileNotFoundError, UnicodeDecodeError, OSError) as e:
            b.error(f"Cannot read protocol file {filepath}: {e}")
            return ProtocolFile(filepath, [])
        return self.extract_from_content(content, filepath)

    def extract_from_content(self, content: str, filepath: str = "") -> ProtocolFile:
        """Extract command entries from protocol content."""
        lines = content.split('\n')
        entries: list[ProtocolEntry] = []
        pending_check_rule: typing.Optional[CheckRule] = None  # Rule waiting to be applied to next command
        current_command = None
        current_output_lines: list[str] = []
        current_line_num = 0
        current_command_rule: typing.Optional[CheckRule] = None  # Rule for the current command
        spec_lines: typing.Optional[list[str]] = None  # lines belonging to @PROT_SPEC block
        for line_num, raw_line in enumerate(lines, 1):
            line = raw_line.rstrip()
            if spec_lines is not None:
                if self.prompt_regex.match(line):
                    pending_check_rule = self._parse_check_rule(spec_lines)
                    spec_lines = None
                    continue
                spec_lines.append(line)
                continue
            if line.strip() == "@PROT_SPEC":
                spec_lines = []
                continue
            # Check for prompt line (user@host /path HH:MM:SS seq) and skip it
            prompt_match = self.prompt_regex.match(line)
            if prompt_match:
                continue
            # Check for command line
            command_match = self.command_regex.match(line)
            if command_match:
                # Save previous entry if exists
                if current_command is not None:
                    output = '\n'.join(current_output_lines).strip()
                    entries.append(
                        ProtocolEntry(current_command, output, current_line_num, current_command_rule)
                    )
                # Start new entry
                current_command = command_match.group(1).strip()
                current_output_lines = []
                current_line_num = line_num
                current_command_rule = pending_check_rule  # Apply pending rule to this command
                pending_check_rule = None  # Rule has been consumed
            else:
                # This is output from the previous command
                if current_command is not None:
                    current_output_lines.append(line)
        # Save final entry
        if current_command is not None:
            output = '\n'.join(current_output_lines).strip()
            entries.append(
                ProtocolEntry(current_command, output, current_line_num, current_command_rule)
            )
        return ProtocolFile(filepath, entries)

    def _parse_check_rule(self, spec_lines: list[str]) -> CheckRule:
        """Parse check rule from a @PROT_SPEC block (full lines)."""
        rule = CheckRule()
        manual_block: list[str] = []
        extra_block: list[str] = []
        comment_block: list[str] = []
        current_block: typing.Optional[tuple[str, list[str]]] = None
        known_keys = {'command_re', 'output_re', 'exitcode', 'skip', 'manual', 'extra', 'comment'}

        for raw_line in spec_lines:
            line = raw_line.rstrip()
            stripped = line.strip()
            if stripped.startswith("command_re="):
                rule.command_re = stripped[len("command_re="):].strip()
                current_block = None
                continue
            if stripped.startswith("output_re="):
                rule.output_re = stripped[len("output_re="):].strip()
                current_block = None
                continue
            if stripped.startswith("exitcode="):
                rule.exitcode = int(stripped[len("exitcode="):].strip())
                current_block = None
                continue
            if stripped.startswith("skip="):
                rule.skip = stripped[len("skip="):].strip() == "1"
                current_block = None
                continue
            if stripped.startswith("manual="):
                rule.manual = True
                inline = stripped[len("manual="):].strip()
                # Collect all manual text (inline or multiline)
                if inline:
                    manual_block.append(inline)
                current_block = ("manual", manual_block)
                continue
            if stripped.startswith("extra="):
                inline = stripped[len("extra="):].strip()
                if inline:
                    extra_block.append(inline)
                current_block = ("extra", extra_block)
                continue
            if stripped.startswith("comment="):
                inline = stripped[len("comment="):].strip()
                if inline:
                    comment_block.append(inline)
                current_block = ("comment", comment_block)
                continue
            # handle indented continuation (manual/extra/comment)
            if current_block and raw_line.startswith("    "):
                _, target = current_block
                target.append(raw_line[4:])
                continue
            # Detect unknown key-value pairs
            if '=' in stripped and stripped:
                # This line contains '=' but didn't match any known key
                key = stripped.split('=', 1)[0].strip()
                if key not in known_keys:
                    rule.unknown_keys.append(f"{key}={stripped.split('=', 1)[1].strip() if len(stripped.split('=', 1)) > 1 else ''}")
        rule.manual_text = "\n".join(manual_block) if manual_block else None
        rule.extra_text = "\n".join(extra_block) if extra_block else None
        rule.comment = "\n".join(comment_block) if comment_block else None
        return rule


class ProtocolValidator:
    """Validates protocol check annotations in author files."""

    def __init__(self):
        self.extractor = ProtocolExtractor()

    def validate_file(self, filepath: str) -> list[str]:
        """Validate protocol annotations in a file."""
        errors = []
        protocol = self.extractor.extract_from_file(filepath)
        for entry in protocol.entries:
            rule = entry.check_rule
            if rule:
                rule_errors = self._validate_check_rule(rule, entry.line_number)
                errors.extend([f"{filepath}:{err}" for err in rule_errors])
                # Check if the rule matches the actual command and output
                if not rule.skip:
                    if rule.command_re:
                        match_errors = self._validate_rule_matches_command(rule, entry, entry.line_number)
                        errors.extend([f"{filepath}:{err}" for err in match_errors])
                    if rule.output_re:
                        match_errors = self._validate_rule_matches_output(rule, entry, entry.line_number)
                        errors.extend([f"{filepath}:{err}" for err in match_errors])
        return errors

    def _validate_check_rule(self, rule: CheckRule, line_num: int) -> list[str]:
        """Validate a single check rule."""
        errors: list[str] = []
        # Check for unknown keys first
        if rule.unknown_keys:
            for unknown in rule.unknown_keys:
                key = unknown.split('=', 1)[0]
                errors.append(f"line {line_num}: Unknown key '{key}' in @PROT_SPEC block. "
                            f"Valid keys: command_re, output_re, exitcode, skip, manual, extra, comment")
        if rule.exitcode is not None and not (0 <= rule.exitcode <= 255):
            errors.append(f"line {line_num}: exitcode must be between 0 and 255 (got {rule.exitcode})")
        if rule.skip and (rule.command_re or rule.output_re or rule.manual or rule.exitcode is not None):
            errors.append(f"line {line_num}: skip cannot be combined with command_re/output_re/manual/exitcode")
        if rule.command_re:
            try:
                re.compile(rule.command_re)
            except re.error as e:
                errors.append(f"line {line_num}: Invalid command_re '{rule.command_re}': {e}")
        if rule.output_re:
            try:
                re.compile(rule.output_re)
            except re.error as e:
                errors.append(f"line {line_num}: Invalid output_re '{rule.output_re}': {e}")
        if rule.manual and not rule.manual_text:
            errors.append(f"line {line_num}: manual requires inline text or continuation lines")
        if not any([rule.command_re, rule.output_re, rule.skip, rule.manual]) and not rule.unknown_keys:
            errors.append(f"line {line_num}: specification contains neither automated check nor manual/skip")
        if rule.extra_text and not any([rule.command_re, rule.output_re, rule.skip, rule.manual]):
            errors.append(f"line {line_num}: extra= without command_re/output_re/skip/manual is not useful")
        return errors

    def _validate_rule_matches_command(self, rule: CheckRule, entry: ProtocolEntry, line_num: int) -> list[str]:
        """Validate that a command_re pattern actually matches the command that follows the @PROT_SPEC block."""
        errors: list[str] = []
        if rule.command_re:
            try:
                if not re.search(rule.command_re, entry.command.strip()):
                    errors.append(f"line {line_num}: command_re pattern '{rule.command_re}' does not match the following command: {entry.command.strip()}")
            except re.error as e:
                errors.append(f"line {line_num}: Invalid command_re '{rule.command_re}': {e}")
        return errors

    def _validate_rule_matches_output(self, rule: CheckRule, entry: ProtocolEntry, line_num: int) -> list[str]:
        """Validate that an output_re pattern actually matches the output that follows the command."""
        errors: list[str] = []
        if rule.output_re:
            try:
                if not re.search(rule.output_re, entry.output):
                    output_preview = entry.output[:100] + "..." if len(entry.output) > 100 else entry.output
                    errors.append(f"line {line_num}: output_re pattern '{rule.output_re}' does not match the following output: {repr(output_preview)}")
            except re.error as e:
                errors.append(f"line {line_num}: Invalid output_re '{rule.output_re}': {e}")
        return errors


class ProtocolChecker:
    """Compares student and author protocol files."""

    def __init__(self):
        self.extractor = ProtocolExtractor()

    def compare_files(self, student_file: str, author_file: str) -> list[CheckResult]:
        """Compare student protocol file with author protocol file."""
        student_protocol = self.extractor.extract_from_file(student_file)
        author_protocol = self.extractor.extract_from_file(author_file)
        results = []
        # Compare each author entry with corresponding student entry
        for i, author_entry in enumerate(author_protocol.entries):
            if i >= len(student_protocol.entries):
                # Student has fewer entries than author
                result = CheckResult(
                    student_entry=None,
                    author_entry=author_entry,
                    command_match=False,
                    output_match=False,
                    success=False,
                    error_message=f"Student file has only {len(student_protocol.entries)} entries, but author file has {len(author_protocol.entries)}",
                )
                results.append(result)
                continue
            student_entry = student_protocol.entries[i]
            result = self._compare_entries(student_entry, author_entry)
            results.append(result)
        # Check if student has more entries than author
        if len(student_protocol.entries) > len(author_protocol.entries):
            for i in range(len(author_protocol.entries), len(student_protocol.entries)):
                student_entry = student_protocol.entries[i]
                result = CheckResult(
                    student_entry=student_entry,
                    author_entry=None,
                    command_match=False,
                    output_match=False,
                    success=False,
                    error_message=f"Student has extra entry at position {i+1}",
                )
                results.append(result)
        return results

    def _compare_entries(self, student_entry: ProtocolEntry, author_entry: ProtocolEntry) -> CheckResult:
        """Compare a single student entry with author entry."""
        rule = author_entry.check_rule or CheckRule(skip=True)  # default to skip when no spec exists
        if rule.skip:
            return CheckResult(
                student_entry=student_entry,
                author_entry=author_entry,
                command_match=True,
                output_match=True,
                success=True,
                requires_manual_check=False,
                manual_check_note=None,
            )
        # Perform automated checks if any regex rules exist
        command_match = self._compare_command(student_entry.command, rule)
        output_match = self._compare_output(student_entry.output, rule)
        success = command_match and output_match
        error_message = None
        if not success:
            error_parts = []
            if not command_match:
                if rule.command_re:
                    error_parts.append(f"command mismatch (pattern: {rule.command_re}, actual: {student_entry.command.strip()})")
                else:
                    error_parts.append("command mismatch")
            if not output_match:
                if rule.output_re:
                    error_parts.append(f"output mismatch (pattern: {rule.output_re})")
                else:
                    error_parts.append("output mismatch")
            error_message = "; ".join(error_parts)
        # Determine if manual check is required
        # Manual check only applies when no automated checks exist
        has_automated_check = rule.command_re or rule.output_re
        requires_manual = rule.manual and not has_automated_check
        return CheckResult(
            student_entry=student_entry,
            author_entry=author_entry,
            command_match=command_match,
            output_match=output_match,
            success=success,
            error_message=error_message,
            requires_manual_check=requires_manual,
            manual_check_note=rule.manual_text or "Manual check required" if requires_manual else None,
        )

    def _compare_command(self, student_cmd: str, rule: CheckRule) -> bool:
        """Compare student command against the rule's command_re pattern."""
        if rule.command_re:
            return bool(re.search(rule.command_re, student_cmd.strip()))
        return True

    def _compare_output(self, student_output: str, rule: CheckRule) -> bool:
        """Compare student output against the rule's output_re pattern."""
        if rule.output_re:
            return bool(re.search(rule.output_re, student_output))
        return True


def load_encrypted_prot_file(prot_crypt_path: str) -> typing.Optional[str]:
    """Load and decrypt a .prot.crypt file. GPG will request passphrase via gpg-agent if needed."""
    if not os.path.exists(prot_crypt_path):
        return None
    try:
        ciphertext = b.slurp_bytes(prot_crypt_path)
        plaintext = mycrypt.decrypt_gpg(ciphertext)
        return plaintext.decode('utf-8')
    except (OSError, RuntimeError, UnicodeDecodeError) as e:
        b.warning(f"Failed to decrypt {prot_crypt_path}: {e}")
        return None
