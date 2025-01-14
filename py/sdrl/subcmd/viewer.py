import base64
import dataclasses
import html
import os
import pathlib
import re
import typing as tg

import argparse_subcommand as ap_sub
import naja_atra.server as nas

import base as b
import sdrl.argparser
import sdrl.constants as c
import sdrl.course
import sdrl.macros as macros
import sdrl.macroexpanders as macroexpanders
import sdrl.markdown as md
import sdrl.participant

meaning = """Specialized webserver for locally viewing contents of one or more student repo work directories."""
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
context: 'Context'  # global data


def add_arguments(subparser: ap_sub.ArgumentParser):
    subparser.add_argument('--port', '-p', type=int, default=8080,
                           help="webserver will listen on this port (default: 8080)")
    subparser.add_argument('--instructor', '-i', action='store_true', default=False,
                           help="generate task links to the instructor versions (not the student versions)")
    subparser.add_argument('dir', type=str, nargs='+',
                           help="short relative path of student workdir to be browsed")


def execute(pargs: ap_sub.Namespace):
    b.set_loglevel('INFO')
    b.set_register_files_callback(lambda s: None)  # in case student .md files contain weird macro calls
    global context
    context = Context(pargs)
    dump()
    b.critical("STOP.")
    b.info(f"Webserver starts. Visit 'http://localhost:{pargs.port}/'. Terminate with Ctrl-C.")
    b.warning("Incomplete development version, not ready for use. Temporarily use 'viewer1' for serious use.")
    try:
        nas.start(port=pargs.port)
    except KeyboardInterrupt:
        print("  sedrila viewer terminated.")


def dump():
    global context
    for wd in context.workdirs:
        stud = wd.metadata
        b.info(f"\n===== {stud.root}: {stud.student_name}")
        print(f"--Paths:\t{wd.pathlist[:3]}...{wd.pathlist[-3:]} ({len(wd.pathlist)} total)")
        print(f"--{c.SUBMISSION_FILE}:\t{wd.submission} ({len(wd.submission)} total)")
        print(f"--submission files:\t{wd.submission_pathlist[:3]}...{wd.submission_pathlist[-3:]} "
              f"({len(wd.submission_pathlist)} total)")


class Workdir:
    """Represents and handles one student working directory"""
    topdir: str  # name of workdir as given on commandline
    metadata: sdrl.participant.Student
    submission: set[str]  # list of tasknames from SUBMISSION_FILE (or empty if none)
    pathlist: list[str]  # fixed, sorted list of file pathnames
    pathset: set[str]  # equivalent set of file pathnames (for quick member checks)
    submission_pathlist: list[str]  # paths with names matching submitted tasks

    def __init__(self, topdir: str):
        self.topdir = topdir = topdir.rstrip('/')  # avoid trouble with non-canonical names
        self.metadata = self._participant_data(topdir)
        self.submission = self._submission_data(os.path.join(topdir, c.SUBMISSION_FILE))
        self.pathlist = self._ordered_pathlist(topdir)
        self.pathset = set(self.pathlist)
        self.submission_pathlist = self._paths_with_submission(self.pathlist, self.submission)
    
    @staticmethod
    def _ordered_pathlist(topdir: str) -> list[str]:
        if not os.path.exists(topdir):
            b.critical(f"'{topdir}' does not exist.")
        elif not os.path.isdir(topdir):
            b.critical(f"'{topdir}' must be a directory.")
        raw_pathlist = sorted((str(p) for p in pathlib.Path(topdir).glob('**/*')
                              if '/.git/' not in str(p) and p.is_file()))
        start = len(topdir) + 1  # index after 'topdir/' in each path
        return [p[start:] for p in raw_pathlist]
    
    @staticmethod
    def _participant_data(topdir: str) -> sdrl.participant.Student:
        participantfile_path = os.path.join(topdir, c.PARTICIPANT_FILE)
        if os.path.isfile(participantfile_path):
            return sdrl.participant.Student(topdir)
        else:
            b.warning(f"'{participantfile_path}' not found, using dummy student description instead.")
            return sdrl.participant.Student.dummy_participant()

    @staticmethod
    def _paths_with_submission(pathlist: list[str], submission: set[str]) -> list[str]:
        items_re = '|'.join([re.escape(item) for item in sorted(submission)])
        submission_re = f"\\b({items_re})\\b"  # match task names only as words or multiwords
        return [p for p in pathlist if re.match(submission_re, p)]  # formerly: match(..., os.path.basename(p)

    
    @staticmethod
    def _submission_data(submissionfile_path: str) -> set[str]:
        if not os.path.isfile(submissionfile_path):
            b.warning(f"'{submissionfile_path}' not found, using an empty set of submissions instead.")
            return set()
        submission_yaml = b.slurp_yaml(submissionfile_path)
        return set(submission_yaml.keys())


class Context:
    # cssfile: b.OStr  # TODO 2: argument of --cssfile
    course: sdrl.course.CourseSI
    workdirs: list[Workdir]  # list of student dirs, forming implicit pairs (0, 1), (2, 3), ...
    
    def __init__(self, args: ap_sub.Namespace):
        self.workdirs = [Workdir(topdir) for topdir in args.dir]
        student1 = self.workdirs[0].metadata
        self.course = sdrl.course.CourseSI(configdict=student1.metadatadict, context=student1.metadata_url)
        macroexpanders.register_macros(self.course)  # noqa


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


def _indented_div(level: int, text: str) -> str:
    return "%s<div style='padding-left: %dem'>%s</div>" % (2*level*' ', 2*level, text)
