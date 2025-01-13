import base64
import dataclasses
import functools
import html
import http.server
import io
import os
import pathlib
import posixpath
import re
import shutil
import sys
import typing as tg
import urllib.parse

import argparse_subcommand as ap_sub

import base as b
import sdrl.argparser
import sdrl.constants as c
import sdrl.course
import sdrl.macros as macros
import sdrl.macroexpanders as macroexpanders
import sdrl.markdown as md
import sdrl.participant

meaning = """Specialized webserver for locally viewing contents of a student repo work directory."""
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
FAVICON_URL = "/favicon-32x32.png"


def add_arguments(subparser):
    subparser.add_argument('--port', '-p', type=int, default=8080,
                           help="webserver will listen on this port (default: 8080)")
    subparser.add_argument('--instructor', '-i', action='store_true', default=False,
                           help=f"generate task links to the instructor versions (not the student versions)")


def execute(pargs: ap_sub.Namespace):
    b.set_loglevel('INFO')
    b.info(f"Webserver starts. Visit 'http://localhost:{pargs.port}/'. Terminate with Ctrl-C.")
    b.set_register_files_callback(lambda s: None)  # in case student .md files contain weird macro calls
    student = sdrl.participant.Student()
    course = sdrl.course.CourseSI(configdict=student.metadatadict, context=student.metadata_url)
    basedir = os.path.basename(os.getcwd())
    macroexpanders.register_macros(course)  # noqa
    server = SedrilaServer(('', pargs.port), SedrilaHTTPRequestHandler,
                           course=course, student=student, basedir=basedir,
                           pargs=pargs)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("  sedrila viewer terminated.")


def render_markdown(info: 'Info', infile, outfile):
    markup_body = infile.read().decode()
    markup = f"# {info.lastname}:{info.fullpath}\n\n{info.byline}\n\n{markup_body}\n"
    do_render_markdown(info, markup, outfile)


def render_prot(info: 'Info', infile, outfile):
    markup = (f"# {info.lastname}:{info.fullpath}\n\n{info.byline}\n\n"
              f"[PROT::{info.fullpath}]\n")
    do_render_markdown(info, markup, outfile)


def render_sourcefile(language: str, info: 'Info', infile, outfile):
    src = infile.read().decode()
    markup = (f"# {info.title}\n\n{info.byline}\n\n"
              f"```{language}\n"
              f"{src}\n"
              f"```\n")
    do_render_markdown(info, markup, outfile)


def just_copyfile(copyfilefunc, info, infile, outfile):
    copyfilefunc(infile, outfile)


def do_render_markdown(info: 'Info', markup: str, outfile):
    template = """<!DOCTYPE HTML>
      <html>
      <head>
        <meta charset="{enc}">
        {csslinks}
        <title>{title}</title>
      </head>
      <body>
        {body}
      </body>
      </html>
    """
    macros.switch_part("viewer")
    mddict = md.render_markdown(info.fullpath, info.basename, markup, b.Mode.STUDENT, dict())
    htmltext = template.format(enc='utf8', csslinks=info.csslinks,
                               title=f"{info.lastname}:{info.basename}", body=mddict['html'])
    outfile.write(htmltext.encode())


@dataclasses.dataclass
class Info:
    pargs: ap_sub.Namespace
    basedir: str  # basename of top-level directory (=username)
    basename: str
    fullpath: str
    lastname: str
    byline: str
    csslinks: str

    @property
    def title(self) -> str:
        return f"{self.basedir}:{self.basename}"


class SedrilaServer(http.server.HTTPServer):
    pargs: ap_sub.Namespace
    student_name: str = "N.N."
    lastname: str = "N.N."
    partner_name: str = ""
    course_url: str = ""
    course: sdrl.course.CourseSI
    basedir: str  # basename of top-level directory (=username)
    submissionitems: dict
    submission_re: str

    def __init__(self, *args, **kwargs):
        self.server_version = f"SedrilaHTTP/{sdrl.argparser.SedrilaArgParser.get_version()}"
        self.pargs = kwargs.pop('pargs')
        self.course = kwargs.pop('course')
        self.basedir = kwargs.pop('basedir')
        student = kwargs.pop('student')
        try:
            self.student_name = student.student_name
            mm = re.search(r"(\w+)$", self.student_name)
            self.lastname = mm.group(1) if mm else "??"
            self.partner_name = student.partner_student_name
            self.course_url = student.course_url
        except b.CritialError:
            pass  # fall back to defaults
        if os.path.exists(c.SUBMISSION_FILE):
            self.submissionitems = b.slurp_yaml(c.SUBMISSION_FILE)
            self.submission_re = self._matcher_regexp(self.submissionitems.keys())
            self.submissionitem_paths = self._find_submissionitems(self.submission_re)
            self.submissionitems_html = self._format_submissionitems(self.submissionitem_paths)
        else:
            self.submissionitems = dict()
            self.submission_re = None
            self.submissionitem_paths = []
            self.submissionitems_html = ""
        super().__init__(*args, **kwargs)

    def version_string(self) -> str:
        return self.server_version

    def sedrila_linkitem(self, name: str, path: str, instructor: bool, tag="span", dirs=False):
        submission_mm = self.submission_re and re.match(self.submission_re, name)
        tasklink = ""
        if not dirs and name.endswith('.html'):
            htmlpagelink = f"&#9;&#9;&#9;<a href='{name}page' class='vwr-htmlpagelink'>page</a>"
        else:
            htmlpagelink = ""
        if dirs:
            cssclass = 'vwr-dirlink'
        elif submission_mm:
            cssclass = 'vwr-filelink-submission'
            matchtext = submission_mm.group()
            instructordir = (f"{c.AUTHOR_OUTPUT_INSTRUCTORS_DEFAULT_SUBDIR}/"
                             if instructor else "")
            taskurl = f"{self.course_url}/{instructordir}{matchtext}.html"
            tasklink = f"&#9;&#9;&#9;<a href='{taskurl}' class='vwr-tasklink'>Task '{matchtext}'</a>"
        else:
            cssclass = 'vwr-filelink'
        href = urllib.parse.quote(path, errors='surrogatepass')
        linktext = html.escape(name, quote=False)
        item = (f"  <{tag} class='vwr-pre'><a href='{href}' class='{cssclass}'>{linktext}</a>"
                f"{tasklink}{htmlpagelink}</{tag}>")
        return item

    def _find_submissionitems(self, submission_re: str) -> list[str]:
        """List of all filepaths starting with a submission item name."""
        candidates = sorted((str(p) for p in pathlib.Path('.').glob('**/*')
                             if p.is_file() and not str(p).startswith('.git')))
        return [p for p in candidates if re.match(submission_re, os.path.basename(p))]

    def _format_submissionitems(self, paths: list[str]) -> str:
        """Turn sorted list of relevant files into an HTML fragment."""
        TAB = '\t'
        NEWLINE = '\n'
        lines = []
        previous_pathparts = []
        for path in paths:
            same_start = True
            pathparts = path.split("/")
            filename = pathparts.pop()  # pathparts are now only the dirnames
            for i in range(len(pathparts)):
                if same_start and len(previous_pathparts) > i and previous_pathparts[i] == pathparts[i]:
                    pass  # reuse existing dirname lines
                else:
                    same_start = False
                    lines.append(_indented_div(i, pathparts[i]))
            lines.append(_indented_div(len(pathparts), self.sedrila_linkitem(filename, path, self.pargs.instructor)))
            previous_pathparts = pathparts
        return f"<p>\n{NEWLINE.join(lines)}\n</p>\n"

    def _matcher_regexp(self, items: tg.Iterable[str]) -> str:
        return '|'.join([re.escape(item) for item in items])


class SedrilaHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Serve nice directory listings, serve rendered versions of some file types and files as-is otherwise."""
    server: SedrilaServer
    renderer: tg.Callable[[tg.Any, tg.Any], None]  # for-read() file, for-write() file
    extensions_map = _encodings_map_default = {
        '.gz': 'application/gzip',
        '.Z': 'application/octet-stream',
        '.bz2': 'application/x-bzip2',
        '.xz': 'application/x-xz',
    }
    how_to_render = dict(  # suffix -> (mimetype, renderfunc)
        md=('text/html', render_markdown),
        c=('text/html', functools.partial(render_sourcefile, 'c')),
        css=('text/html', functools.partial(render_sourcefile, 'css')),
        html=('text/html', functools.partial(render_sourcefile, 'html')),
        json=('text/html', functools.partial(render_sourcefile, 'json')),
        java=('text/html', functools.partial(render_sourcefile, 'java')),
        py=('text/html', functools.partial(render_sourcefile, 'python')),
        sh=('text/html', functools.partial(render_sourcefile, 'sh')),
        yaml=('text/html', functools.partial(render_sourcefile, 'yaml')),
        prot=('text/html', render_prot),
        png=('image/png', lambda info, infile, outfile: shutil.copyfileobj(infile, outfile))
    )

    def send_head(self):  # simplified: no caching, no Content-Length
        path = self.translate_path(self.path)
        f = None  # noqa
        if os.path.isdir(path):
            parts = urllib.parse.urlsplit(self.path)
            if not parts.path.endswith('/'):
                self.send_response(http.HTTPStatus.MOVED_PERMANENTLY)
                new_parts = (parts[0], parts[1], parts[2] + '/',
                             parts[3], parts[4])
                new_url = urllib.parse.urlunsplit(new_parts)
                self.send_header("Location", new_url)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return None
            return self.list_directory(path)
        ctype = self.guess_type(path)
        if path.endswith("/"):
            self.send_error(http.HTTPStatus.NOT_FOUND, "File not found")
            return None
        try:
            f = self.the_file_for(path)
        except FileNotFoundError:
            self.send_error(http.HTTPStatus.NOT_FOUND, "File not found")
            return None
        except OSError as exc:
            self.send_error(http.HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
            return None
        try:
            self.send_response(http.HTTPStatus.OK)
            self.send_header("Content-type", ctype)
            self.end_headers()
            return f
        except:
            f.close()
            raise

    def list_directory(self, path):
        try:
            dirlist = os.listdir(path)
        except OSError:
            self.send_error(
                http.HTTPStatus.NOT_FOUND,
                "No permission to list directory")
            return None
        dirlist.sort(key=lambda a: a.lower())
        pairslist = [(name, os.path.join(path, name)) for name in dirlist]
        dirpairs = [(name, fullpath) for name, fullpath in pairslist
                    if os.path.isdir(fullpath)]
        filepairs = [(name, fullpath) for name, fullpath in pairslist
                     if os.path.isfile(fullpath)]
        r = []
        try:
            displaypath = urllib.parse.unquote(self.path,
                                               errors='surrogatepass')
        except UnicodeDecodeError:
            displaypath = urllib.parse.unquote(path)
        displaypath = html.escape(displaypath, quote=False)
        enc = sys.getfilesystemencoding()
        info = Info(pargs=self.server.pargs,
                    basedir=self.server.basedir, basename=displaypath, fullpath=displaypath,
                    lastname=self.server.lastname, byline=self.sedrila_byline(),
                    csslinks=self.sedrila_csslinks())
        r.append('<!DOCTYPE HTML>')
        r.append('<html>')
        r.append('<head>')
        r.append(f'<meta charset="{enc}">')
        r.append(info.csslinks)
        r.append(f'<title>{info.title}</title>\n</head>')
        r.append(f'<body>\n<h1>{info.title}</h1>')
        r.append(f'<p>{info.byline}</p>')
        if self.server.submissionitems_html:
            r.append(f"<hr>\n<h3>Files named like '{c.SUBMISSION_FILE}' items</h3>\n")
            r.append(self.server.submissionitems_html)
        if filepairs:
            r.append('<hr>\n<h3>Files</h3>\n<ol>')
            r.extend(self.sedrila_linkitems(filepairs, info.pargs.instructor))
            r.append('</ol>')
        if dirpairs:
            r.append('<hr>\n<h3>Directories</h3>\n<ol>')
            r.extend(self.sedrila_linkitems(dirpairs, info.pargs.instructor, dirs=True))
            r.append('</ol>')
        r.append('</body>\n</html>\n')
        encoded = '\n'.join(r).encode(enc, 'surrogateescape')
        f = io.BytesIO()
        f.write(encoded)
        f.seek(0)
        self.send_response(http.HTTPStatus.OK)
        self.send_header("Content-type", "text/html; charset=%s" % enc)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.renderer = functools.partial(just_copyfile, super().copyfile, info)
        return f

    def copyfile(self, source, outputfile):
        """Render file-like object source into file-like destination outputfile."""
        self.renderer(source, outputfile)

    def guess_type(self, path):
        base, ext = posixpath.splitext(path)
        basename = os.path.basename(path)
        info = Info(pargs=self.server.pargs,
                    basename=basename, fullpath=os.path.relpath(path),
                    lastname=self.server.lastname, byline=self.sedrila_byline(),
                    csslinks=self.sedrila_csslinks())
        if ext and ext[1:] in self.how_to_render:
            mimetype, renderfunc = self.how_to_render[ext[1:]]  # lookup without the dot
            self.renderer = functools.partial(renderfunc, info)
            return mimetype
        elif ext == ".htmlpage":  # special case
            self.renderer = functools.partial(just_copyfile, super().copyfile, info)
            return 'text/html'
        else:
            self.renderer = functools.partial(just_copyfile, super().copyfile, info)
        return super().guess_type(path)

    def the_file_for(self, path: str):
        """Return a diskfile handle or virtualfile handle."""
        if path.endswith(FAVICON_URL):
            return io.BytesIO(favicon32x32_png)
        else:
            return open(self.sedrila_actualpath(path), 'rb')

    def sedrila_actualpath(self, path: str) -> str:
        """Convert *.htmlpage to *.html (special case)."""
        actual = re.sub(r"\.htmlpage$", ".html", path)
        # print(f"actualpath: {path} -> {actual}")
        return actual

    def sedrila_byline(self) -> str:
        partner = f" (and {self.server.partner_name})" if self.server.partner_name else ""
        return f"{self.server.student_name}{partner}"

    def sedrila_csslinks(self) -> str:
        if not self.server.course_url:
            return ""
        return (f'<link rel="icon" type="image/png" sizes="16x16 32x32" href="{FAVICON_URL}">\n'
                f'<link href="{self.server.course_url}/sedrila.css" rel="stylesheet">\n'
                f'<link href="{self.server.course_url}/local.css" rel="stylesheet">\n'
                f'<link href="{self.server.course_url}/codehilite.css" rel="stylesheet">\n')

    def sedrila_linkitems(self, pairs: tg.Iterable[tuple[str, str]], instructor: bool, dirs=False) -> tg.Iterable[str]:
        res = []
        for name, fullpath in pairs:
            if self.is_sedrila_invisible(name) or os.path.islink(fullpath):
                continue  # skip dotfiles and symlinks
            item = self.server.sedrila_linkitem(name, name, instructor, 'li', dirs)
            res.append(item)
        return res

    @staticmethod
    def is_sedrila_invisible(name: str) -> bool:
        return name.startswith('.')  # TODO 2: use https://pypi.org/project/gitignore-parser/


def _indented_div(level: int, text: str) -> str:
    return "%s<div style='padding-left: %dem'>%s</div>" % (2 * level * ' ', 2 * level, text)
