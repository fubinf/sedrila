# pytest tests
import contextlib
import itertools
import os
import tempfile
import textwrap # for code format
import pytest

import base as b
import cache
import sdrl.constants as c
import sdrl.course
import sdrl.directory as dir
import sdrl.elements
import sdrl.linkchecker as linkchecker
import sdrl.macros
import sdrl.subcmd.maintainer as maintainer
import yaml

# Test constants
TEST_URL_SEDRILA = "https://sedrila.readthedocs.io"
TEST_URL_SEDRILA_404 = "https://sedrila.readthedocs.io/en/latest/nonexistent-page-xyz123"
TEST_URL_EXAMPLE = "https://example.com"
TEST_CONTENT_SEDRILA = "SeDriLa"
TEST_CONTENT_NONEXISTENT = "ThisTextShouldNotExistAnywhere123456"

# Course structure constants
TEST_CHDIR_NAME = "ch"
TEST_ALTDIR_NAME = "alt"
TEST_STAGES = ["draft", "alpha", "beta"]
TEST_CHAPTER_NAME = "Chapter1"
TEST_TASKGROUP_A = "TaskgroupA"
TEST_TASKGROUP_B = "TaskgroupB"
TEST_TASKGROUP_C = "TaskgroupC"
TEST_SCENARIO_COURSE = "course"
TEST_SCENARIO_DUPLICATE = "duplicate"
TEST_SCENARIO_MISSING = "missing"


def write_markdown(tmp_path, content, filename="test.md"):
    """Write markdown content into tmp_path and return the file path."""
    path = tmp_path / filename
    path.write_text(content, encoding='utf-8')
    return str(path)


class FakeResponse:
    """Small stub mimicking the requests response we care about."""
    def __init__(self, url: str, status_code: int = 200, text: str = ""):
        self.url = url
        self.status_code = status_code
        self.text = text


def stub_requests(monkeypatch, responses: list[FakeResponse]):
    """Replace Session.request with deterministic queued responses."""
    queue = list(responses)
    def fake_request(self, method, url, **_kwargs):
        assert queue, f"unexpected request to {url}"
        response = queue.pop(0)
        assert response.url == url
        return response
    monkeypatch.setattr(linkchecker.requests.Session, "request", fake_request)


@contextlib.contextmanager
def course_env(include_stage: str):
    """Yield a Coursebuilder configured for the requested stage."""
    original_cwd = os.getcwd()
    the_cache = None
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            create_test_course_structure(tmpdir)
            targetdir_s = os.path.join(tmpdir, 'output')
            targetdir_i = os.path.join(tmpdir, 'output_i')
            os.makedirs(targetdir_s, exist_ok=True)
            os.makedirs(targetdir_i, exist_ok=True)
            os.chdir(tmpdir)
            sdrl.macros.macrodefs_early.clear()
            sdrl.macros.macrodefs_late.clear()
            sdrl.macros.macrostate.clear()
            the_cache = cache.SedrilaCache(os.path.join(targetdir_i, c.CACHE_FILENAME), start_clean=True)
            b.set_register_files_callback(the_cache.set_file_dirty)
            directory = dir.Directory(the_cache)
            course = sdrl.course.Coursebuilder(
                configfile='sedrila.yaml',
                context='test',
                include_stage=include_stage,
                targetdir_s=targetdir_s,
                targetdir_i=targetdir_i,
                directory=directory
            )
            allparts = list(itertools.chain(
                directory.get_all(sdrl.course.Chapter),
                directory.get_all(sdrl.course.Taskgroup),
                directory.get_all(sdrl.course.Task)
            ))
            for part in allparts:
                topmatter_elem = directory.get_the(sdrl.elements.Topmatter, part.name)
                topmatter_elem.do_build()
                part.process_topmatter(part.sourcefile, topmatter_elem.value, course)
            yield course
    finally:
        b.set_register_files_callback(None)
        if the_cache:
            the_cache.close()
        os.chdir(original_cwd)


@pytest.mark.parametrize(
    ("comment", "expect_success", "expect_error"),
    [
        pytest.param("", False, "404", id="no_rule_404_fails"),
        pytest.param("<!-- @LINK_SPEC: status=404 -->\n", True, None, id="rule_404_expected_ok"),
    ],
)
def test_status_rule_controls_result(tmp_path, monkeypatch, comment, expect_success, expect_error):
    """Validate that @LINK_SPEC status overrides success evaluation."""
    url = TEST_URL_SEDRILA_404
    markdown = f"""# Test File
    {comment}Broken link: [Target]({url})
    """
    path = write_markdown(tmp_path, markdown)
    extractor = linkchecker.LinkExtractor()
    links = extractor.extract_links_from_file(path)
    assert len(links) == 1, f"Expected 1 link, found {len(links)}"
    rule = links[0].validation_rule
    if comment:
        assert rule and rule.expected_status == 404
    else:
        assert rule is None
    stub_requests(monkeypatch, [FakeResponse(url, status_code=404)])
    result = linkchecker.LinkChecker().check_links(links, show_progress=False)[0]
    assert result.status_code == 404
    assert result.success is expect_success
    if expect_error:
        assert expect_error in (result.error_message or "")
    else:
        assert result.error_message is None


def test_content_rule(tmp_path, monkeypatch):
    """Ensure required text validation passes/fails as expected."""
    url1 = TEST_URL_SEDRILA
    url2 = f"{TEST_URL_SEDRILA}/docs"
    markdown = f"""# Test File
    <!-- @LINK_SPEC: content="{TEST_CONTENT_SEDRILA}" -->
    Good link: [Docs]({url1})
    <!-- @LINK_SPEC: content="{TEST_CONTENT_NONEXISTENT}" -->
    Bad link: [Docs again]({url2})
    """
    path = write_markdown(tmp_path, markdown)
    extractor = linkchecker.LinkExtractor()
    links = extractor.extract_links_from_file(path)
    rule_texts = [link.validation_rule.required_text for link in links]
    assert rule_texts == [TEST_CONTENT_SEDRILA, TEST_CONTENT_NONEXISTENT]
    stub_requests(monkeypatch, [
        FakeResponse(url1, status_code=200, text=f"...{TEST_CONTENT_SEDRILA}..."),
        FakeResponse(url2, status_code=200, text="nothing to see"),
    ])
    results = linkchecker.LinkChecker().check_links(links, show_progress=False)
    by_text = {res.link.validation_rule.required_text: res for res in results}
    assert by_text[TEST_CONTENT_SEDRILA].success
    assert not by_text[TEST_CONTENT_NONEXISTENT].success
    assert "Required text" in (by_text[TEST_CONTENT_NONEXISTENT].error_message or "")

def test_extractor_parses_rules_and_macros(tmp_path):
    """Confirm the extractor reads @LINK_SPEC rules and HREF macros."""
    markdown = f"""# Test File
    <!-- @LINK_SPEC: status=301, timeout=15, ignore_cert=true -->
    Regular link: [Regular]({TEST_URL_EXAMPLE})
    <!-- @LINK_SPEC: content="hello world" -->
    Another link: [Another](https://example.org)
    Macro link: [HREF::https://github.com/fubinf/sedrila]
    """
    path = write_markdown(tmp_path, markdown)
    extractor = linkchecker.LinkExtractor()
    links = extractor.extract_links_from_file(path)
    assert len(links) == 3, f"Expected 3 links, found {len(links)}"
    by_url = {link.url: link for link in links}
    rule1 = by_url[TEST_URL_EXAMPLE].validation_rule
    assert rule1.expected_status == 301
    assert rule1.timeout == 15
    assert rule1.ignore_cert
    rule2 = by_url["https://example.org"].validation_rule
    assert rule2.required_text == "hello world"
    href_link = by_url["https://github.com/fubinf/sedrila"]
    assert href_link.text == href_link.url


def test_check_links_deduplicates_in_batch_mode(tmp_path, monkeypatch):
    """Only one HTTP call should run for duplicate URLs."""
    markdown = f"""# Test File
    First link: [Link1]({TEST_URL_EXAMPLE})
    Second link: [Link2]({TEST_URL_EXAMPLE})
    Third link: [Link3]({TEST_URL_EXAMPLE})
    """
    path = write_markdown(tmp_path, markdown)
    extractor = linkchecker.LinkExtractor()
    links = extractor.extract_links_from_file(path)
    assert len(links) == 3, f"Expected 3 links, found {len(links)}"
    checked = []
    def fake_check(self, link):
        checked.append(link.url)
        return linkchecker.LinkCheckResult(link=link, success=True, status_code=200)
    monkeypatch.setattr(linkchecker.LinkChecker, "check_link", fake_check)
    checker = linkchecker.LinkChecker(delay_between_requests=0, delay_per_host=0)
    results = checker.check_links(links, show_progress=False, batch_mode=True)
    assert len(checked) == 1, f"Expected 1 unique check, but made {len(checked)} requests"
    assert len(results) == len(links), f"Expected {len(links)} results, got {len(results)}"
    assert all(res.link.url == TEST_URL_EXAMPLE for res in results)


def test_uses_get_for_content_validation(tmp_path, monkeypatch):
    """LinkChecker should use GET when content validation is needed, HEAD otherwise."""
    used_methods = []
    def fake_request(self, method, url, **_kwargs):
        used_methods.append(method)
        return FakeResponse(url, status_code=200, text="content")
    monkeypatch.setattr(linkchecker.requests.Session, "request", fake_request)
    # HEAD
    link_no_content = linkchecker.ExternalLink(
        url=TEST_URL_EXAMPLE, text="Test", source_file="test.md", line_number=1)
    # GET
    link_with_content = linkchecker.ExternalLink(
        url=f"{TEST_URL_EXAMPLE}/page", text="Test", source_file="test.md", line_number=2,
        validation_rule=linkchecker.LinkValidationRule(required_text="content"))
    checker = linkchecker.LinkChecker()
    checker.check_link(link_no_content)
    checker.check_link(link_with_content)
    assert used_methods == ['HEAD', 'GET'], f"Expected ['HEAD', 'GET'], got {used_methods}"


def test_extract_links_from_empty_file(tmp_path):
    """Empty files should return empty link list."""
    path = write_markdown(tmp_path, "")
    extractor = linkchecker.LinkExtractor()
    links = extractor.extract_links_from_file(path)
    assert len(links) == 0, f"Expected 0 links from empty file, got {len(links)}"


def test_multiple_links_on_same_line(tmp_path):
    """Multiple links on the same line should all be extracted."""
    markdown = f"""# Test File
    Here are two links: [First]({TEST_URL_EXAMPLE}) and [Second]({TEST_URL_SEDRILA})
    """
    path = write_markdown(tmp_path, markdown)
    extractor = linkchecker.LinkExtractor()
    links = extractor.extract_links_from_file(path)
    assert len(links) == 2, f"Expected 2 links, got {len(links)}"
    urls = {link.url for link in links}
    assert urls == {TEST_URL_EXAMPLE, TEST_URL_SEDRILA}


def create_test_course_structure(base_dir):
    """Create a minimal multi-stage course structure for maintainer tests."""
    ch_dir = os.path.join(base_dir, TEST_CHDIR_NAME)
    alt_dir = os.path.join(base_dir, TEST_ALTDIR_NAME)
    os.makedirs(ch_dir, exist_ok=True)
    os.makedirs(alt_dir, exist_ok=True)
    config = {
        'title': 'Test Course',
        'name': 'test-course',
        'chapterdir': TEST_CHDIR_NAME,
        'altdir': TEST_ALTDIR_NAME,
        'stages': TEST_STAGES,
        'instructors': [],
        'allowed_attempts': '2',
        'chapters': [
            {
                'name': TEST_CHAPTER_NAME,
                'taskgroups': [
                    {'name': TEST_TASKGROUP_A},
                    {'name': TEST_TASKGROUP_B},
                    {'name': TEST_TASKGROUP_C},
                ]
            }
        ]
    }
    with open(os.path.join(base_dir, 'sedrila.yaml'), 'w') as f:
        yaml.dump(config, f)
    with open(os.path.join(ch_dir, 'glossary.md'), 'w') as f:
        f.write(textwrap.dedent("""
            title: Glossary
            ---
            # Glossary
        """).lstrip())
    chapter1_dir = os.path.join(ch_dir, TEST_CHAPTER_NAME)
    os.makedirs(chapter1_dir, exist_ok=True)
    with open(os.path.join(chapter1_dir, 'index.md'), 'w') as f:
        f.write(textwrap.dedent("""
            title: Chapter 1
            ---
            # Chapter 1
        """).lstrip())
    tga_dir = os.path.join(ch_dir, TEST_CHAPTER_NAME, TEST_TASKGROUP_A)
    os.makedirs(tga_dir, exist_ok=True)
    with open(os.path.join(tga_dir, 'index.md'), 'w') as f:
        f.write(textwrap.dedent("""
            title: Taskgroup A
            stage: beta
            ---
            # Taskgroup A

            Link in taskgroup: [Example](https://example.com)
        """).lstrip())
    with open(os.path.join(tga_dir, 'Task1.md'), 'w') as f:
        f.write(textwrap.dedent("""
            title: Task 1
            stage: beta
            timevalue: 1.0
            difficulty: 2
            ---
            # Task 1

            Link in task: [GitHub](https://github.com)
        """).lstrip())
    tgb_dir = os.path.join(ch_dir, TEST_CHAPTER_NAME, TEST_TASKGROUP_B)
    os.makedirs(tgb_dir, exist_ok=True)
    with open(os.path.join(tgb_dir, 'index.md'), 'w') as f:
        f.write(textwrap.dedent("""
            title: Taskgroup B
            stage: alpha
            ---
            # Taskgroup B

            Another link: [Python](https://python.org)
        """).lstrip())
    with open(os.path.join(tgb_dir, 'Task2.md'), 'w') as f:
        f.write(textwrap.dedent("""
            title: Task 2
            stage: alpha
            timevalue: 1.5
            difficulty: 3
            ---
            # Task 2

            Yet another link: [ReadTheDocs](https://readthedocs.org)
        """).lstrip())
    tgc_dir = os.path.join(ch_dir, TEST_CHAPTER_NAME, TEST_TASKGROUP_C)
    os.makedirs(tgc_dir, exist_ok=True)
    with open(os.path.join(tgc_dir, 'index.md'), 'w') as f:
        f.write(textwrap.dedent("""
            title: Taskgroup C
            stage: draft
            ---
            # Taskgroup C

            Draft link: [Wikipedia](https://wikipedia.org)
        """).lstrip())
    alt_tga_dir = os.path.join(alt_dir, TEST_CHAPTER_NAME, TEST_TASKGROUP_A)
    os.makedirs(alt_tga_dir, exist_ok=True)
    with open(os.path.join(alt_tga_dir, 'index.md'), 'w') as f:
        f.write(textwrap.dedent("""
            title: Taskgroup A Alt
            stage: beta
            ---
            # Taskgroup A (Alt version)

            Alt link: [MDN](https://developer.mozilla.org)
        """).lstrip())
    not_in_config_dir = os.path.join(ch_dir, TEST_CHAPTER_NAME, 'NotInConfig')
    os.makedirs(not_in_config_dir, exist_ok=True)
    with open(os.path.join(not_in_config_dir, 'index.md'), 'w') as f:
        f.write(textwrap.dedent("""
            title: Not In Config
            ---
            # This should be ignored

            This file is not in sedrila.yaml: [Should Be Ignored](https://ignored.com)
        """).lstrip())
    return base_dir


def test_extract_files_respects_stages():
    """Only beta-stage files should be included when include_stage=beta."""
    with course_env('beta') as course:
        files = maintainer.extract_markdown_files_from_course(course)
    filenames = {os.path.basename(f) for f in files}
    expected = {'index.md', 'Task1.md'}
    assert filenames == expected, f"Expected {expected}, got {filenames}"


def test_extract_files_ignores_unconfigured_taskgroups():
    """Files absent from sedrila.yaml must not be returned."""
    with course_env('draft') as course:
        files = maintainer.extract_markdown_files_from_course(course)
    for filepath in files:
        assert 'NotInConfig' not in filepath, f"Unconfigured taskgroup file should be ignored: {filepath}"


def prepare_altdir_scenario(tmp_path, scenario: str):
    """Create chapter/altdir fixtures for the given test scenario."""
    ch_dir = tmp_path / TEST_CHDIR_NAME
    alt_dir = tmp_path / TEST_ALTDIR_NAME
    ch_dir.mkdir(parents=True, exist_ok=True)
    alt_dir.mkdir(parents=True, exist_ok=True)
    if scenario == TEST_SCENARIO_COURSE:
        tga = ch_dir / TEST_CHAPTER_NAME / TEST_TASKGROUP_A
        tga.mkdir(parents=True, exist_ok=True)
        ch_index = tga / 'index.md'
        ch_task = tga / 'Task1.md'
        ch_index.write_text("ch index", encoding='utf-8')
        ch_task.write_text("ch task", encoding='utf-8')
        alt_tga = alt_dir / TEST_CHAPTER_NAME / TEST_TASKGROUP_A
        alt_tga.mkdir(parents=True, exist_ok=True)
        alt_index = alt_tga / 'index.md'
        alt_index.write_text("alt index", encoding='utf-8')
        seeds = [str(ch_index), str(ch_task)]
        expected = {str(ch_index), str(ch_task), str(alt_index)}
    elif scenario == TEST_SCENARIO_DUPLICATE:
        ch_file = ch_dir / 'test.md'
        alt_file = alt_dir / 'test.md'
        ch_file.write_text("ch", encoding='utf-8')
        alt_file.write_text("alt", encoding='utf-8')
        seeds = [str(ch_file)]
        expected = {str(ch_file), str(alt_file)}
    elif scenario == TEST_SCENARIO_MISSING:
        ch_file = ch_dir / 'test.md'
        ch_file.write_text("ch", encoding='utf-8')
        seeds = [str(ch_file)]
        expected = {str(ch_file)}
    else:
        raise ValueError(f"unknown scenario {scenario}")
    return str(ch_dir), str(alt_dir), seeds, expected


@pytest.mark.parametrize("scenario", [TEST_SCENARIO_COURSE, TEST_SCENARIO_DUPLICATE, TEST_SCENARIO_MISSING])
def test_add_altdir_files(tmp_path, scenario):
    """Verify add_altdir_files adds, deduplicates, or skips files per scenario."""
    ch_dir, alt_dir, seeds, expected = prepare_altdir_scenario(tmp_path, scenario)
    all_files = maintainer.add_altdir_files(seeds, ch_dir, alt_dir)
    assert set(all_files) == expected, f"Scenario '{scenario}': expected {expected}, got {set(all_files)}"


def test_error_categorization_prefers_status_code():
    """Status codes should override textual hints when categorizing errors."""
    reporter = linkchecker.LinkCheckReporter()
    link = linkchecker.ExternalLink(
        url="https://example.com",
        text="Example",
        source_file="file.md",
        line_number=1
    )
    result = linkchecker.LinkCheckResult(
        link=link,
        success=False,
        status_code=404,
        error_message="Request timed out with status 404"
    )
    assert reporter._categorize_error(result) == "404"
    timeout_result = linkchecker.LinkCheckResult(
        link=link,
        success=False,
        status_code=None,
        error_message="connection timeout reached"
    )
    assert reporter._categorize_error(timeout_result) == "timeout"


def test_failed_links_sorted_by_url_in_report():
    """Reports should tally domains and sort failed links by URL."""
    reporter = linkchecker.LinkCheckReporter()
    link_fail_b = linkchecker.ExternalLink(
        url="https://example.com/zeta",
        text="Zeta",
        source_file="b.md",
        line_number=5
    )
    link_fail_a = linkchecker.ExternalLink(
        url="https://example.com/alpha",
        text="Alpha",
        source_file="a.md",
        line_number=3
    )
    link_fail_other = linkchecker.ExternalLink(
        url="https://another.org/resource",
        text="Other",
        source_file="c.md",
        line_number=2
    )
    link_pass = linkchecker.ExternalLink(
        url="https://example.com/ok",
        text="Ok",
        source_file="d.md",
        line_number=9
    )
    results = [
        linkchecker.LinkCheckResult(link=link_fail_b, success=False, status_code=500, error_message="HTTP 500"),
        linkchecker.LinkCheckResult(link=link_fail_a, success=False, status_code=404, error_message="HTTP 404"),
        linkchecker.LinkCheckResult(link=link_fail_other, success=False, status_code=502, error_message="HTTP 502"),
        linkchecker.LinkCheckResult(link=link_pass, success=True, status_code=200),
    ]
    markdown = reporter.render_markdown_report(results, max_workers=5)
    # Verify the Top Domains table reflects failed link counts.
    assert "| Domain | Links | #Failed Links |" in markdown
    assert "| `example.com` | 3 | 2 |" in markdown
    assert "| `another.org` | 1 | 1 |" in markdown
    # Extract failed link rows and ensure they are ordered by URL.
    failed_section = markdown.split("## Failed Links")[1]
    rows = [
        line for line in failed_section.splitlines()
        if line.startswith("|") and "http" in line
    ]
    urls = [row.split("|")[2].strip() for row in rows]
    assert urls == sorted(urls), "Failed links should be sorted alphabetically by URL"
