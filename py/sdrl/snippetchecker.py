"""
Snippet extraction and inclusion functionality for sedrila.
Allows extracting code snippets from solution files and including them in task files.
"""
import dataclasses
import os
import re
from typing import Callable, Optional

import base as b
import sdrl.constants as c
import sdrl.macros as macros

IDENTIFIER_RE = re.compile(r'^[A-Za-z0-9_]+$')


@dataclasses.dataclass
class CodeSnippet:
    """Represents an extracted code snippet."""
    snippet_id: str
    content: str
    source_file: str
    start_line: int
    end_line: int


class SnippetExtractor:
    """Extracts code snippets from files."""
    GENERIC_START_RE = re.compile(
        r'^SNIPPET::(?P<id>[A-Za-z0-9_]+)$'
    )
    GENERIC_END_RE = re.compile(
        r'^ENDSNIPPET(?:\s*::\s*(?P<id>[A-Za-z0-9_]+))?$'
    )
    BLOCK_WRAPPERS = (
        ("<!--", "-->"),
        ("/*", "*/"),
        ("(*", "*)"),
        ("{-", "-}"),
        ("{#", "#}"),
    )
    SINGLE_LINE_PREFIXES = (
        "//",
        "--",
        "#",
        ";",
        "!",
        "%",
        "'",
    )
    END_MARKER_SENTINEL = object()

    @dataclasses.dataclass
    class _SnippetContext:
        snippet_id: str
        marker_line: int
        start_line: int
        lines: list[str]

    def extract_snippets_from_content(
        self,
        content: str,
        filename: str,
        collect_errors: bool = False
    ) -> tuple[list[CodeSnippet], list[str]]:
        """Extract all snippets from file content based on SNIPPET markers."""
        snippets: list[CodeSnippet] = []
        errors: list[str] = []
        lines = content.split('\n')
        stack: list[SnippetExtractor._SnippetContext] = []
        for index, line in enumerate(lines):
            line_number = index + 1
            snippet_id = self._match_start_marker(line)
            if snippet_id:
                ctx = self._SnippetContext(
                    snippet_id=snippet_id,
                    marker_line=line_number,
                    start_line=line_number + 1,
                    lines=[]
                )
                stack.append(ctx)
                continue
            end_match = self._match_end_marker(line)
            if end_match is not None:
                end_id = None if end_match is self.END_MARKER_SENTINEL else end_match
                if not stack:
                    self._report_error(
                        errors,
                        collect_errors,
                        filename,
                        f"Unexpected ENDSNIPPET at line {line_number}"
                    )
                    continue
                current = stack[-1]
                if end_id and end_id != current.snippet_id:
                    self._report_error(
                        errors,
                        collect_errors,
                        filename,
                        f"Mismatched snippet end marker: expected '{current.snippet_id}', "
                        f"got '{end_id}' at line {line_number}"
                    )
                    continue
                stack.pop()
                snippet_content = '\n'.join(current.lines)
                snippets.append(CodeSnippet(
                    snippet_id=current.snippet_id,
                    content=snippet_content,
                    source_file=filename,
                    start_line=current.start_line,
                    end_line=line_number - 1
                ))
                continue
            if stack:
                for ctx in stack:
                    ctx.lines.append(line)
        for ctx in stack:
            self._report_error(
                errors,
                collect_errors,
                filename,
                f"Unclosed snippet '{ctx.snippet_id}' starting at line {ctx.marker_line}"
            )
        return snippets, errors

    def _match_start_marker(self, line: str) -> Optional[str]:
        normalized = self._normalize_comment_line(line)
        if not normalized:
            return None
        match = self.GENERIC_START_RE.fullmatch(normalized)
        if match:
            return match.group('id')
        return None

    def _match_end_marker(self, line: str) -> Optional[object]:
        normalized = self._normalize_comment_line(line)
        if not normalized:
            return None
        match = self.GENERIC_END_RE.fullmatch(normalized)
        if match:
            end_id = match.group('id')
            return end_id if end_id else self.END_MARKER_SENTINEL
        return None

    def _normalize_comment_line(self, line: str) -> str:
        stripped = line.strip()
        if not stripped:
            return ""
        for start, end in self.BLOCK_WRAPPERS:
            if stripped.startswith(start) and stripped.endswith(end):
                stripped = stripped[len(start):-len(end)].strip()
                break
        while True:
            lowered = stripped.lower()
            if lowered.startswith("rem "):
                stripped = stripped[3:].lstrip()
                continue
            removed_prefix = False
            for prefix in self.SINGLE_LINE_PREFIXES:
                if stripped.startswith(prefix):
                    stripped = stripped[len(prefix):].lstrip()
                    removed_prefix = True
                    break
            if not removed_prefix:
                break
        return stripped.strip()

    def _report_error(
        self,
        errors: list[str],
        collect_errors: bool,
        filename: str,
        message: str
    ):
        if collect_errors:
            errors.append(message)
        else:
            b.warning(message, file=filename)
    
    def extract_snippets_from_file(self, filepath: str) -> list[CodeSnippet]:
        """Extract all snippets from a file."""
        if not os.path.exists(filepath):
            b.warning(f"File not found: {filepath}")
            return []
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        snippets, _ = self.extract_snippets_from_content(content, filepath, collect_errors=False)
        return snippets
@dataclasses.dataclass
class SnippetReference:
    """Represents a reference to a code snippet."""
    snippet_id: str
    source_file: str
    line_number: int
    filespec: str | None = None


@dataclasses.dataclass
class SnippetValidationResult:
    """Result of validating a snippet reference."""
    reference: SnippetReference
    success: bool
    snippet: Optional[CodeSnippet] = None
    error_message: Optional[str] = None


class SnippetReferenceExtractor:
    """Extracts snippet references from task files."""
    MACRO_PATTERN = re.compile(macros.macro_regexp)
    @staticmethod
    def _find_comment_ranges(content: str) -> list[tuple[int, int]]:
        """Return list of (start,end) ranges for HTML comments in content."""
        ranges: list[tuple[int, int]] = []
        idx = 0
        while True:
            start = content.find("<!--", idx)
            if start == -1:
                break
            end = content.find("-->", start + 4)
            if end == -1:
                break
            ranges.append((start, end + 3))
            idx = end + 3
        return ranges

    @staticmethod
    def _inside_comment(pos: int, ranges: list[tuple[int, int]]) -> bool:
        for start, end in ranges:
            if start <= pos < end:
                return True
        return False

    def extract_references_from_content(
        self,
        content: str,
        filename: str
    ) -> list[SnippetReference]:
        """Extract all snippet references from content."""
        references_with_pos: list[tuple[int, SnippetReference]] = []
        comment_ranges = self._find_comment_ranges(content)
        for match in self.MACRO_PATTERN.finditer(content):
            if self._inside_comment(match.start(), comment_ranges):
                continue
            if match.group('name') != 'SNIPPET':
                continue
            snippet_id = (match.group('arg2') or "").strip()
            if not snippet_id or not IDENTIFIER_RE.fullmatch(snippet_id):
                continue
            filespec_raw = (match.group('arg1') or "").strip()
            filespec = filespec_raw or None
            if filespec is not None:
                filespec = _normalize_filespec_value(filespec)
            reference = SnippetReference(
                snippet_id=snippet_id,
                source_file=filename,
                line_number=content.count('\n', 0, match.start()) + 1,
                filespec=filespec,
            )
            references_with_pos.append((match.start(), reference))
        references_with_pos.sort(key=lambda item: item[0])
        return [ref for _, ref in references_with_pos]

    def extract_references_from_file(self, filepath: str) -> list[SnippetReference]:
        """Extract all snippet references from a file."""
        if not os.path.exists(filepath):
            return []
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        return self.extract_references_from_content(content, filepath)


def _normalize_filespec_value(filespec: str) -> str:
    """Normalize shorthand filespecs such as 'ALT' to 'ALT:'."""
    trimmed = filespec.strip()
    shorthand = {
        c.AUTHOR_ALTDIR_PREFIX.rstrip(':'): c.AUTHOR_ALTDIR_PREFIX,
        c.AUTHOR_ITREEDIR_PREFIX.rstrip(':'): c.AUTHOR_ITREEDIR_PREFIX,
    }
    return shorthand.get(trimmed, trimmed)

def _project_root(course) -> str:
    return os.path.dirname(os.path.abspath(course.configfile))

def _resolve_course_path(course, path_value: str) -> str:
    if os.path.isabs(path_value):
        return os.path.normpath(path_value)
    return os.path.normpath(os.path.join(_project_root(course), path_value))

def _ensure_itreedir_root(course) -> Optional[str]:
    """Ensure the instructor tree root is a directory."""
    itreedir = getattr(course, 'itreedir', None)
    if not itreedir:
        return None
    configured_path = _resolve_course_path(course, itreedir)
    if os.path.isdir(configured_path):
        return configured_path
    return None

def _resolve_include_style_path(filespec: str, source_file: str, course) -> str:
    """Resolve filespecs that follow INCLUDE semantics."""
    filespec = _normalize_filespec_value(filespec)
    keyword_re = f"{c.AUTHOR_ALTDIR_PREFIX}|{c.AUTHOR_ITREEDIR_PREFIX}"
    arg_re = r"(?P<kw>" + keyword_re + r")?(?P<slash>/)?(?P<incfile>.*)"
    match = re.fullmatch(arg_re, filespec)
    if not match:
        raise ValueError(f"Invalid snippet path '{filespec}'")
    kw = match.group("kw")
    is_abs = match.group("slash") is not None
    inc_filepath = match.group("incfile")
    project_root = _project_root(course)
    chapter_root = os.path.normpath(os.path.join(project_root, course.chapterdir))
    altdir_root = os.path.normpath(os.path.join(project_root, course.altdir))
    itreedir_root = _ensure_itreedir_root(course)
    source_abs = source_file if os.path.isabs(source_file) else os.path.normpath(
        os.path.join(project_root, source_file)
    )
    source_dir = os.path.dirname(source_abs)
    source_basename = os.path.basename(source_abs)
    rel_dir_from_chapter = os.path.relpath(source_dir, chapter_root)
    if kw == c.AUTHOR_ALTDIR_PREFIX:
        base_root = altdir_root
        rel_dir = rel_dir_from_chapter
        target_dir = os.path.normpath(os.path.join(base_root, rel_dir))
    elif kw == c.AUTHOR_ITREEDIR_PREFIX:
        if not itreedir_root:
            raise ValueError("Snippet path prefix 'ITREE:' cannot be resolved")
        base_root = itreedir_root
        rel_dir = rel_dir_from_chapter
        if is_abs or (inc_filepath and inc_filepath.startswith(os.path.join(rel_dir, ""))):
            target_dir = base_root
        else:
            target_dir = os.path.normpath(os.path.join(base_root, rel_dir))
    else:
        base_root = chapter_root
        target_dir = source_dir
    if is_abs:
        target_dir = base_root
    fullpath = os.path.join(target_dir, inc_filepath or source_basename)
    return os.path.normpath(fullpath)


def _display_snippet_path(filespec: str | None, fullpath: str, course) -> str:
    """Return a human-friendly path for diagnostics."""
    if filespec:
        return filespec
    project_root = os.path.dirname(os.path.abspath(course.configfile))
    try:
        return os.path.relpath(fullpath, project_root)
    except ValueError:
        return fullpath


def _load_snippet(
    snippet_id: str,
    filespec: str | None,
    source_file: str,
    course,
    notify_error: Callable[[str], None]
) -> tuple[Optional[CodeSnippet], Optional[str]]:
    """Resolve and load a snippet, reporting errors via notify_error."""
    try:
        fullpath = _resolve_include_style_path(filespec or "", source_file, course)
    except ValueError as exc:
        notify_error(str(exc))
        return None, None
    if not os.path.exists(fullpath):
        notify_error(f"File not found: {_display_snippet_path(filespec, fullpath, course)}")
        return None, None
    extractor = SnippetExtractor()
    snippets = extractor.extract_snippets_from_file(fullpath)
    for snippet in snippets:
        if snippet.snippet_id == snippet_id:
            return snippet, fullpath
    available_ids = [s.snippet_id for s in snippets]
    notify_error(
        f"Snippet '{snippet_id}' not found in "
        f"'{_display_snippet_path(filespec, fullpath, course)}'. "
        f"Available snippets: {available_ids}"
    )
    return None, None


def _format_snippet_for_macro(snippet: CodeSnippet) -> str:
    """Return snippet content exactly as defined in the source file, preserving trailing newline."""
    content = snippet.content or ""
    if content and not content.endswith('\n'):
        content += '\n'
    return content


class SnippetValidator:
    """Validates snippet references and definitions."""
    
    def validate_file_references(self, filepath: str, course) -> list[SnippetValidationResult]:
        """
        Validate all snippet references in a file."""
        extractor = SnippetReferenceExtractor()
        references = extractor.extract_references_from_file(filepath)
        results = []
        for ref in references:
            result = self._validate_single_reference(ref, course)
            results.append(result)
        return results
    
    def _validate_single_reference(self, reference: SnippetReference, course) -> SnippetValidationResult:
        """Validate a single snippet reference."""
        errors: list[str] = []
        snippet, _ = _load_snippet(
            reference.snippet_id,
            reference.filespec,
            reference.source_file,
            course,
            notify_error=errors.append
        )
        if snippet is None:
            return SnippetValidationResult(
                reference=reference,
                success=False,
                error_message=errors[0] if errors else "Unknown snippet error"
            )
        return SnippetValidationResult(
            reference=reference,
            success=True,
            snippet=snippet
        )
    
    def _validate_snippet_markers_in_file(self, filepath: str) -> list[str]:
        """Validate snippet markers in a single file."""
        if not os.path.exists(filepath):
            return [f"File not found: {filepath}"]
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except (OSError, UnicodeDecodeError):
            return [f"Cannot read file: {filepath}"]
        extractor = SnippetExtractor()
        _, errors = extractor.extract_snippets_from_content(content, filepath, collect_errors=True)
        return errors


def expand_snippet_macro(course, macrocall) -> str:
    """Macro expander for [SNIPPET::filespec::snippet_id]."""
    filespec = (macrocall.arg1 or "").strip()
    snippet_id = (macrocall.arg2 or "").strip()
    if not snippet_id:
        macrocall.error("Snippet name must not be empty")
        return ""
    if not IDENTIFIER_RE.fullmatch(snippet_id):
        macrocall.error("Snippet name must use letters, digits, or underscores only")
        return ""
    snippet, fullpath = _load_snippet(
        snippet_id,
        filespec,
        macrocall.filename,
        course,
        notify_error=macrocall.error
    )
    if snippet is None:
        return ""
    if hasattr(macrocall.md, "includefiles"):
        macrocall.md.includefiles.add(os.path.normpath(fullpath))
    return _format_snippet_for_macro(snippet)

    