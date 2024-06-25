"""
Common superclasses for
a) Course, Chapter, Taskgroup, Task, and their builders all defined in course.py 
b) Glossary, defined in glossary.py
Not all attributes are needed for all parts.
"""

import glob
import os.path
import re
import zipfile

import yaml

import base as b
import sdrl.html as h


class Structurepart:
    TOC_LEVEL = 0  # indent level in table of contents
    sourcefile: str = "???"  # the originating pathname
    outputfile: str  # the target pathname
    slug: str  # the file/dir basename by which we refer to the part
    title: str  # title: value

    def __repr__(self):
        return self.slug


class StructurepartbuilderMixin:  # to be mixed into a Structurepart class
    metadata_text: str  # the YAML front matter character stream
    metadata: b.StrAnyDict  # the YAML front matter
    content: str  # the markdown block
    linkslist_top: str = ''  # generated HTML of cross reference links
    linkslist_bottom: str = ''  # generated HTML of cross reference links
    stage: str = ''  # stage: value
    skipthis: bool  # do not include this chapter/taskgroup/task in generated site
    toc: str  # table of contents

    @property
    def breadcrumb_item(self) -> str:
        return "(undefined)"

    @property
    def to_be_skipped(self) -> bool:
        return ...  # defined in concrete part classes

    @property
    def toc_entry(self) -> str:
        classes = f"stage-{self.stage}" if self.stage else "no-stage"
        return h.indented_block(self.toc_link_text, self.TOC_LEVEL, classes)

    @property
    def toc_link_text(self) -> str:
        titleattr = f"title=\"{self.title}\""
        return f"<a href='{self.outputfile}' {titleattr}>{self.slug}</a>"

    def as_json(self) -> b.StrAnyDict:
        return dict(title=self.title)

    def evaluate_stage(self, context: str, course) -> None:
        """
        Cut the 'stage' attribute down to its first word, check it against course.stages, report violations.
        Set self.skipthis according to course.include_stage.
        """
        self.skipthis = False  # default case
        # ----- handle parts with no 'stage:' given:
        if not getattr(self, 'stage', ''):
            return
        # ----- extract first word from stage:
        mm = re.match(r'\w+', self.stage)  # match first word
        stageword = mm.group(0) if mm else ''
        # ----- handle parts with unknown stage (error):
        try:
            stage_index = course.stages.index(stageword)
        except ValueError:
            b.error(f"{context}: Illegal value of 'stage': '{stageword}'")
            return
        # ----- handle parts with known stage:
        self.skipthis = course.include_stage_index > stage_index

    def read_partsfile(self, file: str):
        """
        Reads files consisting of YAML metadata, then Markdown text, separated by a tiple-dash line.
        Stores metadata into self.metadata, rest into self.content.
        """
        SEPARATOR = "---\n"
        # ----- obtain file contents:
        self.sourcefile = file
        text = b.slurp(file)
        if SEPARATOR not in text:
            b.error(f"{self.sourcefile}: triple-dash separator is missing")
            return
        self.metadata_text, self.content = text.split(SEPARATOR, 1)
        # ----- parse metadata
        try:
            # ----- parse YAML data:
            self.metadata = yaml.safe_load(self.metadata_text)
        except yaml.YAMLError as exc:
            b.error(f"{self.sourcefile}: metadata YAML is malformed: {str(exc)}")
            self.metadata = dict()  # use empty metadata as a weak replacement


class Zipdir(Structurepart):
    """
    Turn directories named ch/mychapter/mytaskgroup/myzipdir.zip 
    containing a tree of files, say, myfile.txt
    into an output file myzipdir.zip
    that contains paths like myzipdir/myfile.txt.  
    """
    innerpath: str  # relative pathname of the zipdir, to be re-created in the ZIP archive

    def __init__(self, zipdirpath: str):
        assert zipdirpath[-1] != '/'  # dirprefix must not end with a slash, else our logic would break
        self.sourcefile = zipdirpath  # e.g. ch/mychapter/mytaskgroup/myzipdir.zip 
        self.slug = self.title = self.outputfile = os.path.basename(zipdirpath)  # e.g. myzipdir.zip
        self.innerpath = self.slug[:-len(".zip")]  # e.g. myzipdir

    @property
    def to_be_skipped(self) -> bool:
        return False  # TODO 3: within course(!) could be skipped if no [PARTREF] to it exists anywhere

    def render(self, targetdir: str):
        with zipfile.ZipFile(f"{targetdir}/{self.outputfile}", mode='w', 
                             compression=zipfile.ZIP_DEFLATED) as archive:  # prefer deflate for build speed
            self._zip_the_files(archive)

    def _zip_the_files(self, archive: zipfile.ZipFile):
        assert os.path.exists(self.sourcefile), f"'{self.sourcefile}' is missing!"
        for dirpath, dirnames, filenames in os.walk(self.sourcefile):
            for filename in sorted(filenames):
                sourcename = f"{dirpath}/{filename}"
                targetname = self._path_in_zip(sourcename)
                archive.write(sourcename, targetname)

    def _path_in_zip(self, sourcename: str) -> str:
        """
        Remove outside-of-zipdir prefix, then use innerpath plus inside-of-zipdir remainder.
        """
        slugpos = sourcename.find(self.slug)  # will always exist
        remainder = sourcename[slugpos+len(self.slug)+1:]
        return f"{self.innerpath}/{remainder}"


class Partscontainer(Structurepart):
    """A Structurepart that can contain other Structureparts."""
    zipdirs: list[Zipdir] = []
    
    def find_zipdirs(self):
        """find all dirs (not files!) *.zip in self.sourcefile dir (not below!), warns about *.zip files"""
        self.zipdirs = []
        inputdir = os.path.dirname(self.sourcefile)
        zipdirs = glob.glob(f"{inputdir}/*.zip")
        for zipdirname in zipdirs:
            if os.path.isdir(zipdirname):
                self.zipdirs.append(Zipdir(zipdirname))
            else:
                b.warning(f"'{zipdirname}' is a file, not a dir, and will be ignored.")

    def render_zipdirs(self, targetdir):
        for zipdir in self.zipdirs:
            zipdir.render(targetdir)
