#!/usr/bin/env python

import os

content_dir = "../propra-inf"
out_dir = "out"

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "test":
        import src.Tests
        src.Tests.Tests.execute()
        exit()

    import src.Environment
    clean = len(sys.argv) > 1 and sys.argv[1] == "clean"
    environment = src.Environment.Environment(content_dir, out_dir)
    environment.setUp(clean)
    environment.run()
