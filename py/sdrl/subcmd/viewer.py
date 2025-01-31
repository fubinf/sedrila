"""Implementation of the 'viewer' subcommand: a student directory and submission web server.
viewer TODO 2 list:
- --css cssfile option
- create service for persistently managing marks in submission.yaml
- persist submission git history (key: id of last commit) for rapid startup?
- add accept/reject logic to viewer 
"""
import base64
import os
import subprocess
import typing as tg

import argparse_subcommand as ap_sub
import bottle  # https://bottlepy.org/docs/dev/

import base as b
import sdrl.constants as c
import sdrl.argparser
import sdrl.course
import sdrl.macros as macros
import sdrl.macroexpanders as macroexpanders
import sdrl.markdown as md
import sdrl.participant
import sdrl.webapp

meaning = """Specialized webserver for locally viewing contents of one or more student repo work directories."""
CSS = "class='viewer'"  # to be included in HTML tags
DEBUG = False  # TODO 1: turn off debug for release
DEFAULT_PORT = '8077'
FAVICON_URL = "/favicon-32x32.png"
VIEWER_CSS_URL = "/viewer.css"
VIEWER_JS_URL = "/script.js"
SEDRILA_REPLACE_URL = "/sedrila-replace.action"
favicon32x32_png_base64 = """iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAACqklEQVRYR+1Wv0t6cRQ9CiloQikk
RlpBU5BQDhlitTgouAoZDg0NmX9Is0MSQlMaItTSIIiDRBERgQ4OCuqgLUkikSD98Mu98Pp+Lc33
pOg7eEHkwefec965597Pk+3t7bXxiyEbEhgq8N8qMDMzA6PRiNfXV7y9vUEmk0Eul/M/xcXFBdrt
vwNkMBgwNzfHZymHgs7Tr1qtolQqdZ21nlMwMTEBvV4Pu90OjUbDyZVKBTc3NwxcKBQ6CIyPj4NI
jI2NcQ5FNptFsVjEw8MD7u/vpREQTi8vL2N9fZ0fCfTk5OTLrUGqeb1eNJtN7O/vv6vRK6nvHqC3
39nZYelbrRaCwSDL3CtWVlawurqKq6srpNPpviuuLwGqsLGxAZPJxMVisRjK5XLPwj6fj1txcHCA
RqPxPQTMZjOcTicXu729RTKZ7Fp4dHQUfr+fDRePx/uC0wFRCigUCgQCAYyMjODx8RGhUKjDgALS
0tISHA4HTk9Pkc/nv48AVXK73Zifn+eiR0dHPFofg1ql0+nYfF/55N88UQpQwuzsLDweD+fSKKZS
qQ58lUqF3d1dXF9fizKfkCyaAE0B9Zf63K0Ni4uLLH84HEa9Xhclv2gPCNXW1tZgtVq7toHkpzg+
PhYNLpmAVqvF9vb2pzao1WqW/+zsDLlc7ucIUOXNzU1MTU11tMFiscBms7H5Xl5efpbAwsICXC4X
g0QiEb4faPnc3d19MqYYJqJNKBSjXUByK5VKngZaTNSWw8ND1Go1MZgdZyQToGxyOy0dmoZMJoPp
6WlEo1HJ4JJNKCDQVb21tcWPz8/PSCQSks0neQ98fD3q++TkJJ6enng1Cx8hUmUYqAUEIlxQl5eX
OD8/l4r7fn5gAmRGuvvJiPTxMWgMTGBQwI95QwJDBX5dgT/hoVUQturVFQAAAABJRU5ErkJggg=="""
favicon32x32_png = base64.b64decode(favicon32x32_png_base64)
get_context = sdrl.participant.get_context  # abbreviation


def add_arguments(subparser: ap_sub.ArgumentParser):
    subparser.add_argument('--port', '-p', type=int, default=DEFAULT_PORT,
                           help=f"webserver will listen on this port (default: {DEFAULT_PORT})")
    subparser.add_argument('--instructor', '-i', action='store_true', default=False,
                           help="generate task links to the instructor versions (not the student versions)")
    subparser.add_argument('workdir', type=str, nargs='*',
                           help="short relative paths of student workdirs to be browsed")


def execute(pargs: ap_sub.Namespace):
    b.set_loglevel('INFO')
    pargs.workdir = [wd.rstrip('/') for wd in pargs.workdir]  # make names canonical
    if not pargs.workdir:
        pargs.workdir = ['.']
    context = sdrl.participant.make_context(pargs, pargs.workdir, sdrl.participant.Student, 
                                            with_submission=True, show_size=True, is_instructor=pargs.instructor)
    sdrl.webapp.run(context)


def run_viewer(ctx: sdrl.participant.Context):
    b.set_register_files_callback(lambda s: None)  # in case student .md files contain weird macro calls
    macroexpanders.register_macros(ctx.course)  # noqa
    port = getattr(ctx.pargs, 'port', DEFAULT_PORT)
    b.info(f"Webserver starts. Visit 'http://localhost:{port}/'. Terminate with Ctrl-C.")
    print("Huh?:", ctx.submission_tasknames, str(ctx.submission_re))
    bottle.run(host='localhost', port=port, debug=DEBUG, reloader=False)
