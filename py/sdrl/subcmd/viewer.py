import dataclasses
import datetime
import email.utils
import functools
import html
import http.server
import io
import os
import posixpath
import re
import sys
import typing as tg
import urllib.parse

import argparse_subcommand as ap_sub

import base as b
import sdrl.argparser
import sdrl.constants as c
import sdrl.participant

meaning = """Trivial webserver for viewing contents of a student repo work directory."""


def add_arguments(subparser):
    subparser.add_argument('--port', '-p', type=int, default=8080,
                           help="webserver will listen on this port (default: 8080)")
    subparser.add_argument('--all', '-a', action='store_true', default=False,
                           help=f"include the ignore-worthy files in the listing")


def execute(pargs: ap_sub.Namespace):
    b.set_loglevel('INFO')
    b.info(f"Extreeeemely basic webserver starts. Visit 'http://localhost:{pargs.port}/'. Terminate with Ctrl-C.")
    server = SedrilaServer(('', pargs.port), SedrilaHTTPRequestHandler)
    server.serve_forever()


@dataclasses.dataclass
class Info:
    path: str
    lastname: str
    byline: str


def render_markdown(info: Info, infile, outfile) -> str:
    markup_body = infile.read()
    markup = f"# {info.lastname}:{info.path}\n### {info.byline}\n\n{markup_body}\n"
    do_render_markdown(markup, outfile)


def render_prot(info: Info, infile, outfile) -> str:
    raw_prot = infile.read()
    markup = (f"# {info.lastname}:{info.path}\n### {info.byline}\n\n"
              f"```\n"
              f"{raw_prot}\n"
              f"```\n")
    html = do_render_markdown(markup)
    outfile.write(html)


def render_sourcefile(language: str, info: Info, infile, outfile) -> str:
    src = infile.read()
    markup = (f"# {info.lastname}:{info.path}\n### {info.byline}\n\n"
              f"```{language}\n"
              f"{src}\n"
              f"```\n")
    html = do_render_markdown(markup)
    outfile.write(html)


def do_render_markdown(markup: str, outfile):
    html = markup  # TODO 1: render, put into HTML template
    outfile.write(html)


class SedrilaServer(http.server.HTTPServer):
    student_name: str = "N.N."
    lastname: str = "N.N."
    partner_name: str = ""
    course_url: str = ""
    submissionitems: dict

    def __init__(self, *args, **kwargs):
        self.server_version = f"SedrilaHTTP/{sdrl.argparser.SedrilaArgParser.get_version()}"
        try:
            student = sdrl.participant.Student()
            self.student_name = student.student_name
            mm = re.search(r"(\w+)$", self.student_name)
            self.lastname = mm.group(1) if mm else "??"
            self.partner_name = student.partner_student_name
            self.course_url = student.course_url
        except b.CritialError:
            pass  # fall back to defaults
        if os.path.exists(c.SUBMISSION_FILE):
            self.submissionitems = ...  # b.slurp_yaml(c.SUBMISSION_FILE)
        else:
            self.submissionitems = dict()
        super().__init__(*args, **kwargs)

    def version_string(self) -> str:
        return self.server_version
    

class SedrilaHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Serve nice directory listings, serve rendered versions of some file types and files as-is otherwise."""
    renderer: tg.Callable[[tg.Any, tg.Any], None]  # for-read() file, for-write() file
    extensions_map = _encodings_map_default = {
        '.gz': 'application/gzip',
        '.Z': 'application/octet-stream',
        '.bz2': 'application/x-bzip2',
        '.xz': 'application/x-xz',
    }
    how_to_render = dict(  # suffix -> (mimetype, renderfunc)
        mdzz=('text/html', render_markdown),
        pyzz=('text/html', functools.partial(render_sourcefile, 'python)')),
        prot=('text/html', render_prot),
    )


    def xxxsend_head(self):  # TODO 2 remove
        """Common code for GET and HEAD commands.

        This sends the response code and MIME headers.

        Return value is either a file object (which has to be copied
        to the outputfile by the caller unless the command was HEAD,
        and must be closed by the caller under all circumstances), or
        None, in which case the caller has nothing further to do.

        """
        path = self.translate_path(self.path)
        f = None
        if os.path.isdir(path):
            parts = urllib.parse.urlsplit(self.path)
            if not parts.path.endswith('/'):
                # redirect browser - doing basically what apache does
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
        # check for trailing "/" which should return 404. See Issue17324
        # The test for this was added in test_httpserver.py
        # However, some OS platforms accept a trailingSlash as a filename
        # See discussion on python-dev and Issue34711 regarding
        # parsing and rejection of filenames with a trailing slash
        if path.endswith("/"):
            self.send_error(http.HTTPStatus.NOT_FOUND, "File not found")
            return None
        try:
            f = open(path, 'rb')
        except OSError:
            self.send_error(http.HTTPStatus.NOT_FOUND, "File not found")
            return None

        try:
            fs = os.fstat(f.fileno())
            # Use browser cache if possible
            if ("If-Modified-Since" in self.headers
                    and "If-None-Match" not in self.headers):
                # compare If-Modified-Since and time of last file modification
                try:
                    ims = email.utils.parsedate_to_datetime(
                        self.headers["If-Modified-Since"])
                except (TypeError, IndexError, OverflowError, ValueError):
                    # ignore ill-formed values
                    pass
                else:
                    if ims.tzinfo is None:
                        # obsolete format with no timezone, cf.
                        # https://tools.ietf.org/html/rfc7231#section-7.1.1.1
                        ims = ims.replace(tzinfo=datetime.timezone.utc)
                    if ims.tzinfo is datetime.timezone.utc:
                        # compare to UTC datetime of last modification
                        last_modif = datetime.datetime.fromtimestamp(
                            fs.st_mtime, datetime.timezone.utc)
                        # remove microseconds, like in If-Modified-Since
                        last_modif = last_modif.replace(microsecond=0)

                        if last_modif <= ims:
                            self.send_response(http.HTTPStatus.NOT_MODIFIED)
                            self.end_headers()
                            f.close()
                            return None

            self.send_response(http.HTTPStatus.OK)
            self.send_header("Content-type", ctype)
            self.send_header("Content-Length", str(fs[6]))
            self.send_header("Last-Modified",
                self.date_time_string(fs.st_mtime))
            self.end_headers()
            return f
        except:
            f.close()
            raise

    def flush_headers(self):  # TODO 1: remove content-length header if we render something
        if hasattr(self, '_headers_buffer'):
            self.wfile.write(b"".join(self._headers_buffer))
            self._headers_buffer = []

    def list_directory(self, path):
        """Helper to produce a directory listing (absent index.html).

        Return value is either a file object, or None (indicating an
        error).  In either case, the headers are sent, making the
        interface the same as for send_head().

        """
        try:
            list = os.listdir(path)
        except OSError:
            self.send_error(
                http.HTTPStatus.NOT_FOUND,
                "No permission to list directory")
            return None
        list.sort(key=lambda a: a.lower())
        pairslist = [(name, os.path.join(path, name)) for name in list]
        dirpairs = [(name, fullname) for name, fullname in pairslist 
                    if os.path.isdir(fullname)]
        filepairs = [(name, fullname) for name, fullname in pairslist 
                     if os.path.isfile(fullname)]
        r = []
        try:
            displaypath = urllib.parse.unquote(self.path,
                                               errors='surrogatepass')
        except UnicodeDecodeError:
            displaypath = urllib.parse.unquote(path)
        displaypath = html.escape(displaypath, quote=False)
        enc = sys.getfilesystemencoding()
        title = displaypath
        r.append('<!DOCTYPE HTML>')
        r.append('<html lang="en">')
        r.append('<head>')
        r.append(f'<meta charset="{enc}">')
        r.append(self.csslinks())
        r.append(f'<title>{self.server.lastname}:{title}</title>\n</head>')
        r.append(f'<body>\n<h1>{self.server.lastname}:{title}</h1>')
        partner = f" (Partner: {self.server.partner_name})" if self.server.partner_name else ""
        r.append(f'<p>{self.server.student_name}{partner}</p>')
        if dirpairs:
            r.append('<hr>\n<h3>Directories</h3>\n<ol>')
            r.extend(self.linkitems(dirpairs))
            r.append('</ol>')
        if filepairs:
            r.append('<hr>\n<h3>Files</h3>\n<ol>')
            r.extend(self.linkitems(filepairs))
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
        return f

    def linkitems(self, pairs: tg.Iterable[tuple[str, str]]) -> tg.Iterable[str]:
        res = []
        for name, fullname in pairs:
            if self.is_invisible(name) or os.path.islink(fullname):
                continue  # skip dotfiles and symlinks
            href = urllib.parse.quote(name, errors='surrogatepass')
            linktext = html.escape(name, quote=False)
            res.append(f"  <li><a href='{href}'>{linktext}</a></li>\n")
        return res

    def is_invisible(self, name: str) -> bool:
        return name.startswith('.')  # TODO 2: use https://pypi.org/project/gitignore-parser/

    def xxxcopyfile(self, source, outputfile):
        """Render file-like object source into file-like destination outputfile."""
        self.renderer(source, outputfile)

    def xxxguess_type(self, path):
        base, ext = posixpath.splitext(path)
        basename = os.path.basename(path)
        if ext and ext[1:] in self.how_to_render:
            mimetype, renderfunc = self.how_to_render[ext[1:]]  # lookup without the dot
            self.renderer = functools.partial(renderfunc, basename)
            return mimetype
        else:
            self.renderer = super().copyfile
        return super().guess_type(path)

    def csslinks(self) -> str:
        if not self.server.course_url:
            return ""
        link1 = f'<link href="{self.server.course_url}/sedrila.css" rel="stylesheet">'
        link2 = f'<link href="{self.server.course_url}/local.css" rel="stylesheet">'
        return f"{link1}\n{link2}"