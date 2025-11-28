"""
External link checker for SeDriLa courses.

This module provides functionality to extract and validate external links
from markdown files in SeDriLa tasks.
"""
import concurrent.futures
import os
import re
import threading
import time
import typing
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlparse
import requests
import base


@dataclass
class LinkValidationRule:
    """Custom validation rule for a specific link."""
    expected_status: typing.Optional[int] = None
    required_text: typing.Optional[str] = None
    ignore_cert: bool = False
    timeout: typing.Optional[int] = None


@dataclass
class ExternalLink:
    """Represents an external link found in a markdown file."""
    url: str
    text: str
    source_file: str
    line_number: int
    validation_rule: typing.Optional[LinkValidationRule] = None
    
    def __str__(self) -> str:
        return f"{self.url} in {self.source_file}:{self.line_number}"


@dataclass
class LinkCheckResult:
    """Result of checking an external link."""
    link: ExternalLink
    success: bool
    status_code: typing.Optional[int] = None
    error_message: typing.Optional[str] = None
    response_time: typing.Optional[float] = None
    redirect_url: typing.Optional[str] = None


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
        except OSError as e:
            base.error(f"Cannot read file {filepath}: {e}")
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
    
    @staticmethod
    def _is_external_url(url: str) -> bool:
        """Check if URL is external (http/https)."""
        parsed = urlparse(url)
        return parsed.scheme in ('http', 'https')
    
    @staticmethod
    def _parse_validation_rule(rule_text: str) -> LinkValidationRule:
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
                        base.warning(f"Invalid status code in LINK_CHECK: {value}")
                elif key == 'content' or key == 'text':
                    rule.required_text = value
                elif key == 'ignore_cert':
                    rule.ignore_cert = value.lower() in ('true', '1', 'yes')
                elif key == 'timeout':
                    try:
                        rule.timeout = int(value)
                    except ValueError:
                        base.warning(f"Invalid timeout in LINK_CHECK: {value}")
        return rule


class LinkChecker:
    """Validates external links by making HTTP requests."""
    timeout: int
    max_retries: int
    delay_between_requests: float
    delay_per_host: float
    session: requests.Session
    host_last_request: dict[str, float]
    
    def __init__(self, timeout: int = 20, max_retries: int = 2, 
                 delay_between_requests: float = 1.0, delay_per_host: float = 2.0,
                 max_workers: typing.Optional[int] = None):
        self.timeout = timeout
        self.max_retries = max_retries
        self.delay_between_requests = delay_between_requests
        self.delay_per_host = delay_per_host  # Additional delay when checking same host
        self.session = requests.Session()
        self.host_last_request = {}  # Track last request time per host
        self._host_lock = threading.Lock()
        self.max_workers = self._determine_max_workers(max_workers)
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
    
    @staticmethod
    def _determine_max_workers(override: typing.Optional[int]) -> int:
        """Resolve worker count from constructor override or environment variable."""
        default_workers = 10
        if override is not None:
            if override < 1:
                base.warning("max_workers must be >= 1; falling back to default 10")
                return default_workers
            return override
        env_value = os.getenv("SDRL_LINKCHECK_MAX_WORKERS")
        if not env_value:
            return default_workers
        try:
            parsed = int(env_value)
            if parsed < 1:
                raise ValueError("value must be >= 1")
            return parsed
        except ValueError:
            base.warning(f"Invalid SDRL_LINKCHECK_MAX_WORKERS='{env_value}', using default {default_workers}")
            return default_workers
    
    def check_link(self, link: ExternalLink) -> LinkCheckResult:
        """Check accessibility of a single external link using HEAD or GET request."""
        for attempt in range(self.max_retries + 1):
            try:
                start_time = time.time()
                # Use custom timeout and SSL settings if specified
                timeout = link.validation_rule.timeout if link.validation_rule and link.validation_rule.timeout \
                    else self.timeout
                verify_ssl = not (link.validation_rule and link.validation_rule.ignore_cert)
                # If expecting a specific redirect status, don't follow redirects
                follow_redirects = True
                if link.validation_rule and link.validation_rule.expected_status:
                    if link.validation_rule.expected_status in [301, 302, 303, 307, 308]:
                        follow_redirects = False
                # Determine request method: use HEAD unless content checking is needed
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
                    except UnicodeDecodeError as e:
                        content_ok = False
                        content_error = f"Could not decode response: {e}"
                    else:
                        if link.validation_rule.required_text not in content:
                            content_ok = False
                            content_error = f"Required text '{link.validation_rule.required_text}' not found"
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
    
    def _wait_for_host_delay(self, url: str):
        """Wait for appropriate delay based on host to avoid anti-crawling mechanisms."""
        host = urlparse(url).netloc.lower()
        if not host:
            return
        required_delay = self.delay_per_host
        sleep_time = 0.0
        with self._host_lock:
            now = time.time()
            if host in self.host_last_request:
                time_since_last = now - self.host_last_request[host]
                if time_since_last < required_delay:
                    sleep_time = required_delay - time_since_last
            # Reserve the slot in advance so that other threads see the delay
            self.host_last_request[host] = now + sleep_time
        if sleep_time > 0:
            time.sleep(sleep_time)
    
    @staticmethod
    def _create_unique_key(link: ExternalLink) -> str:
        """Create a unique key for a link that includes URL and validation rules."""
        validation_key = ""
        if link.validation_rule:
            rule = link.validation_rule
            validation_key = (f"|status:{rule.expected_status}|text:{rule.required_text}|"
                              f"cert:{rule.ignore_cert}|timeout:{rule.timeout}")
        
        return f"{link.url}{validation_key}"
    
    def _check_single_link_with_delay(self, link: ExternalLink) -> LinkCheckResult:
        """Helper to enforce host delay before checking a single link."""
        self._wait_for_host_delay(link.url)
        return self.check_link(link)
    
    def check_links(self, links: list[ExternalLink], show_progress: bool = True, 
                    batch_mode: bool = False) -> list[LinkCheckResult]:
        """Check multiple links, avoiding duplicate URL checks.
        
        Args:
            links: List of links to check
            show_progress: Show progress messages for each link
            batch_mode: If True, reduce verbosity for batch/CI use (only show summary)
        """
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
        if show_progress and not batch_mode:
            base.info(f"Found {total_original_links} external links to validate")
            if total_original_links != total_unique_links:
                duplicate_count = total_original_links - total_unique_links
                base.info(f"After deduplication: {total_unique_links} unique URLs ({duplicate_count} duplicates removed)")
            else:
                base.info(f"All {total_unique_links} links are unique URLs")
        elif batch_mode:
            # Batch mode: only essential info
            base.info(f"Checking {total_unique_links} unique URLs ({total_original_links} total references)...")
        results: list[LinkCheckResult] = []
        total_links = total_unique_links
        if batch_mode:
            # Batch/CI mode: perform HTTP checks in parallel using a thread pool.
            workers = min(self.max_workers, total_links) if total_links > 0 else 0
            if workers <= 1:
                for i, link in enumerate(unique_links):
                    if show_progress and not batch_mode:
                        base.info(f"Checking link {i+1}/{total_links}: {link.url}")
                    results.append(self._check_single_link_with_delay(link))
            else:
                with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                    # executor.map preserves the order of unique_links
                    for i, result in enumerate(executor.map(self._check_single_link_with_delay, unique_links)):
                        if show_progress and not batch_mode:
                            base.info(f"Checking link {i+1}/{total_links}")
                        results.append(result)
        else:
            # Original sequential behavior (kept for interactive/verbose runs)
            for i, link in enumerate(unique_links):
                if show_progress and not batch_mode:
                    base.info(f"Checking link {i+1}/{total_links}: {link.url}")
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
    domain_failures: dict[str, int] = None
    status_codes: dict[int, int] = None
    error_types: dict[str, int] = None
    def __post_init__(self):
        if self.domains is None:
            self.domains = {}
        if self.domain_failures is None:
            self.domain_failures = {}
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
            except:
                domain = 'invalid'
            stats.domains[domain] = stats.domains.get(domain, 0) + 1
            if not result.success:
                stats.domain_failures[domain] = stats.domain_failures.get(domain, 0) + 1
            # Status code analysis
            if result.status_code:
                stats.status_codes[result.status_code] = stats.status_codes.get(result.status_code, 0) + 1
            # Error type analysis
            if not result.success:
                error_key = self._categorize_error(result)
                stats.error_types[error_key] = stats.error_types.get(error_key, 0) + 1
        stats.total_files = len(file_set)
        stats.files_with_links = len(files_with_links)
        stats.files_with_failed_links = len(files_with_failed_links)
        return stats
    
    def _categorize_error(self, result: LinkCheckResult) -> str:
        """Categorize failed link results.
        
        Prefers HTTP status codes taken directly from the response. Falls back to
        parsing the error message only when no status code is available.
        """
        if result.status_code:
            return str(result.status_code)
        error_message = result.error_message or ""
        error_lower = error_message.lower()
        if not error_message:
            return 'other'
        # Non-HTTP status code errors
        if 'timeout' in error_lower or 'timed out' in error_lower:
            return 'timeout'
        if 'connection' in error_lower:
            return 'network'
        if 'ssl' in error_lower or 'certificate' in error_lower:
            return 'ssl'
        # HTTP status codes
        import re
        status_match = re.search(r'\b(4\d{2}|5\d{2})\b', error_message)
        if status_match:
            return status_match.group(1)
        return 'other'
    
    def render_markdown_report(self, results: list[LinkCheckResult]) -> str:
        """Render the Markdown report content and return it as a string."""
        stats = self.generate_statistics(results)
        lines: list[str] = []
        lines.append("# External Link Check Report\n\n")
        lines.append(f"**Generated:** {self.report_timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        # Summary
        lines.append("## Summary\n\n")
        lines.append(f"- **Total links found:** {stats.total_links} (includes duplicate URLs)\n")
        lines.append(f"- **Unique URLs checked:** {stats.unique_urls_checked}\n")
        if stats.unique_urls_checked != stats.total_links and stats.total_links:
            duplicates = stats.total_links - stats.unique_urls_checked
            percentage = (duplicates / stats.total_links) * 100
            lines.append(f"- **Duplicate URLs:** {duplicates} ({percentage:.1f}%)\n")
        lines.append(f"- **Successful:** {stats.successful_links} ({stats.success_rate:.1f}%)\n")
        failed_rate = (100 - stats.success_rate) if stats.total_links else 0.0
        lines.append(f"- **Failed:** {stats.failed_links} ({failed_rate:.1f}%)\n")
        lines.append(f"- **Files with links:** {stats.files_with_links}\n")
        lines.append(f"- **Files with failed links:** {stats.files_with_failed_links}\n\n")
        # Clarification about duplicate handling
        if stats.unique_urls_checked != stats.total_links and stats.total_links:
            lines.append("### Note on Link Deduplication\n\n")
            lines.append(f"Found {stats.total_links} total link references, but only {stats.unique_urls_checked} unique URLs. ")
            lines.append("Each unique URL is checked only once for efficiency, but the result applies to all instances of that URL. ")
            lines.append("This explains why the number of failed links may seem lower than expected.\n\n")
        # Top domains
        if stats.domains:
            lines.append("## Top Link Target Domains\n\n")
            lines.append("| Domain | Links | #Failed Links |\n")
            lines.append("|--------|-------|---------------|\n")
            sorted_domains = sorted(
                stats.domains.items(),
                key=lambda item: (
                    -stats.domain_failures.get(item[0], 0),
                    -item[1],
                    item[0]
                )
            )
            for domain, count in sorted_domains[:15]:
                failed = stats.domain_failures.get(domain, 0)
                lines.append(f"| `{domain}` | {count} | {failed} |\n")
            lines.append("\n")
        # Failed links table (sorted by URL for better grouping)
        failed_results = [r for r in results if not r.success]
        if failed_results:
            lines.append("## Failed Links\n\n")
            lines.append("| Status | URL | File | Line |\n")
            lines.append("|------------|-----|------|------|\n")
            for result in sorted(failed_results, key=lambda r: (r.link.url, r.link.source_file, r.link.line_number)):
                link = result.link
                error_type = self._categorize_error(result)
                lines.append(f"| {error_type} | {link.url} | {link.source_file} | {link.line_number} |\n")
            lines.append("\n")
        # Links by file
        lines.append("## Links by File\n\n")
        failed_grouped = self.group_by_file([res for res in results if not res.success])
        if not failed_grouped:
            lines.append("No link failures were detected.\n\n")
        else:
            for file_path in sorted(failed_grouped.keys()):
                file_results = failed_grouped[file_path]
                lines.append(f"### {file_path}\n\n")
                for result in sorted(file_results, key=lambda x: x.link.line_number):
                    status = self._categorize_error(result)
                    lines.append(f"  [{status}] {result.link.line_number}: {result.link.url}\n")
                lines.append("\n")
        
        return "".join(lines)
    
    def generate_markdown_report(self, results: list[LinkCheckResult], output_file: str = "link_check_report.md") -> str:
        """Write the Markdown report to disk and return its content."""
        content = self.render_markdown_report(results)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)
        return content
    
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
