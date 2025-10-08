"""
Command protocol checker for SeDriLa courses.

This module provides functionality to validate and compare command protocol (.prot) files
that contain command line execution logs from students and authors.
"""
import json
import re
import typing as tg
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

import base as b


@dataclass
class CheckRule:
    """Validation rule for a specific command or output."""
    command_type: str = "exact"  # exact, regex, multi_variant, skip
    output_type: str = "exact"   # exact, regex, flexible, skip
    variants: tg.Optional[list[str]] = None  # For multi_variant command type
    regex_pattern: tg.Optional[str] = None   # For regex types
    manual_check_note: tg.Optional[str] = None  # Note for manual checking


@dataclass
class ProtocolEntry:
    """Represents a single command execution entry in a protocol file."""
    command: str
    output: str
    line_number: int
    check_rule: tg.Optional[CheckRule] = None


@dataclass
class ProtocolFile:
    """Represents a complete protocol file with metadata."""
    filepath: str
    entries: list[ProtocolEntry]
    total_entries: int
    
    def __str__(self) -> str:
        return f"Protocol file {self.filepath} with {self.total_entries} entries"


@dataclass
class CheckResult:
    """Result of comparing a student entry with an author entry."""
    student_entry: ProtocolEntry
    author_entry: ProtocolEntry
    command_match: bool
    output_match: bool
    success: bool
    error_message: tg.Optional[str] = None
    requires_manual_check: bool = False
    manual_check_note: tg.Optional[str] = None


class ProtocolExtractor:
    """Extracts command entries from protocol files."""
    
    # Regex patterns for protocol format
    COMMAND_PATTERN = r'^\$\s+(.+)$'  # $ command only
    CHECK_ANNOTATION_PATTERN = r'^#\s*@PROT_CHECK:\s*(.+)$'
    PROMPT_PATTERN = r'^\S+@\S+\s+\S+\s+\d{2}:\d{2}:\d{2}\s+\d+$'  # user@host /path HH:MM:SS seq
    
    def __init__(self):
        self.command_regex = re.compile(self.COMMAND_PATTERN)
        self.annotation_regex = re.compile(self.CHECK_ANNOTATION_PATTERN)
        self.prompt_regex = re.compile(self.PROMPT_PATTERN)
    
    def extract_from_file(self, filepath: str) -> ProtocolFile:
        """Extract all command entries from a protocol file."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            b.error(f"Cannot read protocol file {filepath}: {e}")
            return ProtocolFile(filepath, [], 0)
        
        return self.extract_from_content(content, filepath)
    
    def extract_from_content(self, content: str, filepath: str = "") -> ProtocolFile:
        """Extract command entries from protocol content."""
        lines = content.split('\n')
        entries = []
        pending_check_rule = None  # Rule waiting to be applied to next command
        current_command = None
        current_output_lines = []
        current_line_num = 0
        current_command_rule = None  # Rule for the current command
        
        for line_num, line in enumerate(lines, 1):
            line = line.rstrip()
            
            # Check for protocol check annotations
            annotation_match = self.annotation_regex.match(line)
            if annotation_match:
                pending_check_rule = self._parse_check_rule(annotation_match.group(1))
                continue
            
            # Check for prompt line (user@host /path HH:MM:SS seq) - skip it
            prompt_match = self.prompt_regex.match(line)
            if prompt_match:
                continue
            
            # Check for command line
            command_match = self.command_regex.match(line)
            if command_match:
                # Save previous entry if exists
                if current_command is not None:
                    output = '\n'.join(current_output_lines).strip()
                    entries.append(ProtocolEntry(
                        current_command, output, current_line_num, current_command_rule
                    ))
                
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
            entries.append(ProtocolEntry(
                current_command, output, current_line_num, current_command_rule
            ))
        
        return ProtocolFile(filepath, entries, len(entries))
    
    def _parse_check_rule(self, rule_text: str) -> CheckRule:
        """Parse check rule from @PROT_CHECK annotation."""
        rule = CheckRule()
        
        # Parse key=value pairs
        for part in rule_text.split(','):
            part = part.strip()
            if '=' in part:
                key, value = part.split('=', 1)
                key = key.strip().lower()
                value = value.strip().strip('"\'')
                
                if key == 'command':
                    if value in ['exact', 'regex', 'multi_variant', 'skip']:
                        rule.command_type = value
                    else:
                        b.warning(f"Invalid command type in @PROT_CHECK: {value}")
                elif key == 'output':
                    if value in ['exact', 'regex', 'flexible', 'skip']:
                        rule.output_type = value
                    else:
                        b.warning(f"Invalid output type in @PROT_CHECK: {value}")
                elif key == 'regex':
                    rule.regex_pattern = value
                elif key == 'variants':
                    # Parse comma-separated variants within quotes
                    rule.variants = [v.strip().strip('"\'') for v in value.split('|')]
                elif key == 'manual_note':
                    rule.manual_check_note = value
        
        return rule


class ProtocolValidator:
    """Validates protocol check annotations in author files."""
    
    def __init__(self):
        self.extractor = ProtocolExtractor()
    
    def validate_file(self, filepath: str) -> list[str]:
        """
        Validate protocol annotations in a file.
        
        Returns:
            list[str]: List of validation error messages
        """
        errors = []
        
        try:
            protocol = self.extractor.extract_from_file(filepath)
        except Exception as e:
            errors.append(f"Cannot parse protocol file {filepath}: {e}")
            return errors
        
        for entry in protocol.entries:
            if entry.check_rule:
                rule_errors = self._validate_check_rule(entry.check_rule, entry.line_number)
                errors.extend([f"{filepath}:{err}" for err in rule_errors])
        
        return errors
    
    def _validate_check_rule(self, rule: CheckRule, line_num: int) -> list[str]:
        """Validate a single check rule."""
        errors = []
        
        # Validate command type
        if rule.command_type not in ['exact', 'regex', 'multi_variant', 'skip']:
            errors.append(f"line {line_num}: Invalid command type '{rule.command_type}'")
        
        # Validate output type
        if rule.output_type not in ['exact', 'regex', 'flexible', 'skip']:
            errors.append(f"line {line_num}: Invalid output type '{rule.output_type}'")
        
        # Validate regex pattern if needed
        if (rule.command_type == 'regex' or rule.output_type == 'regex') and not rule.regex_pattern:
            errors.append(f"line {line_num}: regex type specified but no regex pattern provided")
        
        if rule.regex_pattern:
            try:
                re.compile(rule.regex_pattern)
            except re.error as e:
                errors.append(f"line {line_num}: Invalid regex pattern '{rule.regex_pattern}': {e}")
        
        # Validate variants for multi_variant
        if rule.command_type == 'multi_variant' and not rule.variants:
            errors.append(f"line {line_num}: multi_variant type specified but no variants provided")
        
        return errors


class ProtocolChecker:
    """Compares student and author protocol files."""
    
    def __init__(self):
        self.extractor = ProtocolExtractor()
    
    def compare_files(self, student_file: str, author_file: str) -> list[CheckResult]:
        """
        Compare student protocol file with author protocol file.
        
        Returns:
            list[CheckResult]: Results of comparison for each entry
        """
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
                    error_message=f"Student file has only {len(student_protocol.entries)} entries, but author file has {len(author_protocol.entries)}"
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
                    error_message=f"Student has extra entry at position {i+1}"
                )
                results.append(result)
        
        return results
    
    def _compare_entries(self, student_entry: ProtocolEntry, author_entry: ProtocolEntry) -> CheckResult:
        """Compare a single student entry with author entry."""
        rule = author_entry.check_rule or CheckRule()  # Use default rule if none specified
        
        # Check if this requires manual checking
        if rule.command_type == 'skip' or rule.output_type == 'skip':
            return CheckResult(
                student_entry=student_entry,
                author_entry=author_entry,
                command_match=True,  # Skip means we don't check
                output_match=True,   # Skip means we don't check
                success=True,
                requires_manual_check=True,
                manual_check_note=rule.manual_check_note or "Manual check required"
            )
        
        # Check command
        command_match = self._compare_command(student_entry.command, author_entry.command, rule)
        
        # Check output
        output_match = self._compare_output(student_entry.output, author_entry.output, rule)
        
        success = command_match and output_match
        error_message = None
        
        if not success:
            error_parts = []
            if not command_match:
                error_parts.append("command mismatch")
            if not output_match:
                error_parts.append("output mismatch")
            error_message = "; ".join(error_parts)
        
        return CheckResult(
            student_entry=student_entry,
            author_entry=author_entry,
            command_match=command_match,
            output_match=output_match,
            success=success,
            error_message=error_message
        )
    
    def _compare_command(self, student_cmd: str, author_cmd: str, rule: CheckRule) -> bool:
        """Compare commands based on the rule."""
        if rule.command_type == "exact":
            return student_cmd.strip() == author_cmd.strip()
        elif rule.command_type == "regex":
            if rule.regex_pattern:
                return bool(re.search(rule.regex_pattern, student_cmd))
            else:
                # Fallback to exact match if no regex provided
                return student_cmd.strip() == author_cmd.strip()
        elif rule.command_type == "multi_variant":
            if rule.variants:
                return any(student_cmd.strip() == variant.strip() for variant in rule.variants)
            else:
                # Fallback to exact match if no variants provided
                return student_cmd.strip() == author_cmd.strip()
        elif rule.command_type == "skip":
            return True  # Skip means always pass
        else:
            # Default to exact match
            return student_cmd.strip() == author_cmd.strip()
    
    def _compare_output(self, student_output: str, author_output: str, rule: CheckRule) -> bool:
        """Compare outputs based on the rule."""
        if rule.output_type == "exact":
            return student_output.strip() == author_output.strip()
        elif rule.output_type == "regex":
            if rule.regex_pattern:
                return bool(re.search(rule.regex_pattern, student_output))
            else:
                # Fallback to exact match if no regex provided
                return student_output.strip() == author_output.strip()
        elif rule.output_type == "flexible":
            # Flexible matching: ignore whitespace differences and empty lines
            student_lines = [line.strip() for line in student_output.split('\n') if line.strip()]
            author_lines = [line.strip() for line in author_output.split('\n') if line.strip()]
            return student_lines == author_lines
        elif rule.output_type == "skip":
            return True  # Skip means always pass
        else:
            # Default to exact match
            return student_output.strip() == author_output.strip()


class ProtocolReporter:
    """Generates reports for protocol checking results."""
    
    @staticmethod
    def print_summary(results: list[CheckResult], student_file: str = "", author_file: str = ""):
        """Print a summary of protocol checking results."""
        if not results:
            b.info("No protocol entries to check.")
            return
        
        total_entries = len(results)
        successful = sum(1 for r in results if r.success)
        failed = sum(1 for r in results if not r.success)
        manual_check = sum(1 for r in results if r.requires_manual_check)
        
        b.info(f"Protocol checking results:")
        if student_file and author_file:
            b.info(f"  Student file: {student_file}")
            b.info(f"  Author file: {author_file}")
        b.info(f"  Total entries: {total_entries}")
        b.info(f"  Passed: {successful}")
        b.info(f"  Failed: {failed}")
        b.info(f"  Manual check required: {manual_check}")
        
        # Show failed entries
        if failed > 0:
            b.info("\nFailed entries:")
            for i, result in enumerate(results):
                if not result.success and not result.requires_manual_check:
                    b.info(f"  Entry {i+1}: {result.error_message}")
                    if result.student_entry:
                        b.info(f"    Student command: {result.student_entry.command}")
                    if result.author_entry:
                        b.info(f"    Expected command: {result.author_entry.command}")
        
        # Show manual check entries
        if manual_check > 0:
            b.info("\nEntries requiring manual check:")
            for i, result in enumerate(results):
                if result.requires_manual_check:
                    note = result.manual_check_note or "Manual verification required"
                    b.info(f"  Entry {i+1}: {note}")
                    if result.student_entry:
                        b.info(f"    Student command: {result.student_entry.command}")
    
    @staticmethod
    def generate_json_report(results: list[CheckResult], output_file: str = "protocol_check_report.json"):
        """Generate JSON report of protocol checking results."""
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "total_entries": len(results),
            "successful": sum(1 for r in results if r.success),
            "failed": sum(1 for r in results if not r.success),
            "manual_check_required": sum(1 for r in results if r.requires_manual_check),
            "results": []
        }
        
        for i, result in enumerate(results):
            result_data = {
                "entry_number": i + 1,
                "success": result.success,
                "command_match": result.command_match,
                "output_match": result.output_match,
                "requires_manual_check": result.requires_manual_check,
                "error_message": result.error_message,
                "manual_check_note": result.manual_check_note
            }
            
            if result.student_entry:
                result_data["student_command"] = result.student_entry.command
                result_data["student_output"] = result.student_entry.output
            
            if result.author_entry:
                result_data["author_command"] = result.author_entry.command
                result_data["author_output"] = result.author_entry.output
            
            report_data["results"].append(result_data)
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
            b.info(f"JSON report saved to: {output_file}")
        except Exception as e:
            b.error(f"Failed to save JSON report to {output_file}: {e}")
    
    @staticmethod
    def generate_markdown_report(results: list[CheckResult], output_file: str = "protocol_check_report.md"):
        """Generate Markdown report of protocol checking results."""
        if not results:
            return
        
        total_entries = len(results)
        successful = sum(1 for r in results if r.success)
        failed = sum(1 for r in results if not r.success)
        manual_check = sum(1 for r in results if r.requires_manual_check)
        
        report_lines = [
            "# Protocol Checking Report",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Summary",
            "",
            f"- **Total entries:** {total_entries}",
            f"- **Passed:** {successful}",
            f"- **Failed:** {failed}",
            f"- **Manual check required:** {manual_check}",
            ""
        ]
        
        if failed > 0:
            report_lines.extend([
                "## Failed Entries",
                ""
            ])
            
            for i, result in enumerate(results):
                if not result.success and not result.requires_manual_check:
                    report_lines.extend([
                        f"### Entry {i+1}",
                        "",
                        f"**Error:** {result.error_message}",
                        ""
                    ])
                    
                    if result.student_entry:
                        report_lines.extend([
                            "**Student command:**",
                            f"```bash",
                            result.student_entry.command,
                            "```",
                            ""
                        ])
                    
                    if result.author_entry:
                        report_lines.extend([
                            "**Expected command:**",
                            f"```bash",
                            result.author_entry.command,
                            "```",
                            ""
                        ])
        
        if manual_check > 0:
            report_lines.extend([
                "## Manual Check Required",
                ""
            ])
            
            for i, result in enumerate(results):
                if result.requires_manual_check:
                    note = result.manual_check_note or "Manual verification required"
                    report_lines.extend([
                        f"### Entry {i+1}",
                        "",
                        f"**Note:** {note}",
                        ""
                    ])
                    
                    if result.student_entry:
                        report_lines.extend([
                            "**Student command:**",
                            f"```bash",
                            result.student_entry.command,
                            "```",
                            ""
                        ])
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(report_lines))
            b.info(f"Markdown report saved to: {output_file}")
        except Exception as e:
            b.error(f"Failed to save Markdown report to {output_file}: {e}")
