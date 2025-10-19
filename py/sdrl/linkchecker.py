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

import requests as req

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
    validation_rule: tg.Optional[LinkValidationRule] = None
    
    def __str__(self) -> str:
        return f"{self.url} in {self.source_file}:{self.line_number}"


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
                    links.append(ExternalLink(url, text, filepath, line_num, current_validation_rule))
                    current_validation_rule = None  # Rule applies to next link only
            
            # Extract HREF macro links: [HREF::url]
            for match in self.href_macro_regex.finditer(line):
                url = match.group(1)
                if self._is_external_url(url):
                    links.append(ExternalLink(url, url, filepath, line_num, current_validation_rule))
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
    
    def __init__(self, timeout: int = 10, max_retries: int = 2, delay_between_requests: float = 1.0, delay_per_host: float = 2.0):
        self.timeout = timeout
        self.max_retries = max_retries
        self.delay_between_requests = delay_between_requests
        self.delay_per_host = delay_per_host  # Additional delay when checking same host
        self.session = req.Session()
        self.host_last_request = {}  # Track last request time per host
        
        # Set browser-like headers to avoid triggering anti-crawling mechanisms
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,de;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
    
    def check_link(self, link: ExternalLink) -> LinkCheckResult:
        """Check accessibility of a single external link using HEAD request."""
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
                
                # Determine request method: use HEAD unless content checking is needed
                # This strictly follows professor's requirement: "A link checker should use HEAD, not GET"
                # Only exception: when explicit content validation is required (content= rule)
                use_get = (link.validation_rule and link.validation_rule.required_text)
                method = 'GET' if use_get else 'HEAD'
                
                response = self.session.request(
                    method,
                    link.url, 
                    timeout=timeout, 
                    allow_redirects=follow_redirects,
                    verify=verify_ssl
                )
                response_time = round(time.time() - start_time, 3)
                
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
                
            except req.exceptions.Timeout:
                if attempt == self.max_retries:
                    return LinkCheckResult(
                        link=link,
                        success=False,
                        error_message="Connection timeout"
                    )
                time.sleep(1 * (attempt + 1))  # Exponential backoff
                
            except req.exceptions.ConnectionError as e:
                if attempt == self.max_retries:
                    return LinkCheckResult(
                        link=link,
                        success=False,
                        error_message=f"Connection error: {str(e)}"
                    )
                time.sleep(1 * (attempt + 1))
                
            except req.exceptions.RequestException as e:
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
    
    def _wait_for_host_delay(self, url: str):
        """Wait for appropriate delay based on host to avoid anti-crawling mechanisms."""
        try:
            from urllib.parse import urlparse
            host = urlparse(url).netloc.lower()
            
            current_time = time.time()
            required_delay = self.delay_per_host
            
            if host in self.host_last_request:
                time_since_last = current_time - self.host_last_request[host]
                if time_since_last < required_delay:
                    sleep_time = required_delay - time_since_last
                    time.sleep(sleep_time)
            
            # Update last request time for this host
            self.host_last_request[host] = time.time()
            
        except Exception:
            # If we can't parse the URL, just use the general delay
            pass
    
    def _create_unique_key(self, link: ExternalLink) -> str:
        """Create a unique key for a link that includes URL and validation rules."""
        validation_key = ""
        if link.validation_rule:
            rule = link.validation_rule
            validation_key = f"|status:{rule.expected_status}|text:{rule.required_text}|ssl:{rule.ignore_ssl}|timeout:{rule.timeout}"
        
        return f"{link.url}{validation_key}"
    
    def check_links(self, links: list[ExternalLink], show_progress: bool = True) -> list[LinkCheckResult]:
        """Check multiple links, avoiding duplicate URL checks."""
        if not links:
            return []
        
        # Deduplicate URLs while considering validation rules
        # URLs with different validation rules should be treated as separate checks
        url_to_link = {}
        for link in links:
            unique_key = self._create_unique_key(link)
            if unique_key not in url_to_link:
                url_to_link[unique_key] = link
        
        unique_links = list(url_to_link.values())
        total_original_links = len(links)
        total_unique_links = len(unique_links)
        
        # Display summary of links found
        if show_progress:
            b.info(f"Found {total_original_links} external links to validate")
            if total_original_links != total_unique_links:
                duplicate_count = total_original_links - total_unique_links
                b.info(f"After deduplication: {total_unique_links} unique URLs ({duplicate_count} duplicates removed)")
            else:
                b.info(f"All {total_unique_links} links are unique URLs")
        
        results = []
        total_links = total_unique_links
        
        for i, link in enumerate(unique_links):
            if show_progress:
                b.info(f"Checking link {i+1}/{total_links}: {link.url}")
            
            # Implement per-host delay to avoid triggering anti-crawling mechanisms
            self._wait_for_host_delay(link.url)
            
            result = self.check_link(link)
            results.append(result)
            
            # Add general delay between requests to be respectful to servers
            if i < total_links - 1:
                time.sleep(self.delay_between_requests)
        
        # Map results back to all original links (including duplicates)
        # Create a mapping using the same unique key logic
        unique_key_to_result = {}
        for result in results:
            unique_key = self._create_unique_key(result.link)
            unique_key_to_result[unique_key] = result
        
        all_results = []
        for link in links:
            unique_key = self._create_unique_key(link)
            original_result = unique_key_to_result[unique_key]
            
            # Create new result with the original link (preserving file/line info)
            all_results.append(LinkCheckResult(
                link=link,
                success=original_result.success,
                status_code=original_result.status_code,
                error_message=original_result.error_message,
                response_time=original_result.response_time,
                redirect_url=original_result.redirect_url
            ))
        
        return all_results


@dataclass
class LinkStatistics:
    """Statistical summary of link checking results."""
    total_links: int = 0
    unique_urls_checked: int = 0  # Number of unique URLs actually checked
    successful_links: int = 0
    failed_links: int = 0
    total_files: int = 0
    files_with_links: int = 0
    files_with_failed_links: int = 0  # Files containing links that failed validation
    domains: dict[str, int] = None
    status_codes: dict[int, int] = None
    error_types: dict[str, int] = None
    
    def __post_init__(self):
        if self.domains is None:
            self.domains = {}
        if self.status_codes is None:
            self.status_codes = {}
        if self.error_types is None:
            self.error_types = {}
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_links == 0:
            return 0.0
        return round((self.successful_links / self.total_links) * 100, 3)


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
        
        # Calculate unique URLs checked
        unique_urls = set(result.link.url for result in results)
        stats.unique_urls_checked = len(unique_urls)
        
        file_set = set()
        files_with_links = set()
        files_with_failed_links = set()
        
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
                files_with_failed_links.add(link.source_file)
            
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
        
        stats.total_files = len(file_set)
        stats.files_with_links = len(files_with_links)
        stats.files_with_failed_links = len(files_with_failed_links)
        
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
        elif '405' in error_lower or 'method not allowed' in error_lower:
            return '405_method_not_allowed'
        elif '500' in error_lower or 'server error' in error_lower:
            return '500_server_error'
        elif 'connection' in error_lower:
            return 'connection_error'
        elif 'ssl' in error_lower or 'certificate' in error_lower:
            return 'ssl_error'
        else:
            return 'other'
    
    def print_summary(self, results: list[LinkCheckResult]) -> None:
        """Print a summary of link checking results with integrated statistics."""
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
        b.info(f"  Files with failed links: {stats.files_with_failed_links}")
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
                b.error(f"     Error: {result.error_message}")
                if result.status_code:
                    b.error(f"     Status: {result.status_code}")
            b.info("")
        
        # Final status
        b.info("=" * 60)
        if failed_results:
            # Count by HTTP status code
            status_counts = {}
            other_errors = 0
            for result in failed_results:
                if result.status_code:
                    status_counts[result.status_code] = status_counts.get(result.status_code, 0) + 1
                else:
                    other_errors += 1
            
            # Build status breakdown string
            breakdown_parts = []
            for status_code in sorted(status_counts.keys()):
                breakdown_parts.append(f"{status_code}: {status_counts[status_code]}")
            if other_errors > 0:
                breakdown_parts.append(f"other: {other_errors}")
            breakdown = ", ".join(breakdown_parts)
            
            b.error(f"VALIDATION FAILED: {len(failed_results)}/{stats.total_links} links failed validation ({breakdown})")
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
            405: "Method Not Allowed",
            500: "Internal Server Error",
            502: "Bad Gateway",
            503: "Service Unavailable",
            504: "Gateway Timeout"
        }
        return descriptions.get(status_code, "Unknown")
    
    def generate_json_report(self, results: list[LinkCheckResult], output_file: str = "link_check_report.json") -> None:
        """Generate a detailed JSON report with fixed filename."""
        stats = self.generate_statistics(results)
        
        # Sort domains by count (descending)
        sorted_domains = dict(sorted(stats.domains.items(), key=lambda x: x[1], reverse=True))
        
        report_data = {
            "metadata": {
                "timestamp": self.report_timestamp.isoformat(),
                "total_links": stats.total_links,
                "unique_urls_checked": stats.unique_urls_checked,
                "success_rate": stats.success_rate
            },
            "statistics": {
                "total_links": stats.total_links,
                "unique_urls_checked": stats.unique_urls_checked,
                "duplicate_urls": stats.total_links - stats.unique_urls_checked,
                "successful_links": stats.successful_links,
                "failed_links": stats.failed_links,
                "total_files": stats.total_files,
                "files_with_links": stats.files_with_links,
                "files_with_failed_links": stats.files_with_failed_links,
                "domains": sorted_domains,
                "status_codes": stats.status_codes,
                "error_types": stats.error_types
            },
            "detailed_results": []
        }
        
        # Add detailed results (simplified fields)
        for result in results:
            result_data = {
                "url": result.link.url,
                "text": result.link.text,
                "source_file": result.link.source_file,
                "line_number": result.link.line_number,
                "status_code": result.status_code,
                "response_time": result.response_time
            }
            
            # Only include non-null optional fields
            if result.error_message:
                result_data["error_message"] = result.error_message
            if result.redirect_url:
                result_data["redirect_url"] = result.redirect_url
            
            report_data["detailed_results"].append(result_data)
        
        # Write JSON report
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        b.info(f"Detailed JSON report saved to: {output_file}")
    
    def generate_markdown_report(self, results: list[LinkCheckResult], output_file: str = "link_check_report.md") -> None:
        """Generate a simplified Markdown report with fixed filename."""
        stats = self.generate_statistics(results)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"# External Link Check Report\n\n")
            f.write(f"**Generated:** {self.report_timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Summary
            f.write("## Summary\n\n")
            f.write(f"- **Total links found:** {stats.total_links} (includes duplicate URLs)\n")
            f.write(f"- **Unique URLs checked:** {stats.unique_urls_checked}\n")
            if stats.unique_urls_checked != stats.total_links:
                duplicates = stats.total_links - stats.unique_urls_checked
                f.write(f"- **Duplicate URLs:** {duplicates} ({duplicates/stats.total_links*100:.1f}%)\n")
            f.write(f"- **Successful:** {stats.successful_links} ({stats.success_rate:.1f}%)\n")
            f.write(f"- **Failed:** {stats.failed_links} ({100-stats.success_rate:.1f}%)\n")
            f.write(f"- **Files with links:** {stats.files_with_links}\n")
            f.write(f"- **Files with failed links:** {stats.files_with_failed_links}\n\n")
            
            # Clarification about duplicate handling
            if stats.unique_urls_checked != stats.total_links:
                f.write("### Note on Link Deduplication\n\n")
                f.write(f"Found {stats.total_links} total link references, but only {stats.unique_urls_checked} unique URLs. ")
                f.write("Each unique URL is checked only once for efficiency, but the result applies to all instances of that URL. ")
                f.write("This explains why the number of failed links may seem lower than expected.\n\n")
            
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
            
            # Failed links table (sorted by error type, then filename)
            failed_results = [r for r in results if not r.success]
            if failed_results:
                f.write("## Failed Links\n\n")
                f.write("| Error Type | URL | File | Line |\n")
                f.write("|------------|-----|------|------|\n")
                
                # Sort by error type first, then by filename
                def sort_key(result):
                    error_type = self._categorize_error(result.error_message) if result.error_message else 'unknown'
                    return (error_type, result.link.source_file)
                
                for result in sorted(failed_results, key=sort_key):
                    link = result.link
                    error_type = self._categorize_error(result.error_message) if result.error_message else 'unknown'
                    f.write(f"| {error_type} | {link.url} | {link.source_file} | {link.line_number} |\n")
                f.write("\n")
            
            # Links by file (simplified format)
            f.write("## Links by File\n\n")
            grouped = self.group_by_file(results)
            for file_path in sorted(grouped.keys()):
                file_results = grouped[file_path]
                f.write(f"### {file_path}\n\n")
                for result in sorted(file_results, key=lambda x: x.link.line_number):
                    status = "[PASS]" if result.success else "[FAIL]"
                    f.write(f"  {status} {result.link.line_number}: {result.link.url}\n")
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
