import os
import shutil

class Environment():
    def __init__(self, content_dir, out_dir, toc_depth = 3, *args, **kwargs):
        self.content_dir, self.out_dir, self.toc_depth = content_dir, out_dir, toc_depth

    def setUp(self, clean = False, create = True):
        if clean and os.path.isdir(self.out_dir):
            shutil.rmtree(self.out_dir)
        if create and not os.path.isdir(self.out_dir):
            try:
                os.makedirs(self.out_dir)
            except Exception:
                exit("Error creating output directory {}, maybe there is already a file with that name".format(self.out_dir))

    def tearDown(self):
        self.setUp(True, False)

    def run(self):
        if not os.path.isdir(self.content_dir):
            exit("No source directory found at {}".format(self.content_dir))
        import src.Markdown
        ext = src.Markdown.Markdown(self.content_dir, self.out_dir, self.toc_depth)
        for root, subdirs, files in os.walk(self.content_dir):
            subdirs.sort()
            if "/." in root:
                continue
            subdirs = list(filter(lambda d: not(d.startswith(".")), subdirs))
            ext.process(root, subdirs, files)
        ext.finish()
