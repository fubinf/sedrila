"""
Snippet extraction and inclusion functionality for sedrila.
Allows extracting code snippets from solution files and including them in task files.
"""
import dataclasses
import os
import re
from typing import Optional

import base as b


@dataclasses.dataclass
class CodeSnippet:
    """Represents an extracted code snippet."""
    snippet_id: str
    content: str
    source_file: str
    start_line: int
    end_line: int
    language: Optional[str] = None


class SnippetExtractor:
    """Extracts code snippets from files."""
    
    # Pattern for HTML comment style: <!-- @SNIPPET_START: snippet_id lang=python -->
    SNIPPET_START_RE = re.compile(
        r'<!--\s*@SNIPPET_START:\s*(?P<id>\w+)(?:\s+lang=(?P<lang>\w+))?\s*-->'
    )
    SNIPPET_END_RE = re.compile(
        r'<!--\s*@SNIPPET_END:\s*(?P<id>\w+)\s*-->'
    )
    
    def extract_snippets_from_content(self, content: str, filename: str, collect_errors: bool = False) -> tuple[list[CodeSnippet], list[str]]:
        """
        Extract all snippets from file content.
        
        Args:
            content: The file content
            filename: The filename (for error messages)
            collect_errors: If True, collect errors instead of just warning
            
        Returns:
            Tuple of (snippets, errors) where errors is empty if collect_errors=False
        """
        snippets = []
        errors = []
        lines = content.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i]
            start_match = self.SNIPPET_START_RE.search(line)
            
            if start_match:
                snippet_id = start_match.group('id')
                language = start_match.group('lang')
                start_line = i + 1
                
                # Find the corresponding end marker
                snippet_lines = []
                i += 1
                found_end = False
                
                while i < len(lines):
                    line = lines[i]
                    end_match = self.SNIPPET_END_RE.search(line)
                    
                    if end_match:
                        end_id = end_match.group('id')
                        if end_id == snippet_id:
                            found_end = True
                            end_line = i
                            snippet_content = '\n'.join(snippet_lines)
                            snippets.append(CodeSnippet(
                                snippet_id=snippet_id,
                                content=snippet_content,
                                source_file=filename,
                                start_line=start_line,
                                end_line=end_line,
                                language=language
                            ))
                            break
                        else:
                            error_msg = f"Mismatched snippet end marker: expected '{snippet_id}', got '{end_id}' at line {i+1}"
                            if collect_errors:
                                errors.append(error_msg)
                            else:
                                b.warning(error_msg, file=filename)
                    else:
                        snippet_lines.append(line)
                    
                    i += 1
                
                if not found_end:
                    error_msg = f"Unclosed snippet '{snippet_id}' starting at line {start_line}"
                    if collect_errors:
                        errors.append(error_msg)
                    else:
                        b.warning(error_msg, file=filename)
            
            i += 1
        
        return snippets, errors
    
    def extract_snippets_from_file(self, filepath: str) -> list[CodeSnippet]:
        """Extract all snippets from a file."""
        if not os.path.exists(filepath):
            b.warning(f"File not found: {filepath}")
            return []
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        snippets, _ = self.extract_snippets_from_content(content, filepath, collect_errors=False)
        return snippets


def find_snippet_in_file(snippet_id: str, filepath: str) -> Optional[CodeSnippet]:
    """Find a specific snippet in a file."""
    extractor = SnippetExtractor()
    snippets = extractor.extract_snippets_from_file(filepath)
    
    for snippet in snippets:
        if snippet.snippet_id == snippet_id:
            return snippet
    
    return None


@dataclasses.dataclass
class SnippetReference:
    """Represents a reference to a code snippet."""
    snippet_id: str
    source_file: str
    referenced_file: str | None
    line_number: int


@dataclasses.dataclass
class SnippetValidationResult:
    """Result of validating a snippet reference."""
    reference: SnippetReference
    success: bool
    snippet: Optional[CodeSnippet] = None
    error_message: Optional[str] = None


class SnippetReferenceExtractor:
    """Extracts snippet references from task files."""
    
    def extract_references_from_content(self, content: str, filename: str) -> list[SnippetReference]:
        """Extract all @INCLUDE_SNIPPET references from content."""
        references = []
        pattern = re.compile(
            r'^@INCLUDE_SNIPPET:\s*(?P<id>\w+)(?:\s+from\s+(?P<file>.+?))?\s*$',
            re.MULTILINE
        )
        
        for line_num, line in enumerate(content.split('\n'), 1):
            match = pattern.search(line)
            if match:
                references.append(SnippetReference(
                    snippet_id=match.group('id'),
                    source_file=filename,
                    referenced_file=match.group('file').strip() if match.group('file') else None,
                    line_number=line_num
                ))
        
        return references
    
    def extract_references_from_file(self, filepath: str) -> list[SnippetReference]:
        """Extract all snippet references from a file."""
        if not os.path.exists(filepath):
            return []
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return self.extract_references_from_content(content, filepath)


def _resolve_snippet_path(referenced_file: str | None, source_file: str, course) -> str:
    """
    Resolve a snippet file path using course configuration.
    
    Two path styles are supported:
    1. altdir/ prefix: resolved relative to the project root (e.g., altdir/solutions/file.py)
    2. Omitted path: derive the matching file inside altdir by exchanging the chapterdir prefix
    
    Args:
        referenced_file: The file path from @INCLUDE_SNIPPET directive
        source_file: The task file containing the reference
        course: Coursebuilder object with chapterdir, altdir, and configfile attributes
    
    Returns:
        Resolved absolute path to the snippet file
    """
    project_root = os.path.dirname(os.path.abspath(course.configfile))
    
    if referenced_file:
        altdir_prefix = f"{course.altdir}/"
        if referenced_file.startswith(altdir_prefix):
            fullpath = os.path.join(project_root, referenced_file)
        else:
            raise ValueError(
                f"Unsupported snippet path '{referenced_file}'. "
                "Use an 'altdir/' path or omit the path to use the matching altdir file."
            )
    else:
        fullpath = _derive_altdir_path(source_file, course, project_root)
    
    return os.path.normpath(fullpath)


def _derive_altdir_path(source_file: str, course, project_root: str) -> str:
    """Derive the matching file in altdir by exchanging the chapterdir prefix."""
    if os.path.isabs(source_file):
        rel_path = os.path.relpath(source_file, project_root)
    else:
        rel_path = os.path.normpath(source_file)
    
    # Already inside altdir
    if rel_path.startswith(f"{course.altdir}/"):
        return os.path.join(project_root, rel_path)
    
    chapter_prefix = course.chapterdir.rstrip('/')
    if chapter_prefix:
        prefix = f"{chapter_prefix}/"
        if rel_path.startswith(prefix):
            rel_rest = rel_path[len(prefix):]
        else:
            rel_rest = rel_path
    else:
        rel_rest = rel_path.lstrip("/\\")
    
    altdir_rel = os.path.join(course.altdir, rel_rest)
    return os.path.join(project_root, altdir_rel)


class SnippetValidator:
    """Validates snippet references and definitions."""
    
    def validate_file_references(self, filepath: str, course) -> list[SnippetValidationResult]:
        """
        Validate all snippet references in a file.
        
        Args:
            filepath: Path to the task file containing snippet references
            course: Coursebuilder object with chapterdir, altdir, and configfile attributes
        """
        extractor = SnippetReferenceExtractor()
        references = extractor.extract_references_from_file(filepath)
        
        results = []
        for ref in references:
            result = self._validate_single_reference(ref, course)
            results.append(result)
        
        return results
    
    def _validate_single_reference(self, reference: SnippetReference, course) -> SnippetValidationResult:
        """Validate a single snippet reference."""
        # Resolve the file path using course configuration
        try:
            fullpath = _resolve_snippet_path(
                reference.referenced_file,
                reference.source_file,
                course
            )
        except ValueError as exc:
            return SnippetValidationResult(
                reference=reference,
                success=False,
                error_message=str(exc)
            )
        
        # Check if file exists
        if not os.path.exists(fullpath):
            project_root = os.path.dirname(os.path.abspath(course.configfile))
            display_path = reference.referenced_file or os.path.relpath(fullpath, project_root)
            return SnippetValidationResult(
                reference=reference,
                success=False,
                error_message=f"File not found: {display_path}"
            )
        
        # Find the snippet
        snippet = find_snippet_in_file(reference.snippet_id, fullpath)
        
        if snippet is None:
            # Get available snippets for error message
            extractor = SnippetExtractor()
            available = extractor.extract_snippets_from_file(fullpath)
            available_ids = [s.snippet_id for s in available]
            
            return SnippetValidationResult(
                reference=reference,
                success=False,
                error_message=f"Snippet '{reference.snippet_id}' not found in '{reference.referenced_file}'. Available snippets: {available_ids}"
            )
        
        return SnippetValidationResult(
            reference=reference,
            success=True,
            snippet=snippet
        )
    
    def validate_directory_snippets(self, directory: str) -> dict[str, list[str]]:
        """Validate snippet markers in all files in a directory."""
        file_errors = {}
        
        # Exclude binary files and system files (use exclusion approach, not inclusion)
        excluded_extensions = {'.zip', '.tar', '.gz', '.bz2', '.xz', '.7z',
                              '.exe', '.bin', '.so', '.dll', '.dylib',
                              '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico', '.svg',
                              '.pdf', '.doc', '.docx', '.xls', '.xlsx',
                              '.pyc', '.pyo', '.o', '.a', '.class',
                              '.db', '.sqlite', '.sqlite3'}
        excluded_names = {'.git', '.svn', '.hg', '__pycache__', 
                         '.DS_Store', 'Thumbs.db'}
        
        for root, dirs, files in os.walk(directory):
            # Skip system and cache directories
            dirs[:] = [d for d in dirs if d not in excluded_names]
            
            for file in files:
                # Skip binary files, hidden files, and excluded files
                if file.startswith('.'):
                    continue
                if file in excluded_names:
                    continue
                if any(file.endswith(ext) for ext in excluded_extensions):
                    continue
                
                filepath = os.path.join(root, file)
                errors = self._validate_snippet_markers_in_file(filepath)
                if errors:
                    file_errors[filepath] = errors
        
        return file_errors
    
    def _validate_snippet_markers_in_file(self, filepath: str) -> list[str]:
        """Validate snippet markers in a single file."""
        try:
            extractor = SnippetExtractor()
            
            if not os.path.exists(filepath):
                return [f"File not found: {filepath}"]
            
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Use collect_errors=True to get validation errors
            _, errors = extractor.extract_snippets_from_content(content, filepath, collect_errors=True)
            return errors
            
        except Exception as e:
            return [f"Error parsing snippets: {str(e)}"]


def expand_snippet_inclusion(content: str, context_file: str, course) -> str:
    """
    Expand @INCLUDE_SNIPPET directives in content.
    
    Format:
      @INCLUDE_SNIPPET: snippet_id
      @INCLUDE_SNIPPET: snippet_id from altdir/path/to/file.md
    
    When no path is given, the snippet file is derived by exchanging the course's
    chapterdir prefix with altdir.
    
    Args:
        content: The content containing @INCLUDE_SNIPPET directives
        context_file: The file containing the directive
        course: Coursebuilder object with chapterdir, altdir, and configfile attributes
    """
    # Debug output
    project_root = os.path.dirname(os.path.abspath(course.configfile))
    b.debug(f"expand_snippet_inclusion called for {context_file}, project_root={project_root}")
    
    # Pattern: @INCLUDE_SNIPPET: snippet_id [from filepath]
    pattern = re.compile(
        r'^@INCLUDE_SNIPPET:\s*(?P<id>\w+)(?:\s+from\s+(?P<file>.+?))?\s*$',
        re.MULTILINE
    )
    
    # Check if pattern matches anything
    matches = list(pattern.finditer(content))
    if matches:
        b.debug(f"Found {len(matches)} snippet inclusions")
        for i, match in enumerate(matches):
            b.debug(f"  Match {i+1}: id='{match.group('id')}', file='{match.group('file')}'")
    else:
        b.debug("No @INCLUDE_SNIPPET patterns found in content")
        # Show the first few lines of content for debugging
        lines = content.split('\n')[:10]
        b.debug(f"Content preview (first 10 lines):")
        for i, line in enumerate(lines, 1):
            b.debug(f"  {i:2}: {line}")
    
    def replace_snippet(match: re.Match) -> str:
        snippet_id = match.group('id')
        snippet_file = match.group('file')
        if snippet_file:
            snippet_file = snippet_file.strip()
        
        b.debug(f"Processing snippet inclusion: id='{snippet_id}', file='{snippet_file}'")
        
        # Use _resolve_snippet_path for consistent path resolution
        try:
            fullpath = _resolve_snippet_path(snippet_file, context_file, course)
        except ValueError as exc:
            b.warning(str(exc), file=context_file)
            return f"<!-- ERROR: {exc} -->"
        b.debug(f"Resolved path: '{fullpath}'")
        b.debug(f"File exists: {os.path.exists(fullpath)}")
        
        # Extract the snippet
        snippet = find_snippet_in_file(snippet_id, fullpath)
        
        if snippet is None:
            # Check what snippets are available
            extractor = SnippetExtractor()
            available = extractor.extract_snippets_from_file(fullpath)
            available_ids = [s.snippet_id for s in available]
            
            b.warning(
                f"Snippet '{snippet_id}' not found in '{fullpath}'. "
                f"Available snippets: {available_ids}",
                file=context_file
            )
            return f"<!-- ERROR: Snippet '{snippet_id}' not found in '{snippet_file}' -->"
        
        # Return the snippet content (which should already be in markdown code block format)
        b.debug(f"Returning snippet content: {repr(snippet.content[:100])}")
        return snippet.content
    
    result = pattern.sub(replace_snippet, content)
    
    # Debug: show the result around where @INCLUDE_SNIPPET was
    if result != content:
        b.debug("Content changed after snippet expansion")
        # Find where the change occurred by comparing line by line
        orig_lines = content.split('\n')
        result_lines = result.split('\n')
        for i, (orig, new) in enumerate(zip(orig_lines, result_lines)):
            if orig != new and '@INCLUDE_SNIPPET' in orig:
                b.debug(f"Line {i+1} changed from: {repr(orig)}")
                b.debug(f"                    to: {repr(new[:100])}")
    else:
        b.debug("No change detected after snippet expansion")
    
    return result
