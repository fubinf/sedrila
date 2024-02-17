"""
Common superclass for
a) Course, Chapter, Taskgroup (all via Partscontainer), and Task, all defined in course.py 
b) Glossary, defined in glossary.py
c) ZipDir
Not all attributes are needed for all parts; 
the design is a bit scruffy, which saves various intermediate superclasses.
"""

import glob
import os.path
import re
import zipfile

import yaml

import base as b
import sdrl.html as h


class Structurepart:
    """Common superclass"""
    TOC_LEVEL = 0  # indent level in table of contents
    sourcefile: str = "???"  # the originating pathname
    outputfile: str  # the target pathname
    metadata_text: str  # the YAML front matter character stream
    metadata: b.StrAnyDict  # the YAML front matter
    content: str  # the markdown block
    slug: str  # the file/dir basename by which we refer to the part
    title: str  # title: value
    linkslist: str = ''  # generated HTML of cross reference links
    stage: str = ''  # stage: value
    skipthis: bool  # do not include this chapter/taskgroup/task in generated site
    toc: str  # table of contents

    @property
    def breadcrumb_item(self) -> str:
        return "(undefined)"

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
    that contains mychapter/mytaskgroup/myzipdir/myfile.txt.  
    """
    innerpath: str  # relative pathname of the zipdir, to be re-created in the ZIP archive

    def __init__(self, dirprefix: str, dirname: str, outputdir: str):
        assert dirname.startswith(dirprefix)
        assert dirname[-1] != '/'  # dirprefix must not end with a slash, else our logic would break
        self.sourcefile = dirname
        self.slug = self.title = self.outputfile = os.path.basename(dirname)  # e.g. myfile.zip
        bareslug = self.slug[:-4]  # e.g. myfile
        innerpath1 = os.path.dirname(dirname).replace(dirprefix+'/', '', 1)
        self.innerpath = f"{innerpath1}/{bareslug}"

    def render(self, targetdir: str):
        with zipfile.ZipFile(f"{targetdir}/{self.outputfile}", mode='w') as archive:
            self._zip_the_files(archive)

    def _zip_the_files(self, archive: zipfile.ZipFile):
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
    
    def find_zipdirs(self, dirprefix: str):
        """find all dirs (not files!) *.zip in inputdir (not below!), warns about *.zip files"""
        self.zipdirs = []
        inputdir = os.path.dirname(self.sourcefile)
        outputdir = os.path.dirname(self.outputfile)
        zipdirs = glob.glob(f"{inputdir}/*.zip")
        for dirname in zipdirs:
            if os.path.isdir(dirname):
                self.zipdirs.append(Zipdir(dirprefix, dirname, outputdir))
            else:
                b.warning(f"'{dirname}' is a file, not a dir, and will be ignored.")

    def render_zipdirs(self, targetdir):
        for zipdir in self.zipdirs:
            zipdir.render(targetdir)
