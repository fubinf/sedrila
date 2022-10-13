import unittest
import os
import re
import xml.etree.ElementTree as etree
import src.Environment

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.environment = src.Environment.Environment("test", "test_out")
        cls.environment.setUp(True)
        cls.environment.run()
        cls.readcache = {}

    @classmethod
    def tearDownClass(cls):
        cls.environment.tearDown()

    def execute():
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(Tests)
        unittest.TextTestRunner().run(suite)

    def test_header_footer(self):
        content = self.environment.content("index.html")
        self.assertTrue(content.startswith(self.environment.content("src/header.html", True, "")))
        self.assertTrue(content.endswith(self.environment.content("src/footer.html", True, "")))

    def test_skip(self):
        self.assertFalse(os.path.isdir(self.environment.out_path(".hidden")))
        self.assertFalse(os.path.isfile(self.environment.out_path("resources.html")))
        self.assertFalse(os.path.isdir(self.environment.out_path("inline")))

    def test_resources(self):
        footer = self.environment.content("src/footer.html", True, "")
        content = self.environment.content("index.html").removesuffix(footer)
        #links should be present and wrapped in some way!
        resource_regex = r'(?:<(\S+)(?:\s[^>]+)?>\s*<a href="https://example.org/(\d+)">Link \2</a>\s*</\1>\s*){2}$'
        self.assertIsNotNone(re.search(resource_regex, content))

    def test_inlining(self):
        header = self.environment.content("src/header.html", True, "")
        content = self.environment.content("inline.html")[len(header):]
        #direct inline
        self.assertIn("inlined index", content)
        #overview
        overview_regex = r'<div class="overview"><a href="inline/index.html">Inline Title</a>(.*)inlined overview(.*)</div>'
        self.assertIsNotNone(re.search(overview_regex, content, re.DOTALL))

    def test_toc(self):
        header = self.environment.content("src/header.html", True, "")
        footer = self.environment.content("src/footer.html", True, "")
        content = self.environment.content("toc.html").removesuffix(footer)[len(header):]
        #we could compare strings directly, but results might differ in indentation or similar
        generated = etree.fromstring(content)
        expected = etree.fromstring(self.environment.content("toc_result.html"))
        self.assertEqual(etree.tostring(expected), etree.tostring(generated))
