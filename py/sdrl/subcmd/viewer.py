"""Implementation of the 'viewer' subcommand: a student directory and submission web server.
viewer TODO 1 list:
- check for unique course
- task links
- list of submissions with status
- mark submissions not represented in list of submission-related files
viewer TODO 2 list:
- --css cssfile option
- create service for persistently managing marks in submission.yaml
- reflect submission git history in that service (as 'instructor' already does)
- persist submission git history (key: id of last commit) for rapid startup
- add accept/reject logic to viewer 
"""
import base64
import functools
import itertools
import os
import pathlib
import re
import subprocess
import typing as tg

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
DEBUG = True  # TODO 1: turn off debug for release
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
context: 'Context'  # global data


def add_arguments(subparser: ap_sub.ArgumentParser):
    subparser.add_argument('--port', '-p', type=int, default=DEFAULT_PORT,
                           help=f"webserver will listen on this port (default: {DEFAULT_PORT})")
    subparser.add_argument('--instructor', '-i', action='store_true', default=False,
                           help="generate task links to the instructor versions (not the student versions)")
    subparser.add_argument('dir', type=str, nargs='+',
                           help="short relative path of student workdir to be browsed")


def execute(pargs: ap_sub.Namespace):
    b.set_loglevel('INFO')
    b.set_register_files_callback(lambda s: None)  # in case student .md files contain weird macro calls
    global context
    context = Context(pargs)
    # dump()
    # b.critical("STOP.")
    b.info(f"Webserver starts. Visit 'http://localhost:{pargs.port}/'. Terminate with Ctrl-C.")
    b.warning("Incomplete development version.")
    try:
        bottle.run(host='localhost', port=pargs.port, debug=DEBUG, reloader=DEBUG)
    except KeyboardInterrupt:
        print("  sedrila viewer terminated.")


def dump():
    global context
    for wd in context.workdirs:
        stud = wd.metadata
        b.info(f"\n===== {stud.root}: {stud.student_name}")
        print(f"--Paths:\t{list(wd.pathset)[:3]}...{list(wd.pathset)[-3:]} ({len(wd.pathset)} total)")
        print(f"--{c.SUBMISSION_FILE}:\t{wd.submission} ({len(wd.submission)} total)")
        print(f"--submission_re:\t{wd.submission_re}")
        print(f"--submission files:\t{list(wd.submission_pathset)[:3]}...{list(wd.submission_pathset)[-3:]} "
              f"({len(wd.submission_pathset)} total)")
    b.info(f"\n===== Context")
    print(sorted(context.submission_pathset))


class Workdir:
    """Represents and handles one student working directory. Its top is the root of the virtual file system."""
    topdir: str  # name of workdir as given on commandline

    def __init__(self, topdir: str):
        self.topdir = topdir = topdir.rstrip('/')  # avoid trouble with non-canonical names
        if not os.path.exists(topdir):
            b.critical(f"'{topdir}' does not exist.")
        elif not os.path.isdir(topdir):
            b.critical(f"'{topdir}' must be a directory.")
        b.info(f"'{self.topdir}':\t{len(self.pathset)} files\t{len(self.submission)} submissions")

    @functools.cached_property
    def pathset(self) -> set[str]:
        """file pathnames within topdir"""
        raw_pathlist = (str(p) for p in pathlib.Path(self.topdir).glob('**/*')
                        if '/.git/' not in str(p) and p.is_file())
        start = len(self.topdir)  # index after 'topdir/' in each path, except it includes the slash
        return set((p[start:] for p in raw_pathlist))

    @functools.cached_property
    def metadata(self) -> sdrl.participant.Student:
        participantfile_path = os.path.join(self.topdir, c.PARTICIPANT_FILE)
        if os.path.isfile(participantfile_path):
            return sdrl.participant.Student(self.topdir)
        else:
            b.warning(f"'{participantfile_path}' not found, using dummy student description instead.")
            return sdrl.participant.Student.dummy_participant()

    @functools.cached_property
    def submission(self) -> set[str]:
        """tasknames from c.SUBMISSION_FILE (or empty if none)"""
        submissionfile_path = os.path.join(self.topdir, c.SUBMISSION_FILE)
        if not os.path.isfile(submissionfile_path):
            b.warning(f"'{submissionfile_path}' not found, using an empty set of submissions instead.")
            return set()
        submission_yaml = b.slurp_yaml(submissionfile_path)
        return set(submission_yaml.keys())

    @functools.cached_property
    def submission_pathset(self) -> set[str]:
        """paths with names matching submitted tasks"""
        return self._submission_pathset_and_remaining_submissions[0]

    @functools.cached_property
    def _submission_pathset_and_remaining_submissions(self) -> tuple[set[str], set[str]]:
        """paths with names matching submitted tasks & this"""
        paths_matched, submissions_matched = set(), set()
        my_re = re.compile(self.submission_re)
        for p in self.pathset:
            mm = my_re.search(p)
            if mm:
                paths_matched.add(p)
                submissions_matched.add(mm.group())
        remaining_submissions = self.submission - submissions_matched
        return paths_matched, remaining_submissions

    @functools.cached_property
    def submission_re(self) -> str:
        """regexp matching the name of any submitted task"""
        items_re = '|'.join([re.escape(item) for item in sorted(self.submission)])
        return f"\\b{items_re}\\b"  # match task names only as words or multiwords

    @functools.cached_property
    def submissions_remaining(self) -> set[str]:
        """submissions not matched by paths"""
        return self._submission_pathset_and_remaining_submissions[1]

    def exists(self, path: str) -> bool:
        return path in self.pathset

    def actualpath(self, path: str) -> str:
        """Turns the absolute virtual path into a physical path."""
        assert path[0] == '/'
        return os.path.join(self.topdir, path[1:])

    def actualsize(self, path: str) -> int:
        return pathlib.Path(self.actualpath(path)).stat().st_size


class Context:
    """The virtual filesystem that is being browsed: the merged union of the student Workdirs."""
    # cssfile: b.OStr  # TODO 2: argument of --cssfile
    course: sdrl.course.CourseSI
    workdirs: list[Workdir]  # list of student dirs, forming implicit pairs (0, 1), (2, 3), ...
    
    def __init__(self, args: ap_sub.Namespace):
        self.workdirs = [Workdir(topdir) for topdir in args.dir]
        student1 = self.workdirs[0].metadata
        if not hasattr(student1, 'course_url'):
            b.critical(f"'{args.dir[0]}' must have a {c.PARTICIPANT_FILE}, because we need a course URL")
        self.course = sdrl.course.CourseSI(configdict=student1.metadatadict, context=student1.metadata_url)
        macroexpanders.register_macros(self.course)  # noqa

    @functools.cached_property
    def course_url(self) -> str:
        return self.workdirs[0].metadata.course_url

    @functools.cached_property
    def pathset(self) -> set[str]:
        """file pathnames present in any Workdir"""
        return set(itertools.chain.from_iterable((wd.pathset for wd in self.workdirs)))

    @functools.cached_property
    def submission(self) -> set[str]:
        """union of submitted tasknames"""
        return set(itertools.chain.from_iterable((wd.submission for wd in self.workdirs)))

    @functools.cached_property
    def submission_pathset(self) -> set[str]:
        """union of submission_pathsets"""
        return set(itertools.chain.from_iterable((wd.submission_pathset for wd in self.workdirs)))

    @functools.cached_property
    def submission_re(self) -> str:
        """regexp matching the name of any submitted task"""
        items_re = '|'.join([re.escape(item) for item in sorted(self.submission)])
        return f"\\b({items_re})\\b"  # match task names only as words or multiwords

    def ls(self, dirname: str) -> tuple[set[str], set[str]]:
        """dirs, files = ls("/some/dir/")  somewhat like the Unix ls command"""
        assert dirname.endswith('/')
        dirs, files = set(), set()
        start = len(dirname)  # index of 'local' (within dirname) part of pathname
        for path in self.pathset:
            if not path.startswith(dirname):  # not our business
                continue
            localpath = path[start:]
            slashpos = localpath.find("/")
            slash_found = slashpos > -1
            if slash_found:
                dirs.add(localpath[:slashpos+1])  # adding it again makes no difference
            else:
                files.add(localpath)
        return dirs, files

    def workdir(self, workdirname: str) -> Workdir:
        candidates = [wd for wd in self.workdirs if wd.topdir == workdirname]
        return candidates[0]  # rightfully crash for nonexisting name


basepage_html = """<!DOCTYPE html>
<html>
 <head>
  <title>{title}</title>
  <meta charset="utf-8">
  {csslinks}
 </head>
 <body>
  {body}
 </body>
</html>
"""


viewer_css = """

"""


@bottle.route("/")
def serve_root():
    global context
    body = "%s\n\n%s" % (
        html_for_submissionrelated_files(),
        html_for_directorylist("/", breadcrumb=False),
    )
    pagetext = basepage_html.format(
        title=f"viewer",
        csslinks=html_for_csslinks(context.course_url),
        body=body
    )
    return pagetext


@bottle.route(FAVICON_URL)
def serve_favicon():
    return (200, favicon32x32_png, 'img/png')


@bottle.route(VIEWER_CSS_URL)
def serve_css():
    return (200, viewer_css, 'text/css')


@bottle.route("<mypath:path>/")
def serve_directory(mypath: str):
    global context
    pagetext = basepage_html.format(
        title=f"viewer",
        csslinks=html_for_csslinks(context.course_url),
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
        csslinks=html_for_csslinks(context.course_url),
        body=body
    )
    return pagetext


def handle_rawfile(mypath: str, workdir: str):
    global context
    wd = context.workdir(workdir)
    return bottle.static_file(wd.actualpath(mypath), root='.')


def html_for_breadcrumb(path: str) -> str:
    parts = [f"<p><a href='/'>viewer</a>:"]
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
    return f"{''.join(parts)}</p>"


def html_for_csslinks(course_url: str) -> str:
    return (f'<link rel="icon" type="image/png" sizes="16x16 32x32" href="{FAVICON_URL}">\n'
        f'<link href="{course_url}/sedrila.css" rel="stylesheet">\n'
        f'<link href="{course_url}/local.css" rel="stylesheet">\n'
        f'<link href="{course_url}/codehilite.css" rel="stylesheet">\n'
        f'<link href="{VIEWER_CSS_URL}" rel="stylesheet">\n')


def html_for_directorylist(mypath, breadcrumb=True) -> str:
    """A page listing the directories and files under mypath in the virtual filesystem."""
    global context
    dirs, files = context.ls(mypath)
    lines = [html_for_breadcrumb(mypath) if breadcrumb else ""]  # noqa
    lines.append("<hr>")
    lines.append(f"<h1>Contents of '{mypath}'</h1>")
    lines.append("<h2>Subdirectories</h2>")
    lines.append("<table>")
    for dir in sorted(dirs):
        lines.append(f"<tr><td><a href='{dir}'>{dir}</a></td></tr>")
    lines.append("</table>")
    lines.append("<hr>")
    lines.append("<h2>Files</h2>")
    lines.append("<table>")
    for file in sorted(files):
        filepath = os.path.join(mypath, file)
        lines.append(f"<tr><td><a href='{filepath}'>{file}</a></td>{html_for_file_existence(filepath)}</tr>")
    lines.append("</table>")
    lines.append("<hr>")
    body = "\n".join(lines)
    return body


def html_for_file(mypath) -> str:
    """
    Page body showing each Workdir's version (if existing) of file mypath, and pairwise diffs where possible.
    We create this as a Markdown page, then render it.
    """
    global context
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
            lines.append(f"<a href='?raw={workdir.topdir}'>{workdir.actualpath(mypath)}</a>")
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
        prevdir = context.workdirs[idx-1]  # previous workdir
        toc.append(f"<a href='#diff-{prevdir.topdir}-{workdir.topdir}'>diff</a>  ")
        lines.append(f"<hr id='diff-{prevdir.topdir}-{workdir.topdir}'>")
        lines.append(f"# {idx-1}/{idx}. diff {prevdir.topdir}/{workdir.topdir} for {filename}")
        if kinds[-2:] != [SRC, SRC]:
            lines.append("No diff shown. It requires two source files, which we do not have here.")
            return
        diff_output = diff_files(prevdir.actualpath(mypath), workdir.actualpath(mypath))
        lines.append("\n```diff")
        lines.append(diff_output)
        lines.append("```")

    # ----- iterate through workdirs and prepare the sections:
    kinds = []  # which files are SRC, BINARY, or MISSING
    lines = []  # noqa, some entries will be entire file contents, not single lines
    toc = []
    for idx, workdir in enumerate(context.workdirs):
        toc.append(f"<a href='#{workdir.topdir}'>{idx}. {workdir.topdir}</a>  ")
        lines.append(f"<hr id='{workdir.topdir}'>")
        lines.append(f"# {idx}. {workdir.topdir}: {filename}")
        if not workdir.exists(mypath):
            lines.append(f"(('{mypath}' does not exist in '{workdir.topdir}'))")
            kinds.append(MISSING)
        else:
            append_one_file()
        if idx % 2 == 1:
            append_diff()
    # ----- render:
    the_toc, the_lines = '\n'.join(toc), '\n'.join(lines)
    markdown = f"{html_for_breadcrumb(mypath)}\n# {mypath}\n{the_toc}\n{the_lines}"
    macros.switch_part("viewer")
    mddict = md.render_markdown(mypath, filename, markdown, b.Mode.STUDENT, dict())
    return mddict['html']


def html_for_file_existence(mypath: str) -> str:
    """One or more table column entries with file existence markers for each file or file pair."""
    global context
    BEGIN = '<td>'
    END = '</td>'
    MISSING = '-- '
    entries = [BEGIN]
    for idx, wd in enumerate(context.workdirs):
        if wd.exists(mypath):
            entries.append(f"{str(idx)} ")
        else:
            entries.append(MISSING)
        if idx % 2 == 1:  # finish a pair
            if entries[-1] != MISSING and entries[-2] != MISSING:  # both files are present
                size_even, size_odd = prev_wd.actualsize(mypath), wd.actualsize(mypath)
                b.info(f"sizes: even {size_even}, odd {size_odd}")
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


def html_for_submissionrelated_files() -> str:
    global context
    lines = ["<hr>", "<h1>Files with submission-related names</h1>", "<table>"]
    for mypath in sorted(context.submission_pathset):
        lines.append(f"<tr><td><a href='{mypath}'>{mypath}</a></td>{html_for_file_existence(mypath)}</tr>")
    lines.append("</table>")
    return "\n".join(lines)


def diff_files(path1: str, path2: str) -> str:
    cmd = f"/usr/bin/diff '{path1}' '{path2}'"
    result = subprocess.run(cmd, shell=True, text=True, capture_output=True, check=False)
    if result.returncode == 0:
        return "files are identical"
    elif result.returncode == 1:  # differences found
        return result.stdout
    else:  # there were execution problems
        return f"<p>('diff' exit status: {result.returncode}</p>\n{result.stderr}"
