"""Implementation of the 'viewer' subcommand: a student directory and submission web server.
viewer TODO 2 list:
- --css cssfile option
- create service for persistently managing marks in submission.yaml
- reflect submission git history in that service (as 'instructor' already does)
- persist submission git history (key: id of last commit) for rapid startup
- add accept/reject logic to viewer 
"""
import base64
import os
import subprocess

import argparse_subcommand as ap_sub
import bottle  # https://bottlepy.org/docs/dev/

import base as b
import sdrl.argparser
import sdrl.constants as c
import sdrl.course
import sdrl.macros as macros
import sdrl.macroexpanders as macroexpanders
import sdrl.markdown as md
import sdrl.participant

meaning = """Specialized webserver for locally viewing contents of one or more student repo work directories."""
CSS = "class='viewer'"  # to be included in HTML tags
DEBUG = False  # TODO 1: turn off debug for release
DEFAULT_PORT = '8077'
FAVICON_URL = "/favicon-32x32.png"
VIEWER_CSS_URL = "/viewer.css"
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
    if pargs.instructor:
        context = sdrl.participant.make_context(pargs, pargs.workdir, sdrl.participant.Student, 
                                                with_submission=True, show_size=True, is_instructor=True)
    else:
        context = sdrl.participant.make_context(pargs, pargs.workdir, sdrl.participant.StudentS, 
                                                with_submission=False, show_size=False, is_instructor=False)
    run_viewer(context)


def run_viewer(ctx: sdrl.participant.Context):
    b.set_register_files_callback(lambda s: None)  # in case student .md files contain weird macro calls
    macroexpanders.register_macros(ctx.course)  # noqa
    port = getattr(ctx.pargs, 'port', DEFAULT_PORT)
    b.info(f"Webserver starts. Visit 'http://localhost:{port}/'. Terminate with Ctrl-C.")
    bottle.run(host='localhost', port=port, debug=DEBUG, reloader=False)


basepage_html = """<!DOCTYPE html>
<html>
 <head>
  <title>{title}</title>
  <meta charset="utf-8">
  {csslinks}
 </head>
 <body class='viewer'>
  {body}
 </body>
</html>
"""


viewer_css = """
h1.viewer, h2.viewer, h3.viewer {
  font-family: sans-serif;
  width: 100%;
  background-color: var(--main-color);
  padding: 0.5ex 1em;
  border-radius: 0.5ex;
  box-sizing: border-box;
}

td.viewer {
  padding: 0.3ex 1em;
}

tr.even {}

tr.odd {
    background-color: #ddd;
}
"""


@bottle.route("/")
def serve_root():
    body = "%s\n\n%s\n\n%s" % (
        html_for_submissionrelated_files(),
        html_for_remaining_submissions(),
        html_for_directorylist("/", breadcrumb=False),
    )
    pagetext = basepage_html.format(
        title=f"viewer",
        csslinks=html_for_csslinks(get_context().course_url),
        body=body
    )
    return pagetext


@bottle.route(FAVICON_URL)
def serve_favicon():
    bottle.response.content_type = 'img/png'
    return favicon32x32_png


@bottle.route(VIEWER_CSS_URL)
def serve_css():
    bottle.response.content_type = 'text/css'
    return viewer_css


@bottle.route("<mypath:path>/")
def serve_directory(mypath: str):
    pagetext = basepage_html.format(
        title=f"viewer",
        csslinks=html_for_csslinks(get_context().course_url),
        body=html_for_directorylist(f"{mypath}/")
    )
    return pagetext


@bottle.route("<mypath:path>")
def serve_vfile(mypath: str):
    if bottle.request.query.raw:  # ...?raw=workdirname
        return handle_rawfile(mypath, bottle.request.query.raw)
    body = html_for_file(f"{mypath}")
    pagetext = basepage_html.format(
        title=f"viewer",
        csslinks=html_for_csslinks(get_context().course_url),
        body=body
    )
    return pagetext


def handle_rawfile(mypath: str, workdir: str):
    wd = get_context().students[workdir]
    return bottle.static_file(wd.path_actualpath(mypath), root='.')


def html_for_breadcrumb(path: str) -> str:
    parts = [f"<nav {CSS}><a href='/'>viewer</a>:"]
    slashpos = path.find("/", 0)
    assert slashpos == 0
    nextslashpos = path.find("/", slashpos+1)
    # ----- process path elements between slashes:
    while nextslashpos > 0:
        parts.append(f" / <a href='{path[:nextslashpos+1]}'>{path[slashpos+1:nextslashpos]}</a>")
        slashpos = nextslashpos
        nextslashpos = path.find("/", slashpos+1)
    # ----- process last path element:
    if slashpos + 1 == len(path):
        parts.append(" /")  # dir path
    else:
        parts.append(f" / <a href='{path}'>{path[slashpos+1:]}</a>")  # file path
    return f"{''.join(parts)}</nav>"


def html_for_csslinks(course_url: str) -> str:
    return (f'<link rel="icon" type="image/png" sizes="16x16 32x32" href="{FAVICON_URL}">\n'
            f'<link href="{course_url}/sedrila.css" rel="stylesheet">\n'
            f'<link href="{course_url}/local.css" rel="stylesheet">\n'
            f'<link href="{course_url}/codehilite.css" rel="stylesheet">\n'
            f'<link href="{VIEWER_CSS_URL}" rel="stylesheet">\n')


def html_for_directorylist(mypath, breadcrumb=True) -> str:
    """A page listing the directories and files under mypath in the virtual filesystem."""
    dirs, files = get_context().ls(mypath)
    lines = [html_for_breadcrumb(mypath) if breadcrumb else ""]  # noqa
    lines.append(f"<h1 {CSS}>Contents of '{mypath}'</h1>")
    lines.append(f"<h2 {CSS}>Subdirectories</h2>")
    lines.append(f"<table {CSS}>")
    for idx, mydir in enumerate(sorted(dirs)):
        lines.append(f"{tr_tag(idx)}"
                     f"<td {CSS}><a href='{mydir}'>{mydir}</a></td>"
                     f"<td {CSS}>{html_for_tasklink(mydir)}</td>"
                     f"</tr>")
    lines.append("</table>")
    lines.append(f"<h2 {CSS}>Files</h2>")
    lines.append(f"<table {CSS}>")
    for idx, file in enumerate(sorted(files)):
        filepath = os.path.join(mypath, file)
        lines.append(f"{tr_tag(idx)}"
                     f"<td {CSS}><a href='{filepath}'>{file}</a></td>"
                     f"{html_for_file_existence(filepath)}"
                     f"<td {CSS}>{html_for_tasklink(filepath)}</td>"
                     f"</tr>")
    lines.append("</table>")
    body = "\n".join(lines)
    return body


def html_for_file(mypath) -> str:
    """
    Page body showing each Workdir's version (if existing) of file mypath, and pairwise diffs where possible.
    We create this as a Markdown page, then render it.
    """
    SRC = 'src'
    BINARY = 'binary'
    MISSING = 'missing'
    binaryfile_suffixes = ('pdf', 'zip')  # TODO 2: what else?
    suffix2lang = dict(  # see https://pygments.org/languages/  TODO 2: always just use the suffix?
        c="c", cc="c++", cpp="c++", cs="csharp",
        go="golang",
        h="c++", html="html",
        java="java", js="javascript",
        py="python", 
        sh="shell", 
        txt="")
    filename = os.path.basename(mypath)
    frontname, suffix = os.path.splitext(filename)

    def append_one_file():
        content = b.slurp(f"{workdir.topdir}{mypath}")
        if suffix == '.md':
            lines.append(content)
        elif suffix == '.prot':
            lines.append(macroexpanders.prot_html(content))
        elif not suffix or suffix[1:] in binaryfile_suffixes:
            lines.append(f"<a href='?raw={workdir.topdir}'>{workdir.path_actualpath(mypath)}</a>")
            kinds.append(BINARY)
            return
        else:  # any other suffix: assume this is a sourcefile 
            language = suffix2lang.get(suffix[1:], "")
            if language == 'html':
                lines.append(f"<a href='?raw={workdir.topdir}'>view as HTML page</a>")
            lines.append(f"```{language}")
            lines.append(content.rstrip("\n"))
            lines.append(f"```")
        kinds.append(SRC)

    def append_diff():
        prevdir = get_context().studentlist[idx-1]  # previous workdir
        toc.append(f"<a href='#diff-{prevdir.topdir}-{workdir.topdir}'>diff</a>  ")
        lines.append(f"<h2 id='diff-{prevdir.topdir}-{workdir.topdir}' {CSS}"
                     f">{idx-1}/{idx}. diff {prevdir.topdir}/{workdir.topdir}</h2>")
        if kinds[-2:] != [SRC, SRC]:
            lines.append("No diff shown. It requires two source files, which we do not have here.")
            return
        diff_output = diff_files(prevdir.path_actualpath(mypath), workdir.path_actualpath(mypath))
        lines.append("\n```diff")
        lines.append(diff_output)
        lines.append("```")

    # ----- iterate through workdirs and prepare the sections:
    kinds = []  # which files are SRC, BINARY, or MISSING
    lines = []  # noqa, some entries will be entire file contents, not single lines
    toc = []
    for idx, workdir in enumerate(get_context().studentlist):
        toc.append(f"<a href='#{workdir.topdir}'>{idx}. {workdir.topdir}</a>  ")
        lines.append(f"<h2 id='{workdir.topdir}' {CSS}>{idx}. {workdir.topdir}: {filename}</h2>")
        if not workdir.path_exists(mypath):
            lines.append(f"(('{mypath}' does not exist in '{workdir.topdir}'))")
            kinds.append(MISSING)
        else:
            append_one_file()
        if idx % 2 == 1:
            append_diff()
    # ----- render:
    the_toc, the_lines = '\n'.join(toc), '\n'.join(lines)
    markdown = (f"{html_for_breadcrumb(mypath)}\n"
                f"<h1 {CSS}>{mypath}</h1>\n"
                f"{the_toc}\n"
                f"{the_lines}")
    macros.switch_part("viewer")
    mddict = md.render_markdown(mypath, filename, markdown, b.Mode.STUDENT, dict())
    return mddict['html']


def html_for_file_existence(mypath: str) -> str:
    """One or more table column entries with file existence markers for each file or file pair."""
    BEGIN = f'<td {CSS}>'
    END = '</td>'
    MISSING = '-- '
    entries = [BEGIN]
    for idx, wd in enumerate(get_context().studentlist):
        if wd.path_exists(mypath):
            entries.append(f"{str(idx)} ")
        else:
            entries.append(MISSING)
        if idx % 2 == 1:  # finish a pair
            if entries[-1] != MISSING and entries[-2] != MISSING:  # both files are present
                size_even, size_odd = prev_wd.path_actualsize(mypath), wd.path_actualsize(mypath)  # noqa
                if size_even > 1.5*size_odd:
                    sign = ">>"
                elif size_even > size_odd:
                    sign = ">"
                elif size_even == size_odd:
                    sign = "="
                elif 1.5 * size_even < size_odd:
                    sign = "<<"
                elif size_even < size_odd:
                    sign = "<"
                else:
                    assert False
                last = entries.pop()
                entries.append(f" {sign} ")
                entries.append(last)
            entries.append(END)
            entries.append(BEGIN)
        prev_wd = wd
    if entries[-1] == BEGIN:  # repair the end
        entries.pop()
    return ''.join(entries)


def html_for_remaining_submissions() -> str:
    def html_for_remainingness(subm: str) -> str:
        MISSING = '-- '
        parts = []
        for idx2, wd in enumerate(get_context().studentlist):
            parts.append(f"{str(idx2)} " if subm in wd.submissions_remaining else MISSING)    
        return ''.join(parts)

    lines = [f"<h1 {CSS}>Submissions not covered above</h1>", 
             f"<table {CSS}>"]
    for idx, submission in enumerate(sorted(get_context().submissions_remaining)):
        lines.append(f"{tr_tag(idx)}"
                     f"<td {CSS}>{submission}</td>"
                     f"<td {CSS}>{html_for_remainingness(submission)}</td>"
                     f"<td {CSS}>{html_for_tasklink(submission)}</td>"
                     f"</tr>")
    lines.append("</table>")
    return "\n".join(lines)


def html_for_submissionrelated_files() -> str:
    lines = [f"<h1 {CSS}>Files with submission-related names</h1>", 
             f"<table {CSS}>"]
    for idx, mypath in enumerate(sorted(get_context().submission_pathset)):
        lines.append(f"{tr_tag(idx)}"
                     f"<td {CSS}><a href='{mypath}'>{mypath}</a></td>"
                     f"{html_for_file_existence(mypath)}"
                     f"<td {CSS}>{html_for_tasklink(mypath)}</td>"
                     f"</tr>")
    lines.append("</table>")
    return "\n".join(lines)


def html_for_tasklink(str_with_taskname: str) -> str:
    context = get_context()
    mm = context.submission_re.search(str_with_taskname)
    instructorpart = "instructor/" if context.is_instructor else ""
    return f"<a href='{context.course_url}{instructorpart}{mm.group()}.html'>task</a>" if mm else ""


def tr_tag(idx: int) -> str:
    color = "even" if idx % 2 == 0 else "odd"
    return f"<tr class='viewer {color}'>"


def diff_files(path1: str, path2: str) -> str:
    cmd = f"/usr/bin/diff '{path1}' '{path2}'"
    result = subprocess.run(cmd, shell=True, text=True, capture_output=True, check=False)
    if result.returncode == 0:
        return "files are identical"
    elif result.returncode == 1:  # differences found
        return result.stdout
    else:  # there were execution problems
        return f"<p>('diff' exit status: {result.returncode}</p>\n{result.stderr}"
