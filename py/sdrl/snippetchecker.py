"""
Snippet extraction and inclusion functionality for sedrila.
Allows extracting code snippets from solution files and including them in task files.
"""
import dataclasses
import os
import re
import sys
from pathlib import Path
from typing import Optional


def _ensure_sedrila_path():
    """
    Automatically detect and add sedrila/py path to sys.path if needed.
    This ensures snippet functionality works with both pipx global installs and virtual environments.
    """
    # Skip if we're already in a working environment
    try:
        import base as b
        return  # If base imports successfully, we're good
    except ImportError:
        pass  # Need to find and add sedrila path
    
    # Try to find sedrila/py path using multiple detection methods  
    current_file = os.path.abspath(__file__)
    sedrila_py_candidates = []
    
    # Method 1: Current file is in sedrila/py/sdrl/snippetchecker.py
    # So sedrila/py should be two levels up
    py_path = os.path.dirname(os.path.dirname(current_file))
    if os.path.basename(py_path) == 'py':
        sedrila_py_candidates.append(py_path)
    
    # Method 2: Look for sedrila installation in common locations
    # This handles the case where sedrila is installed via pipx or pip
    home_dir = os.path.expanduser("~")
    possible_locations = [
        # Common development location
        os.path.join(home_dir, "MA", "sedrila", "py"),
        # Look in the same directory structure as current file
        os.path.join(os.path.dirname(current_file), "..", "..", ".."),
    ]
    
    for location in possible_locations:
        abs_location = os.path.abspath(location)
        if os.path.exists(os.path.join(abs_location, "base.py")):
            sedrila_py_candidates.append(abs_location)
    
    # Method 3: Search in sys.path for an existing sedrila installation
    for path in sys.path:
        if os.path.exists(os.path.join(path, "base.py")):
            sedrila_py_candidates.append(path)
    
    # Try each candidate path
    for candidate in sedrila_py_candidates:
        if os.path.exists(os.path.join(candidate, "base.py")):
            normalized_path = os.path.abspath(candidate)
            if normalized_path not in sys.path:
                sys.path.insert(0, normalized_path)
            try:
                import base as b
                return  # Success!
            except ImportError:
                continue
    
    # If we get here, we couldn't find base.py anywhere
    raise ImportError(
        "Cannot find sedrila base module. Please ensure sedrila is properly installed "
        "or set PYTHONPATH to include the sedrila/py directory."
    )


# Ensure sedrila path is available before importing base
_ensure_sedrila_path()
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
    referenced_file: str
    line_number: int


@dataclasses.dataclass 
class SnippetValidationResult:
    """Result of validating a snippet reference."""
    reference: SnippetReference
    success: bool
    snippet: Optional[CodeSnippet] = None
    error_message: Optional[str] = None


@dataclasses.dataclass
class ValidationStatistics:
    """Statistics for snippet validation."""
    total_references: int
    successful_references: int
    failed_references: int
    success_rate: float
    unique_snippets_found: int


class SnippetReferenceExtractor:
    """Extracts snippet references from task files."""
    
    def extract_references_from_content(self, content: str, filename: str) -> list[SnippetReference]:
        """Extract all @INCLUDE_SNIPPET references from content."""
        references = []
        pattern = re.compile(
            r'^@INCLUDE_SNIPPET:\s*(?P<id>\w+)\s+from\s+(?P<file>.+?)\s*$',
            re.MULTILINE
        )
        
        for line_num, line in enumerate(content.split('\n'), 1):
            match = pattern.search(line)
            if match:
                references.append(SnippetReference(
                    snippet_id=match.group('id'),
                    source_file=filename,
                    referenced_file=match.group('file').strip(),
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


class SnippetValidator:
    """Validates snippet references and definitions."""
    
    def validate_file_references(self, filepath: str, base_directory: str) -> list[SnippetValidationResult]:
        """Validate all snippet references in a file."""
        extractor = SnippetReferenceExtractor()
        references = extractor.extract_references_from_file(filepath)
        
        results = []
        for ref in references:
            result = self._validate_single_reference(ref, base_directory)
            results.append(result)
        
        return results
    
    def _validate_single_reference(self, reference: SnippetReference, base_directory: str) -> SnippetValidationResult:
        """Validate a single snippet reference."""
        # Resolve the file path
        # base_directory should be the directory containing the task file
        # For altdir/ paths, we need to go up to the project root
        
        if reference.referenced_file.startswith('altdir/'):
            # Path is relative to project root
            # base_directory is typically /path/to/project/ch/Web/Django
            # We need to find the project root (the directory containing both ch/ and altdir/)
            
            # Go up from base_directory until we find a directory that contains 'altdir'
            project_root = base_directory
            while project_root and project_root != '/':
                if os.path.exists(os.path.join(project_root, 'altdir')):
                    break
                project_root = os.path.dirname(project_root)
            
            if not project_root or project_root == '/':
                # Fallback: assume base_directory is under ch/, go up to parent
                if '/ch/' in base_directory:
                    project_root = base_directory.split('/ch/')[0]
                else:
                    project_root = base_directory
            
            fullpath = os.path.join(project_root, reference.referenced_file)
        elif os.path.isabs(reference.referenced_file):
            # Absolute path
            fullpath = reference.referenced_file  
        else:
            # Relative to the source file's directory
            source_dir = os.path.dirname(reference.source_file)
            fullpath = os.path.join(source_dir, reference.referenced_file)
        
        fullpath = os.path.normpath(fullpath)
        
        # Check if file exists
        if not os.path.exists(fullpath):
            return SnippetValidationResult(
                reference=reference,
                success=False,
                error_message=f"File not found: {reference.referenced_file}"
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
        
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.endswith(('.md', '.py', '.js', '.ts', '.java', '.cpp', '.c')):
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


class SnippetReporter:
    """Generates reports for snippet validation results."""
    
    def print_summary(self, results: list[SnippetValidationResult], file_errors: dict[str, list[str]] = None):
        """Print a summary of validation results."""
        if file_errors is None:
            file_errors = {}
        
        # Print snippet definition errors first
        if file_errors:
            b.error("Snippet definition errors found:")
            for filepath, errors in file_errors.items():
                b.error(f"  {filepath}:")
                for error in errors:
                    b.error(f"    - {error}")
        
        if not results:
            if not file_errors:
                b.info("No snippet references found")
            return
        
        total = len(results)
        successful = sum(1 for r in results if r.success)
        failed = total - successful
        
        b.info(f"Snippet validation summary:")
        b.info(f"  Total references: {total}")
        b.info(f"  Successful: {successful}")
        b.info(f"  Failed: {failed}")
        
        if failed > 0:
            b.info("Failed references:")
            for result in results:
                if not result.success:
                    b.error(f"  {result.reference.source_file}:{result.reference.line_number} - {result.error_message}")
        else:
            b.info("All snippet references are valid!")
    
    def generate_statistics(self, validation_results: list[SnippetValidationResult], 
                          file_errors: dict[str, list[str]]) -> ValidationStatistics:
        """Generate statistics from validation results."""
        total = len(validation_results)
        successful = sum(1 for r in validation_results if r.success)
        failed = total - successful
        success_rate = (successful / total * 100) if total > 0 else 0.0
        
        unique_snippets = set()
        for result in validation_results:
            if result.success and result.snippet:
                unique_snippets.add(result.snippet.snippet_id)
        
        return ValidationStatistics(
            total_references=total,
            successful_references=successful,
            failed_references=failed,
            success_rate=success_rate,
            unique_snippets_found=len(unique_snippets)
        )
    
    def generate_json_report(self, validation_results: list[SnippetValidationResult], 
                           file_errors: dict[str, list[str]] = None, 
                           output_file: str = "snippet_validation_report.json"):
        """Generate a JSON report."""
        import json
        
        report_data = {
            "validation_results": [],
            "file_errors": file_errors or {},
            "statistics": {}
        }
        
        for result in validation_results:
            result_data = {
                "reference": {
                    "snippet_id": result.reference.snippet_id,
                    "source_file": result.reference.source_file,
                    "referenced_file": result.reference.referenced_file,
                    "line_number": result.reference.line_number
                },
                "success": result.success,
                "error_message": result.error_message
            }
            
            if result.snippet:
                result_data["snippet"] = {
                    "snippet_id": result.snippet.snippet_id,
                    "source_file": result.snippet.source_file,
                    "start_line": result.snippet.start_line,
                    "end_line": result.snippet.end_line,
                    "language": result.snippet.language
                }
            
            report_data["validation_results"].append(result_data)
        
        stats = self.generate_statistics(validation_results, file_errors or {})
        report_data["statistics"] = {
            "total_references": stats.total_references,
            "successful_references": stats.successful_references,
            "failed_references": stats.failed_references,
            "success_rate": stats.success_rate,
            "unique_snippets_found": stats.unique_snippets_found
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2)
        
        b.info(f"JSON report generated: {output_file}")
    
    def generate_markdown_report(self, validation_results: list[SnippetValidationResult], 
                               file_errors: dict[str, list[str]] = None, 
                               output_file: str = "snippet_validation_report.md"):
        """Generate a Markdown report."""
        lines = ["# Snippet Validation Report", ""]
        
        # Statistics
        stats = self.generate_statistics(validation_results, file_errors or {})
        lines.extend([
            "## Summary", "",
            f"- **Total references**: {stats.total_references}",
            f"- **Successful**: {stats.successful_references}",
            f"- **Failed**: {stats.failed_references}", 
            f"- **Success rate**: {stats.success_rate:.1f}%",
            f"- **Unique snippets found**: {stats.unique_snippets_found}", ""
        ])
        
        # Validation results
        if validation_results:
            lines.extend(["## Validation Results", ""])
            for result in validation_results:
                status = "PASS" if result.success else "FAIL"
                lines.append(f"### {status} {result.reference.snippet_id}")
                lines.append(f"- **Source**: `{result.reference.source_file}:{result.reference.line_number}`")
                lines.append(f"- **Reference**: `{result.reference.referenced_file}`")
                
                if result.success and result.snippet:
                    lines.append(f"- **Found at**: `{result.snippet.source_file}:{result.snippet.start_line}-{result.snippet.end_line}`")
                    if result.snippet.language:
                        lines.append(f"- **Language**: `{result.snippet.language}`")
                else:
                    lines.append(f"- **Error**: {result.error_message}")
                
                lines.append("")
        
        # File errors
        if file_errors:
            lines.extend(["## File Errors", ""])
            for filepath, errors in file_errors.items():
                lines.append(f"### {filepath}")
                for error in errors:
                    lines.append(f"- {error}")
                lines.append("")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        b.info(f"Markdown report generated: {output_file}")


def expand_snippet_inclusion(content: str, context_file: str, basedir: str) -> str:
    """
    Expand @INCLUDE_SNIPPET directives in content.
    
    Format: @INCLUDE_SNIPPET: snippet_id from path/to/file.md
    
    The path resolution works as follows:
    - If path starts with 'altdir/', it's resolved relative to the project root (basedir)
    - Otherwise, it's resolved relative to the context file's directory
    """
    # Debug output
    b.debug(f"expand_snippet_inclusion called for {context_file}, basedir={basedir}")
    
    # Pattern: @INCLUDE_SNIPPET: snippet_id from filepath
    pattern = re.compile(
        r'^@INCLUDE_SNIPPET:\s*(?P<id>\w+)\s+from\s+(?P<file>.+?)\s*$',
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
        snippet_file = match.group('file').strip()
        
        b.debug(f"Processing snippet inclusion: id='{snippet_id}', file='{snippet_file}'")
        
        # Resolve the file path
        # The basedir should be the project root (e.g., /home/navi/MA/propra-inf)
        # context_file might be something like: propra-inf/ch/Web/Django/django-project.md
        # or an absolute path like: /home/navi/MA/propra-inf/ch/Web/Django/django-project.md
        
        if snippet_file.startswith('altdir/'):
            # Path is relative to project root
            fullpath = os.path.join(basedir, snippet_file)
            b.debug(f"Using altdir path: basedir='{basedir}' + snippet_file='{snippet_file}' -> '{fullpath}'")
        elif os.path.isabs(snippet_file):
            # Absolute path
            fullpath = snippet_file
            b.debug(f"Using absolute path: '{fullpath}'")
        else:
            # Relative to the context file's directory
            context_dir = os.path.dirname(context_file)
            fullpath = os.path.join(context_dir, snippet_file)
            b.debug(f"Using relative path: context_dir='{context_dir}' + snippet_file='{snippet_file}' -> '{fullpath}'")
        
        # Normalize the path
        fullpath = os.path.normpath(fullpath)
        b.debug(f"Normalized path: '{fullpath}'")
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
