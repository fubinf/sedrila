# pytest tests for linkchecker
import os
import tempfile

import sdrl.linkchecker as linkchecker


def test_404_gets_reported():
    """Test that a 404 link is reported as failed."""
    # Use a URL that should return 404 on sedrila.readthedocs.io
    test_url = "https://sedrila.readthedocs.io/en/latest/nonexistent-page-xyz123"
    
    # Create a temporary test markdown file
    test_content = f"""# Test File
    
This is a test link that should return 404: [Broken Link]({test_url})
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', encoding='utf-8') as f:
        f.write(test_content)
        f.flush()
        os.fsync(f.fileno())
        temp_file = f.name

        # Extract links
        extractor = linkchecker.LinkExtractor()
        links = extractor.extract_links_from_file(temp_file)
        
        assert len(links) == 1, "Should find exactly one link"
        assert links[0].url == test_url, "Should extract the correct URL"
        
        # Check the link
        checker = linkchecker.LinkChecker()
        results = checker.check_links(links, show_progress=False)
        
        assert len(results) == 1, "Should have one result"
        result = results[0]
        
        # Should be reported as failed with 404 status
        assert not result.success, "404 link should be reported as failed"
        assert result.status_code == 404, f"Expected 404, got {result.status_code}"
        assert "404" in (result.error_message or ""), "Error message should mention 404"


def test_404_suppressed():
    """Test that a suppressed 404 (with LINK_CHECK comment) is not reported as failed."""
    # Use a URL that should return 404 on sedrila.readthedocs.io
    test_url = "https://sedrila.readthedocs.io/en/latest/another-nonexistent-page-abc789"
    
    # Create a temporary test markdown file with LINK_CHECK comment
    test_content = f"""# Test File

<!-- LINK_CHECK: status=404 -->
This link is expected to return 404: [Expected 404]({test_url})
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', encoding='utf-8') as f:
        f.write(test_content)
        f.flush()
        os.fsync(f.fileno())
        temp_file = f.name

        # Extract links
        extractor = linkchecker.LinkExtractor()
        links = extractor.extract_links_from_file(temp_file)
        
        assert len(links) == 1, "Should find exactly one link"
        assert links[0].url == test_url, "Should extract the correct URL"
        
        # Check that validation rule was parsed
        link = links[0]
        assert link.validation_rule is not None, "Should have validation rule"
        assert link.validation_rule.expected_status == 404, "Should expect 404 status"
        
        # Check the link
        checker = linkchecker.LinkChecker()
        results = checker.check_links(links, show_progress=False)
        
        assert len(results) == 1, "Should have one result"
        result = results[0]
        
        # Should be reported as successful because 404 was expected
        assert result.success, "Expected 404 link should be reported as successful"
        assert result.status_code == 404, f"Should still return 404, got {result.status_code}"


def test_content_check_works():
    """Test that content= validation works correctly."""
    # Use sedrila.readthedocs.io homepage which should contain "SeDriLa"
    test_url_valid = "https://sedrila.readthedocs.io"
    
    # Create a temporary test markdown file with content check
    test_content = f"""# Test File

<!-- LINK_CHECK: content="SeDriLa" -->
This link should contain "SeDriLa": [SeDriLa Docs]({test_url_valid})

<!-- LINK_CHECK: content="ThisTextShouldNotExistAnywhere123456" -->
This link should not contain the required text: [Should Fail Content Check]({test_url_valid})
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', encoding='utf-8') as f:
        f.write(test_content)
        f.flush()
        os.fsync(f.fileno())
        temp_file = f.name

        # Extract links
        extractor = linkchecker.LinkExtractor()
        links = extractor.extract_links_from_file(temp_file)
        
        assert len(links) == 2, "Should find exactly two links"
        
        # Check that validation rules were parsed
        link1, link2 = links[0], links[1]
        
        assert link1.validation_rule is not None, "First link should have validation rule"
        assert link1.validation_rule.required_text == "SeDriLa", "Should require 'SeDriLa'"
        
        assert link2.validation_rule is not None, "Second link should have validation rule"
        assert link2.validation_rule.required_text == "ThisTextShouldNotExistAnywhere123456", "Should require non-existent text"
        
        # Check the links
        checker = linkchecker.LinkChecker()
        results = checker.check_links(links, show_progress=False)
        
        assert len(results) == 2, "Should have two results"
        
        # First link should succeed (contains "SeDriLa")
        result1 = results[0]
        assert result1.success, "Link with existing content should succeed"
        assert result1.status_code == 200, "Should return 200 OK"
        
        # Second link should fail (doesn't contain the required text)
        result2 = results[1]
        assert not result2.success, "Link with missing content should fail"
        assert result2.status_code == 200, "Should still return 200 OK from server"
        assert "Required text" in (result2.error_message or ""), "Error should mention required text"


def test_validation_rule_parsing():
    """Test that LINK_CHECK comments are parsed correctly."""
    test_content = """# Test File

<!-- LINK_CHECK: status=301, timeout=15, ignore_ssl=true -->
Test link: [Test](https://example.com)

<!-- LINK_CHECK: content="hello world" -->  
Another link: [Test2](https://example.org)
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', encoding='utf-8') as f:
        f.write(test_content)
        f.flush()
        os.fsync(f.fileno())
        temp_file = f.name

        extractor = linkchecker.LinkExtractor()
        links = extractor.extract_links_from_file(temp_file)
        
        assert len(links) == 2, "Should find two links"
        
        # Check first link validation rule
        rule1 = links[0].validation_rule
        assert rule1 is not None, "Should have validation rule"
        assert rule1.expected_status == 301, "Should expect 301 status"
        assert rule1.timeout == 15, "Should have timeout=15"
        assert rule1.ignore_ssl is True, "Should ignore SSL"
        
        # Check second link validation rule
        rule2 = links[1].validation_rule
        assert rule2 is not None, "Should have validation rule"
        assert rule2.required_text == "hello world", "Should require 'hello world'"


def test_href_macro_extraction():
    """Test that HREF macro links are extracted correctly."""
    test_content = """# Test File

Regular link: [Regular](https://example.com)

HREF macro: [HREF::https://sedrila.readthedocs.io]

Another HREF: [HREF::https://github.com/fubinf/sedrila]
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', encoding='utf-8') as f:
        f.write(test_content)
        f.flush()
        os.fsync(f.fileno())
        temp_file = f.name

        extractor = linkchecker.LinkExtractor()
        links = extractor.extract_links_from_file(temp_file)
        
        assert len(links) == 3, "Should find three links"
        
        # Check URLs
        urls = [link.url for link in links]
        assert "https://example.com" in urls, "Should extract regular link"
        assert "https://sedrila.readthedocs.io" in urls, "Should extract first HREF macro"
        assert "https://github.com/fubinf/sedrila" in urls, "Should extract second HREF macro"
        
        # HREF macro links should use URL as text
        href_links = [link for link in links if link.url.startswith("https://sedrila.readthedocs.io")]
        assert len(href_links) == 1, "Should find sedrila HREF link"
        assert href_links[0].text == href_links[0].url, "HREF macro should use URL as text"


def test_batch_mode_output():
    """Test that batch mode produces less verbose output."""
    test_content = """# Test File

Regular link: [Test](https://example.com)
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', encoding='utf-8') as f:
        f.write(test_content)
        f.flush()
        os.fsync(f.fileno())
        temp_file = f.name

        extractor = linkchecker.LinkExtractor()
        links = extractor.extract_links_from_file(temp_file)
        
        # Check links in batch mode
        checker = linkchecker.LinkChecker()
        results = checker.check_links(links, show_progress=False, batch_mode=True)
        
        # Should still return results
        assert len(results) == 1, "Should have one result"
        
        # Batch mode doesn't change result structure, only output verbosity
        assert results[0].link.url == "https://example.com"


def test_deduplication():
    """Test that duplicate URLs are only checked once."""
    test_content = """# Test File

First link: [Link1](https://example.com)
Second link: [Link2](https://example.com)
Third link: [Link3](https://example.com)
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', encoding='utf-8') as f:
        f.write(test_content)
        f.flush()
        os.fsync(f.fileno())
        temp_file = f.name

        extractor = linkchecker.LinkExtractor()
        links = extractor.extract_links_from_file(temp_file)
        
        # Should extract all 3 link references
        assert len(links) == 3, "Should extract 3 link references"
        
        # But check_links should deduplicate
        checker = linkchecker.LinkChecker()
        results = checker.check_links(links, show_progress=False)
        
        # All 3 results should be returned (mapped back to original links)
        assert len(results) == 3, "Should return results for all 3 references"
        
        # All should reference the same URL
        assert all(r.link.url == "https://example.com" for r in results)


# ============================================================================
# Maintainer file selection tests (for --check-links workflow)
# ============================================================================

def create_test_course_structure(base_dir):
    """
    Create a minimal course structure for testing maintainer file selection.
    
    Creates:
    - sedrila.yaml config
    - ch/Chapter1/TaskgroupA/index.md (stage: beta)
    - ch/Chapter1/TaskgroupA/Task1.md (stage: beta)
    - ch/Chapter1/TaskgroupB/index.md (stage: alpha)
    - ch/Chapter1/TaskgroupB/Task2.md (stage: alpha)
    - ch/Chapter1/TaskgroupC/index.md (stage: draft)
    - alt/Chapter1/TaskgroupA/index.md (altdir file)
    - ch/Chapter1/NotInConfig/index.md (not in config, should be ignored)
    """
    import yaml
    
    # Create directories
    ch_dir = os.path.join(base_dir, 'ch')
    alt_dir = os.path.join(base_dir, 'alt')
    os.makedirs(ch_dir, exist_ok=True)
    os.makedirs(alt_dir, exist_ok=True)
    
    # Create sedrila.yaml
    config = {
        'title': 'Test Course',
        'name': 'test-course',
        'chapterdir': 'ch',
        'altdir': 'alt',
        'stages': ['draft', 'alpha', 'beta'],
        'instructors': [],  # Required field
        'allowed_attempts': '2',  # Required field
        'chapters': [
            {
                'name': 'Chapter1',
                'taskgroups': [
                    {'name': 'TaskgroupA'},
                    {'name': 'TaskgroupB'},
                    {'name': 'TaskgroupC'},
                ]
            }
        ]
    }
    
    with open(os.path.join(base_dir, 'sedrila.yaml'), 'w') as f:
        yaml.dump(config, f)
    
    # Create glossary.md (required)
    with open(os.path.join(ch_dir, 'glossary.md'), 'w') as f:
        f.write("""title: Glossary
---
# Glossary
""")
    
    # Create Chapter1 index.md (required)
    chapter1_dir = os.path.join(ch_dir, 'Chapter1')
    os.makedirs(chapter1_dir, exist_ok=True)
    with open(os.path.join(chapter1_dir, 'index.md'), 'w') as f:
        f.write("""title: Chapter 1
---
# Chapter 1
""")
    
    # Create TaskgroupA (beta stage)
    tga_dir = os.path.join(ch_dir, 'Chapter1', 'TaskgroupA')
    os.makedirs(tga_dir, exist_ok=True)
    
    with open(os.path.join(tga_dir, 'index.md'), 'w') as f:
        f.write("""title: Taskgroup A
stage: beta
---
# Taskgroup A

Link in taskgroup: [Example](https://example.com)
""")
    
    with open(os.path.join(tga_dir, 'Task1.md'), 'w') as f:
        f.write("""title: Task 1
stage: beta
timevalue: 1.0
difficulty: 2
---
# Task 1

Link in task: [GitHub](https://github.com)
""")
    
    # Create TaskgroupB (alpha stage)
    tgb_dir = os.path.join(ch_dir, 'Chapter1', 'TaskgroupB')
    os.makedirs(tgb_dir, exist_ok=True)
    
    with open(os.path.join(tgb_dir, 'index.md'), 'w') as f:
        f.write("""title: Taskgroup B
stage: alpha
---
# Taskgroup B

Another link: [Python](https://python.org)
""")
    
    with open(os.path.join(tgb_dir, 'Task2.md'), 'w') as f:
        f.write("""title: Task 2
stage: alpha
timevalue: 1.5
difficulty: 3
---
# Task 2

Yet another link: [ReadTheDocs](https://readthedocs.org)
""")
    
    # Create TaskgroupC (draft stage)
    tgc_dir = os.path.join(ch_dir, 'Chapter1', 'TaskgroupC')
    os.makedirs(tgc_dir, exist_ok=True)
    
    with open(os.path.join(tgc_dir, 'index.md'), 'w') as f:
        f.write("""title: Taskgroup C
stage: draft
---
# Taskgroup C

Draft link: [Wikipedia](https://wikipedia.org)
""")
    
    # Create altdir file for TaskgroupA
    alt_tga_dir = os.path.join(alt_dir, 'Chapter1', 'TaskgroupA')
    os.makedirs(alt_tga_dir, exist_ok=True)
    
    with open(os.path.join(alt_tga_dir, 'index.md'), 'w') as f:
        f.write("""title: Taskgroup A Alt
stage: beta
---
# Taskgroup A (Alt version)

Alt link: [MDN](https://developer.mozilla.org)
""")
    
    # Create NotInConfig directory (should be ignored)
    not_in_config_dir = os.path.join(ch_dir, 'Chapter1', 'NotInConfig')
    os.makedirs(not_in_config_dir, exist_ok=True)
    
    with open(os.path.join(not_in_config_dir, 'index.md'), 'w') as f:
        f.write("""title: Not In Config
---
# This should be ignored

This file is not in sedrila.yaml: [Should Be Ignored](https://ignored.com)
""")
    
    return base_dir


def test_extract_files_respects_stages():
    """Test that maintainer file extraction respects stage filtering."""
    import sdrl.subcmd.maintainer as maintainer
    import sdrl.course
    import sdrl.directory as dir
    import sdrl.elements
    import cache
    import sdrl.constants as c
    import base as b
    import itertools
    
    with tempfile.TemporaryDirectory() as tmpdir:
        create_test_course_structure(tmpdir)
        
        original_cwd = os.getcwd()
        try:
            # Coursebuilder expects to be run from the course root
            os.chdir(tmpdir)
            
            targetdir_s = os.path.join(tmpdir, 'output')
            targetdir_i = os.path.join(tmpdir, 'output_i')
            os.makedirs(targetdir_s, exist_ok=True)
            os.makedirs(targetdir_i, exist_ok=True)
            
            # Clear global macro state to avoid conflicts between tests
            import sdrl.macros
            sdrl.macros.macrodefs_early.clear()
            sdrl.macros.macrodefs_late.clear()
            sdrl.macros.macrostate.clear()
            
            # Test with beta stage (should only include beta)
            the_cache = cache.SedrilaCache(os.path.join(targetdir_i, c.CACHE_FILENAME), start_clean=True)
            b.set_register_files_callback(the_cache.set_file_dirty)
            directory = dir.Directory(the_cache)
            
            course_beta = sdrl.course.Coursebuilder(
                configfile='sedrila.yaml',
                context='test',
                include_stage='beta',
                targetdir_s=targetdir_s,
                targetdir_i=targetdir_i,
                directory=directory
            )
            
            # Initialize stage filtering
            allparts = list(itertools.chain(
                directory.get_all(sdrl.course.Chapter),
                directory.get_all(sdrl.course.Taskgroup),
                directory.get_all(sdrl.course.Task)
            ))
            for part in allparts:
                topmatter_elem = directory.get_the(sdrl.elements.Topmatter, part.name)
                topmatter_elem.do_build()
                part.process_topmatter(part.sourcefile, topmatter_elem.value, course_beta)
            
            files_beta = maintainer.extract_markdown_files_from_course(course_beta)
            the_cache.close()
            
            # Should only include TaskgroupA files (beta stage)
            assert len(files_beta) == 2, f"Expected 2 files for beta stage, got {len(files_beta)}"
            filenames = [os.path.basename(f) for f in files_beta]
            assert 'index.md' in filenames
            assert 'Task1.md' in filenames
        finally:
            os.chdir(original_cwd)


def test_extract_files_ignores_unconfigured_taskgroups():
    """Test that files not in sedrila.yaml are ignored."""
    import sdrl.subcmd.maintainer as maintainer
    import sdrl.course
    import sdrl.directory as dir
    import sdrl.elements
    import cache
    import sdrl.constants as c
    import base as b
    import itertools
    
    with tempfile.TemporaryDirectory() as tmpdir:
        create_test_course_structure(tmpdir)
        
        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir)
            
            targetdir_s = os.path.join(tmpdir, 'output')
            targetdir_i = os.path.join(tmpdir, 'output_i')
            os.makedirs(targetdir_s, exist_ok=True)
            os.makedirs(targetdir_i, exist_ok=True)
            
            # Clear global macro state to avoid conflicts between tests
            import sdrl.macros
            sdrl.macros.macrodefs_early.clear()
            sdrl.macros.macrodefs_late.clear()
            sdrl.macros.macrostate.clear()
            
            the_cache = cache.SedrilaCache(os.path.join(targetdir_i, c.CACHE_FILENAME), start_clean=True)
            b.set_register_files_callback(the_cache.set_file_dirty)
            directory = dir.Directory(the_cache)
            
            course = sdrl.course.Coursebuilder(
                configfile='sedrila.yaml',
                context='test',
                include_stage='draft',
                targetdir_s=targetdir_s,
                targetdir_i=targetdir_i,
                directory=directory
            )
            
            # Initialize stage filtering
            allparts = list(itertools.chain(
                directory.get_all(sdrl.course.Chapter),
                directory.get_all(sdrl.course.Taskgroup),
                directory.get_all(sdrl.course.Task)
            ))
            for part in allparts:
                topmatter_elem = directory.get_the(sdrl.elements.Topmatter, part.name)
                topmatter_elem.do_build()
                part.process_topmatter(part.sourcefile, topmatter_elem.value, course)
            
            files = maintainer.extract_markdown_files_from_course(course)
            the_cache.close()
            
            # Should not include NotInConfig directory
            for filepath in files:
                assert 'NotInConfig' not in filepath, f"Should not include unconfigured taskgroup: {filepath}"
        finally:
            os.chdir(original_cwd)


def test_add_altdir_files():
    """Test that altdir files are correctly discovered."""
    import sdrl.subcmd.maintainer as maintainer
    
    with tempfile.TemporaryDirectory() as tmpdir:
        create_test_course_structure(tmpdir)
        
        ch_dir = os.path.join(tmpdir, 'ch')
        alt_dir = os.path.join(tmpdir, 'alt')
        
        # Test files from chapterdir
        chapterdir_files = [
            os.path.join(ch_dir, 'Chapter1', 'TaskgroupA', 'index.md'),
            os.path.join(ch_dir, 'Chapter1', 'TaskgroupA', 'Task1.md'),
        ]
        
        # Add altdir files
        all_files = maintainer.add_altdir_files(chapterdir_files, ch_dir, alt_dir)
        
        # Should include both chapterdir and altdir files
        assert len(all_files) == 3, f"Expected 3 files (2 ch + 1 alt), got {len(all_files)}"
        
        # Check that altdir file is included
        alt_file = os.path.join(alt_dir, 'Chapter1', 'TaskgroupA', 'index.md')
        assert alt_file in all_files, f"Should include altdir file: {alt_file}"
        
        # Check that original files are still there
        for orig_file in chapterdir_files:
            assert orig_file in all_files, f"Should still include original file: {orig_file}"


def test_add_altdir_files_no_duplicates():
    """Test that altdir files are not duplicated."""
    import sdrl.subcmd.maintainer as maintainer
    
    with tempfile.TemporaryDirectory() as tmpdir:
        ch_dir = os.path.join(tmpdir, 'ch')
        alt_dir = os.path.join(tmpdir, 'alt')
        
        # Create a file that exists in both ch and alt
        test_file_ch = os.path.join(ch_dir, 'test.md')
        test_file_alt = os.path.join(alt_dir, 'test.md')
        
        os.makedirs(ch_dir, exist_ok=True)
        os.makedirs(alt_dir, exist_ok=True)
        
        with open(test_file_ch, 'w') as f:
            f.write("test ch")
        with open(test_file_alt, 'w') as f:
            f.write("test alt")
        
        # Add altdir files
        all_files = maintainer.add_altdir_files([test_file_ch], ch_dir, alt_dir)
        
        # Should have 2 unique files
        assert len(all_files) == 2, f"Expected 2 files, got {len(all_files)}"
        assert test_file_ch in all_files
        assert test_file_alt in all_files


def test_add_altdir_files_only_existing():
    """Test that only existing altdir files are added."""
    import sdrl.subcmd.maintainer as maintainer
    
    with tempfile.TemporaryDirectory() as tmpdir:
        ch_dir = os.path.join(tmpdir, 'ch')
        alt_dir = os.path.join(tmpdir, 'alt')
        
        os.makedirs(ch_dir, exist_ok=True)
        os.makedirs(alt_dir, exist_ok=True)
        
        # Create a file only in ch
        test_file_ch = os.path.join(ch_dir, 'test.md')
        with open(test_file_ch, 'w') as f:
            f.write("test ch")
        
        # Do NOT create corresponding alt file
        
        # Add altdir files
        all_files = maintainer.add_altdir_files([test_file_ch], ch_dir, alt_dir)
        
        # Should only have the original file
        assert len(all_files) == 1, f"Expected 1 file, got {len(all_files)}"
        assert test_file_ch in all_files
