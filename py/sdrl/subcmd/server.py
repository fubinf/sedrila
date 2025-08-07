"""
A trivial, development-only, non-robust, barely protected webserver for 
serving a file tree created by 'sedrila author'.
"""

import http.server
import os
import sys

import argparse_subcommand as ap_sub

meaning = """Development-only single-user webserver for serving a file tree created by 'sedrila author'."""

LOCALHOST_ONLY = '127.0.0.1'  # do not respond to requests directed to globally-visible addresses 


def add_arguments(subparser: ap_sub.ArgumentParser):
    subparser.add_argument('--quiet', '-q', action='store_true',
                           help="suppress the request logging output")
    subparser.add_argument('port', type=int,
                           help="port on which to serve the files")
    subparser.add_argument('sourcedir',
                           help="directory tree of files to be served")


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        """suppress the annoying 'broken pipe' error msgs often created by http.server"""
        try:
            super().do_GET()
        except (BrokenPipeError, ConnectionResetError):
            pass  # Ignore client disconnects


def execute(pargs: ap_sub.Namespace):
    os.chdir(pargs.sourcedir)  # change into the file tree to be served
    if pargs.quiet:
        sys.stderr = open(os.devnull, 'w')  # suppress request logging
    server = http.server.ThreadingHTTPServer((LOCALHOST_ONLY, pargs.port), QuietHandler)
    server.serve_forever()  # serve until stopped with Ctrl-C
