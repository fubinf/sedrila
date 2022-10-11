#!/usr/bin/env python

import os
import shutil

content_dir = "../propra-inf"
out_dir = "out"
toc_depth = 3

def ensure_environment(clean = False):
    if clean and os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    if not os.path.isdir(out_dir):
        try:
            os.makedirs(out_dir)
        except Exception:
            exit("Error creating output directory {}, maybe there is already a file with that name".format(out_dir))

if __name__ == "__main__":
    import sys
    from src.Markdown import Markdown
    clean = len(sys.argv) > 1 and sys.argv[1] == "clean"
    if not os.path.isdir(content_dir):
        exit("No source directory found at {}".format(content_dir))
    ensure_environment(clean)
    ext = Markdown(content_dir, out_dir, toc_depth)
    for root, subdirs, files in os.walk(content_dir):
        subdirs.sort()
        print(subdirs)
        if "/." in root:
            continue
        subdirs = list(filter(lambda d: not(d.startswith(".")), subdirs))
        ext.process(root, subdirs, files)
    ext.finish()
