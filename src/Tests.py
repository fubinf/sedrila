import unittest
import os
import re
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

    def out_path(self, file):
        return os.path.join(self.environment.out_dir, file.replace("/", os.path.sep))

    def content(self, file, absolute = False, fallback = None):
        if not absolute:
            file = self.out_path(file)
        if file not in self.readcache:
            if os.path.isfile(file):
                with open(file, "r", encoding="utf8") as f:
                    self.readcache[file] = f.read()
            else:
                return fallback
        return self.readcache[file]

    def test_header_footer(self):
        content = self.content("index.html")
        self.assertTrue(content.startswith(self.content("src/header.html", True, "")))
        self.assertTrue(content.endswith(self.content("src/footer.html", True, "")))

    def test_skip(self):
        self.assertFalse(os.path.isdir(self.out_path(".hidden")))
        self.assertFalse(os.path.isfile(self.out_path("resources.html")))
        self.assertFalse(os.path.isdir(self.out_path("inline")))

    def test_resources(self):
        footer = self.content("src/footer.html", True, "")
        content = self.content("index.html").removesuffix(footer)
        #links should be present and wrapped in some way!
        resource_regex = r'(?:<(\S+)(?:\s[^>]+)?>\s*<a href="https://example.org/(\d+)">Link \2</a>\s*</\1>\s*){2}$'
        self.assertIsNotNone(re.search(resource_regex, content))

    def test_inlining(self):
        header = self.content("src/header.html", True, "")
        content = self.content("inline.html")[len(header):]
        #direct inline
        self.assertIn("inlined index", content)
        #overview
        overview_regex = r'<div class="overview"><a href="inline/index.html">Inline Title</a>(.*)inlined overview(.*)</div>'
        self.assertIsNotNone(re.search(overview_regex, content, re.DOTALL))
