import base64
import dataclasses
import functools
import html
import itertools
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
        print(f"--Paths:\t{list(wd.pathset)[:3]}...{list(wd.pathset)[-3:]} ({len(wd.pathset)} total)")
        print(f"--{c.SUBMISSION_FILE}:\t{wd.submission} ({len(wd.submission)} total)")
        print(f"--submission files:\t{list(wd.submission_pathset)[:3]}...{list(wd.submission_pathset)[-3:]} "
              f"({len(wd.submission_pathset)} total)")
    b.info(f"\n===== Context")
    print(context.ls('/'))

class Workdir:
    """Represents and handles one student working directory."""
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
        return set((p for p in self.pathset if re.match(self.submission_re, p)))

    @functools.cached_property
    def submission_re(self) -> str:
        """regexp matching the name of any submitted task"""
        items_re = '|'.join([re.escape(item) for item in sorted(self.submission)])
        return f"\\b({items_re})\\b"  # match task names only as words or multiwords


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
