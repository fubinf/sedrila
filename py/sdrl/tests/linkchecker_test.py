# pytest tests for linkchecker
import tempfile
import os.path

import sdrl.linkchecker as linkchecker


def test_404_gets_reported():
    """Test that a 404 link is reported as failed."""
    # Use a URL that should return 404 on sedrila.readthedocs.io
    test_url = "https://sedrila.readthedocs.io/en/latest/nonexistent-page-xyz123"
    
    # Create a temporary test markdown file
    test_content = f"""# Test File
    
This is a test link that should return 404: [Broken Link]({test_url})
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
        f.write(test_content)
        temp_file = f.name
    
    try:
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
        
    finally:
        # Cleanup
        try:
            os.unlink(temp_file)
        except:
            pass


def test_404_suppressed():
    """Test that a suppressed 404 (with LINK_CHECK comment) is not reported as failed."""
    # Use a URL that should return 404 on sedrila.readthedocs.io
    test_url = "https://sedrila.readthedocs.io/en/latest/another-nonexistent-page-abc789"
    
    # Create a temporary test markdown file with LINK_CHECK comment
    test_content = f"""# Test File

<!-- LINK_CHECK: status=404 -->
This link is expected to return 404: [Expected 404]({test_url})
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
        f.write(test_content)
        temp_file = f.name
    
    try:
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
        
    finally:
        # Cleanup
        try:
            os.unlink(temp_file)
        except:
            pass


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
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
        f.write(test_content)
        temp_file = f.name
    
    try:
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
        
    finally:
        # Cleanup
        try:
            os.unlink(temp_file)
        except:
            pass


def test_validation_rule_parsing():
    """Test that LINK_CHECK comments are parsed correctly."""
    test_content = """# Test File

<!-- LINK_CHECK: status=301, timeout=15, ignore_ssl=true -->
Test link: [Test](https://example.com)

<!-- LINK_CHECK: content="hello world" -->  
Another link: [Test2](https://example.org)
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
        f.write(test_content)
        temp_file = f.name
    
    try:
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
        
    finally:
        # Cleanup
        try:
            os.unlink(temp_file)
        except:
            pass


def test_href_macro_extraction():
    """Test that HREF macro links are extracted correctly."""
    test_content = """# Test File

Regular link: [Regular](https://example.com)

HREF macro: [HREF::https://sedrila.readthedocs.io]

Another HREF: [HREF::https://github.com/fubinf/sedrila]
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
        f.write(test_content)
        temp_file = f.name
    
    try:
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
        
    finally:
        # Cleanup
        try:
            os.unlink(temp_file)
        except:
            pass
