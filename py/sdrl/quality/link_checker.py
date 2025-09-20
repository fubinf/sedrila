"""
External link checker for SeDriLa courses.

This module provides functionality to extract and validate external links
from markdown files in SeDriLa tasks.
"""
import json
import re
import time
import typing as tg
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime
from urllib.parse import urlparse

import requests

import base as b


@dataclass
class LinkValidationRule:
    """Custom validation rule for a specific link."""
    expected_status: tg.Optional[int] = None
    required_text: tg.Optional[str] = None
    ignore_ssl: bool = False
    timeout: tg.Optional[int] = None


@dataclass
class ExternalLink:
    """Represents an external link found in a markdown file."""
    url: str
    text: str
    source_file: str
    line_number: int
    link_type: str  # 'markdown' or 'href_macro'
    validation_rule: tg.Optional[LinkValidationRule] = None
    
    def __str__(self) -> str:
        return f"{self.url} ({self.link_type}) in {self.source_file}:{self.line_number}"


@dataclass
class LinkCheckResult:
    """Result of checking an external link."""
    link: ExternalLink
    success: bool
    status_code: tg.Optional[int] = None
    error_message: tg.Optional[str] = None
    response_time: tg.Optional[float] = None
    redirect_url: tg.Optional[str] = None


class LinkExtractor:
    """Extracts external links from markdown content."""
    
    # Regex patterns for different link formats
    MARKDOWN_LINK_PATTERN = r'\[([^\]]*)\]\(([^)]+)\)'
    HREF_MACRO_PATTERN = r'\[HREF::([^\]]+)\]'
    LINK_CHECK_COMMENT_PATTERN = r'<!--\s*LINK_CHECK:\s*([^-]+)\s*-->'
    
    def __init__(self):
        self.markdown_regex = re.compile(self.MARKDOWN_LINK_PATTERN)
        self.href_macro_regex = re.compile(self.HREF_MACRO_PATTERN)
        self.link_check_regex = re.compile(self.LINK_CHECK_COMMENT_PATTERN)
    
    def extract_links_from_file(self, filepath: str) -> list[ExternalLink]:
        """Extract all external links from a markdown file."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            b.error(f"Cannot read file {filepath}: {e}")
            return []
        
        links = []
        lines = content.split('\n')
        
        current_validation_rule = None
        
        for line_num, line in enumerate(lines, 1):
            # Check for LINK_CHECK comments
            link_check_match = self.link_check_regex.search(line)
            if link_check_match:
                current_validation_rule = self._parse_validation_rule(link_check_match.group(1))
                continue
            
            # Extract standard markdown links: [text](url)
            for match in self.markdown_regex.finditer(line):
                text, url = match.groups()
                if self._is_external_url(url):
                    links.append(ExternalLink(url, text, filepath, line_num, 'markdown', current_validation_rule))
                    current_validation_rule = None  # Rule applies to next link only
            
            # Extract HREF macro links: [HREF::url]
            for match in self.href_macro_regex.finditer(line):
                url = match.group(1)
                if self._is_external_url(url):
                    links.append(ExternalLink(url, url, filepath, line_num, 'href_macro', current_validation_rule))
                    current_validation_rule = None  # Rule applies to next link only
        
        return links
    
    def _is_external_url(self, url: str) -> bool:
        """Check if URL is external (http/https)."""
        parsed = urlparse(url)
        return parsed.scheme in ('http', 'https')
    
    def _parse_validation_rule(self, rule_text: str) -> LinkValidationRule:
        """Parse validation rule from LINK_CHECK comment."""
        rule = LinkValidationRule()
        
        # Parse key=value pairs
        for part in rule_text.split(','):
            part = part.strip()
            if '=' in part:
                key, value = part.split('=', 1)
                key = key.strip().lower()
                value = value.strip().strip('"\'')
                
                if key == 'status':
                    try:
                        rule.expected_status = int(value)
                    except ValueError:
                        b.warning(f"Invalid status code in LINK_CHECK: {value}")
                elif key == 'content' or key == 'text':
                    rule.required_text = value
                elif key == 'ignore_ssl':
                    rule.ignore_ssl = value.lower() in ('true', '1', 'yes')
                elif key == 'timeout':
                    try:
                        rule.timeout = int(value)
                    except ValueError:
                        b.warning(f"Invalid timeout in LINK_CHECK: {value}")
        
        return rule


class LinkChecker:
    """Validates external links by making HTTP requests."""
    
    def __init__(self, timeout: int = 10, max_retries: int = 2, delay_between_requests: float = 0.5):
        self.timeout = timeout
        self.max_retries = max_retries
        self.delay_between_requests = delay_between_requests
        self.session = requests.Session()
        
        # Set a reasonable User-Agent to avoid being blocked
        self.session.headers.update({
            'User-Agent': 'sedrila-link-checker/1.0 (Educational Content Validation; +https://github.com/fubinf/sedrila)'
        })
    
    def check_link(self, link: ExternalLink) -> LinkCheckResult:
        """Check accessibility of a single external link."""
        for attempt in range(self.max_retries + 1):
            try:
                start_time = time.time()
                # Use custom timeout and SSL settings if specified
                timeout = link.validation_rule.timeout if link.validation_rule and link.validation_rule.timeout else self.timeout
                verify_ssl = not (link.validation_rule and link.validation_rule.ignore_ssl)
                
                # If expecting a specific redirect status, don't follow redirects
                follow_redirects = True
                if link.validation_rule and link.validation_rule.expected_status:
                    if link.validation_rule.expected_status in [301, 302, 303, 307, 308]:
                        follow_redirects = False
                
                response = self.session.get(
                    link.url, 
                    timeout=timeout, 
                    allow_redirects=follow_redirects,
                    verify=verify_ssl
                )
                response_time = time.time() - start_time
                
                # Determine if we were redirected
                redirect_url = response.url if response.url != link.url else None
                
                # Check if status code matches expectation
                expected_status = link.validation_rule.expected_status if link.validation_rule else None
                if expected_status:
                    status_ok = response.status_code == expected_status
                    error_message = None if status_ok else f"Expected HTTP {expected_status}, got {response.status_code}"
                else:
                    # Default: consider 2xx and 3xx status codes as success
                    status_ok = 200 <= response.status_code < 400
                    error_message = None if status_ok else f"HTTP {response.status_code}"
                
                # Check content if required
                content_ok = True
                content_error = None
                if link.validation_rule and link.validation_rule.required_text:
                    try:
                        content = response.text
                        if link.validation_rule.required_text not in content:
                            content_ok = False
                            content_error = f"Required text '{link.validation_rule.required_text}' not found"
                    except Exception as e:
                        content_ok = False
                        content_error = f"Could not check content: {e}"
                
                # Combine results
                success = status_ok and content_ok
                if not success:
                    if error_message and content_error:
                        error_message = f"{error_message}; {content_error}"
                    elif content_error:
                        error_message = content_error
                
                return LinkCheckResult(
                    link=link,
                    success=success,
                    status_code=response.status_code,
                    error_message=error_message,
                    response_time=response_time,
                    redirect_url=redirect_url
                )
                
            except requests.exceptions.Timeout:
                if attempt == self.max_retries:
                    return LinkCheckResult(
                        link=link,
                        success=False,
                        error_message="Connection timeout"
                    )
                time.sleep(1 * (attempt + 1))  # Exponential backoff
                
            except requests.exceptions.ConnectionError as e:
                if attempt == self.max_retries:
                    return LinkCheckResult(
                        link=link,
                        success=False,
                        error_message=f"Connection error: {str(e)}"
                    )
                time.sleep(1 * (attempt + 1))
                
            except requests.exceptions.RequestException as e:
                return LinkCheckResult(
                    link=link,
                    success=False,
                    error_message=f"Request error: {str(e)}"
                )
        
        # This should never be reached, but just in case
        return LinkCheckResult(
            link=link,
            success=False,
            error_message="Unknown error after all retries"
        )
    
    def check_links(self, links: list[ExternalLink], show_progress: bool = True) -> list[LinkCheckResult]:
        """Check multiple links and return results."""
        if not links:
            return []
        
        results = []
        total_links = len(links)
        
        for i, link in enumerate(links):
            if show_progress:
                b.info(f"Checking link {i+1}/{total_links}: {link.url}")
            
            result = self.check_link(link)
            results.append(result)
            
            # Add delay between requests to be respectful to servers
            if i < total_links - 1:
                time.sleep(self.delay_between_requests)
        
        return results


@dataclass
class LinkStatistics:
    """Statistical summary of link checking results."""
    total_links: int = 0
    successful_links: int = 0
    failed_links: int = 0
    total_files: int = 0
    files_with_links: int = 0
    files_with_broken_links: int = 0
    domains: dict[str, int] = None
    status_codes: dict[int, int] = None
    error_types: dict[str, int] = None
    link_types: dict[str, int] = None
    
    def __post_init__(self):
        if self.domains is None:
            self.domains = {}
        if self.status_codes is None:
            self.status_codes = {}
        if self.error_types is None:
            self.error_types = {}
        if self.link_types is None:
            self.link_types = {}
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_links == 0:
            return 0.0
        return (self.successful_links / self.total_links) * 100


class LinkCheckReporter:
    """Generates reports for link checking results."""
    
    def __init__(self):
        self.report_timestamp = datetime.now()
    
    def generate_statistics(self, results: list[LinkCheckResult]) -> LinkStatistics:
        """Generate comprehensive statistics from link check results."""
        if not results:
            return LinkStatistics()
        
        stats = LinkStatistics()
        stats.total_links = len(results)
        
        file_set = set()
        files_with_links = set()
        files_with_broken_links = set()
        
        for result in results:
            link = result.link
            
            # Basic counts
            if result.success:
                stats.successful_links += 1
            else:
                stats.failed_links += 1
            
            # File tracking
            file_set.add(link.source_file)
            files_with_links.add(link.source_file)
            if not result.success:
                files_with_broken_links.add(link.source_file)
            
            # Domain analysis
            try:
                domain = urlparse(link.url).netloc.lower()
                stats.domains[domain] = stats.domains.get(domain, 0) + 1
            except:
                stats.domains['invalid'] = stats.domains.get('invalid', 0) + 1
            
            # Status code analysis
            if result.status_code:
                stats.status_codes[result.status_code] = stats.status_codes.get(result.status_code, 0) + 1
            
            # Error type analysis
            if not result.success and result.error_message:
                error_key = self._categorize_error(result.error_message)
                stats.error_types[error_key] = stats.error_types.get(error_key, 0) + 1
            
            # Link type analysis
            stats.link_types[link.link_type] = stats.link_types.get(link.link_type, 0) + 1
        
        stats.total_files = len(file_set)
        stats.files_with_links = len(files_with_links)
        stats.files_with_broken_links = len(files_with_broken_links)
        
        return stats
    
    def _categorize_error(self, error_message: str) -> str:
        """Categorize error messages for statistics."""
        error_lower = error_message.lower()
        if 'timeout' in error_lower or 'timed out' in error_lower:
            return 'timeout'
        elif '404' in error_lower or 'not found' in error_lower:
            return '404_not_found'
        elif '403' in error_lower or 'forbidden' in error_lower:
            return '403_forbidden'
        elif '500' in error_lower or 'server error' in error_lower:
            return '500_server_error'
        elif 'connection' in error_lower:
            return 'connection_error'
        elif 'ssl' in error_lower or 'certificate' in error_lower:
            return 'ssl_error'
        else:
            return 'other'
    
    def print_summary(self, results: list[LinkCheckResult]) -> None:
        """Print a summary of link checking results."""
        if not results:
            b.info("No external links found to check.")
            return
        
        stats = self.generate_statistics(results)
        
        b.info("=" * 60)
        b.info("EXTERNAL LINK CHECK REPORT")
        b.info("=" * 60)
        b.info(f"Timestamp: {self.report_timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        b.info("")
        
        # Basic statistics
        b.info("BASIC STATISTICS")
        b.info(f"  Total links checked: {stats.total_links}")
        b.info(f"  Successful: {stats.successful_links} ({stats.success_rate:.1f}%)")
        b.info(f"  Failed: {stats.failed_links} ({100-stats.success_rate:.1f}%)")
        b.info(f"  Files with links: {stats.files_with_links}")
        b.info(f"  Files with broken links: {stats.files_with_broken_links}")
        b.info("")
        
        # Link type distribution
        if stats.link_types:
            b.info("LINK TYPES")
            for link_type, count in sorted(stats.link_types.items()):
                percentage = (count / stats.total_links) * 100
                b.info(f"  {link_type}: {count} ({percentage:.1f}%)")
            b.info("")
        
        # Top domains
        if stats.domains:
            b.info("TOP DOMAINS")
            sorted_domains = sorted(stats.domains.items(), key=lambda x: x[1], reverse=True)
            for domain, count in sorted_domains[:10]:  # Top 10 domains
                percentage = (count / stats.total_links) * 100
                b.info(f"  {domain}: {count} links ({percentage:.1f}%)")
            b.info("")
        
        # Status codes
        if stats.status_codes:
            b.info("HTTP STATUS CODES")
            sorted_codes = sorted(stats.status_codes.items())
            for status_code, count in sorted_codes:
                percentage = (count / stats.total_links) * 100
                status_desc = self._get_status_description(status_code)
                b.info(f"  {status_code} ({status_desc}): {count} ({percentage:.1f}%)")
            b.info("")
        
        # Error analysis
        if stats.error_types:
            b.info("ERROR ANALYSIS")
            sorted_errors = sorted(stats.error_types.items(), key=lambda x: x[1], reverse=True)
            for error_type, count in sorted_errors:
                percentage = (count / stats.failed_links) * 100 if stats.failed_links > 0 else 0
                b.info(f"  {error_type.replace('_', ' ').title()}: {count} ({percentage:.1f}% of failures)")
            b.info("")
        
        # Failed links details
        failed_results = [r for r in results if not r.success]
        if failed_results:
            b.info("FAILED LINKS DETAILS")
            for result in failed_results:
                link = result.link
                b.error(f"  FAILED: {link.url}")
                b.error(f"     File: {link.source_file}:{link.line_number}")
                b.error(f"     Type: {link.link_type}")
                b.error(f"     Error: {result.error_message}")
                if result.status_code:
                    b.error(f"     Status: {result.status_code}")
            b.info("")
        
        # Final status
        b.info("=" * 60)
        if failed_results:
            b.error(f"VALIDATION FAILED: {len(failed_results)}/{stats.total_links} links are broken")
        else:
            b.info(f"VALIDATION PASSED: All {stats.total_links} links are accessible")
        b.info("=" * 60)
    
    def _get_status_description(self, status_code: int) -> str:
        """Get human-readable description for HTTP status codes."""
        descriptions = {
            200: "OK",
            301: "Moved Permanently",
            302: "Found",
            403: "Forbidden",
            404: "Not Found",
            500: "Internal Server Error",
            502: "Bad Gateway",
            503: "Service Unavailable",
            504: "Gateway Timeout"
        }
        return descriptions.get(status_code, "Unknown")
    
    def generate_json_report(self, results: list[LinkCheckResult], output_file: str) -> None:
        """Generate a detailed JSON report."""
        stats = self.generate_statistics(results)
        
        report_data = {
            "metadata": {
                "timestamp": self.report_timestamp.isoformat(),
                "total_links": stats.total_links,
                "success_rate": stats.success_rate
            },
            "statistics": asdict(stats),
            "detailed_results": []
        }
        
        # Add detailed results
        for result in results:
            result_data = {
                "url": result.link.url,
                "text": result.link.text,
                "source_file": result.link.source_file,
                "line_number": result.link.line_number,
                "link_type": result.link.link_type,
                "success": result.success,
                "status_code": result.status_code,
                "error_message": result.error_message,
                "redirect_url": result.redirect_url,
                "response_time": result.response_time
            }
            report_data["detailed_results"].append(result_data)
        
        # Write JSON report
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        b.info(f"Detailed JSON report saved to: {output_file}")
    
    def generate_markdown_report(self, results: list[LinkCheckResult], output_file: str) -> None:
        """Generate a detailed Markdown report."""
        stats = self.generate_statistics(results)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"# External Link Check Report\n\n")
            f.write(f"**Generated:** {self.report_timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Summary
            f.write("## Summary\n\n")
            f.write(f"- **Total links:** {stats.total_links}\n")
            f.write(f"- **Successful:** {stats.successful_links} ({stats.success_rate:.1f}%)\n")
            f.write(f"- **Failed:** {stats.failed_links} ({100-stats.success_rate:.1f}%)\n")
            f.write(f"- **Files with links:** {stats.files_with_links}\n")
            f.write(f"- **Files with broken links:** {stats.files_with_broken_links}\n\n")
            
            # Top domains
            if stats.domains:
                f.write("## Top Domains\n\n")
                f.write("| Domain | Links | Percentage |\n")
                f.write("|--------|-------|------------|\n")
                sorted_domains = sorted(stats.domains.items(), key=lambda x: x[1], reverse=True)
                for domain, count in sorted_domains[:15]:
                    percentage = (count / stats.total_links) * 100
                    f.write(f"| {domain} | {count} | {percentage:.1f}% |\n")
                f.write("\n")
            
            # Failed links
            failed_results = [r for r in results if not r.success]
            if failed_results:
                f.write("## Failed Links\n\n")
                f.write("| URL | File | Line | Error |\n")
                f.write("|-----|------|------|-------|\n")
                for result in failed_results:
                    link = result.link
                    f.write(f"| {link.url} | {link.source_file} | {link.line_number} | {result.error_message} |\n")
                f.write("\n")
            
            # All links by file
            f.write("## Links by File\n\n")
            grouped = self.group_by_file(results)
            for file_path in sorted(grouped.keys()):
                file_results = grouped[file_path]
                f.write(f"### {file_path}\n\n")
                f.write("| Line | URL | Status | Type |\n")
                f.write("|------|-----|--------|------|\n")
                for result in sorted(file_results, key=lambda x: x.link.line_number):
                    status = "✅" if result.success else "❌"
                    f.write(f"| {result.link.line_number} | {result.link.url} | {status} | {result.link.link_type} |\n")
                f.write("\n")
        
        b.info(f"Detailed Markdown report saved to: {output_file}")
    
    @staticmethod
    def get_failed_links(results: list[LinkCheckResult]) -> list[LinkCheckResult]:
        """Get only the failed link results."""
        return [r for r in results if not r.success]
    
    @staticmethod
    def group_by_file(results: list[LinkCheckResult]) -> dict[str, list[LinkCheckResult]]:
        """Group results by source file."""
        grouped = {}
        for result in results:
            file_path = result.link.source_file
            if file_path not in grouped:
                grouped[file_path] = []
            grouped[file_path].append(result)
        return grouped
