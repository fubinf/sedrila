"""
Class model for the stuff taking part in the incremental build.
See the architecture description in README.md.
"""

import glob
import os.path
import shutil
import zipfile

import base as b
import cache as c
import directory as d


class Element:
    """Common superclass of the stuff taking part in incremental build: Sources and Products."""
    name: str  # path, filename, or partname
    state: c.State = c.State.UNDETERMINED
    cache: c.SedrilaCache | None
    directory: d.Directory | None

    def __init__(self, name: str, *args, **kwargs):
        self.name = name
        self.cache = self.directory = None
        for key, val in kwargs.items():
            setattr(self, key, val)  # store all keyword args in same-named attr

    def build(self):
        """Generic framework operation."""
        self.do_evaluate_state()
        if self.state != c.State.AS_BEFORE:
            self.do_build()
            self.state = c.State.HAS_CHANGED

    def do_evaluate_state(self):
        """Class-specific: Look at dependencies and perhaps cache or file to set state."""
        assert False, f"{type(self)}.do_evaluate_state() not defined"

    def do_build(self):
        """Class-specific: perform actual build work."""
        assert False, f"{type(self)}.do_build() not defined"


class Product(Element):
    """Abstract superclass for any kind of thing that gets built."""
    pass


class Piece(Product):
    """Abstract superclass for an internal outcome of build, managed in the cache or with help of the cache."""
    @property
    def cache_key(self) -> str:
        return f"{self.name}__{str(type(self)).lower()}__"


class Body_s(Piece):
    """Student HTML page text content."""
    pass


class Body_i(Body_s):
    """Just like Body_s, but for instructor HTML."""
    pass


class Content(Piece):
    """Markdown part of a Part sourcefile."""
    pass


class ItemList(Piece):
    """Abstract superclass for lists of names of dependencies."""
    pass


class AssumedByList(ItemList):
    """List of names of Parts that assume this Part."""
    pass


class IncludeList(ItemList):
    """List of names of files INCLUDEd by a Part."""
    pass


class PartrefList(ItemList):
    """List of names of Parts PARTREF'd by a Part."""
    pass


class RequiredByList(ItemList):
    """List of names of Parts that require this Part."""
    pass


class Toc(Piece):
    """HTML for the toc of a Part."""
    pass


class Tocline(Piece):
    """HTML for the toc entry of one Part."""
    pass


class Topmatter(Piece):
    """Metadata from a Part file."""
    pass


class Outputfile(Product):
    """Superclass for Products ending up in a file (or two). Also used directly, for baseresources."""
    outputfile: str  # the target pathname within the target directory
    targetdir_s: str
    targetdir_i: str
    sourcefile: 'Sourcefile' | None  # if given, build is a copy operation
    
    def do_build(self):
        b.debug(f"copying '{filename}'\t-> '{course.targetdir_s}'")
        shutil.copy(filename, course.targetdir_s)
        b.debug(f"copying '{filename}'\t-> '{course.targetdir_i}'")
        shutil.copy(filename, course.targetdir_i)

    def do_evaluate_state(self):
        ...


class Part(Outputfile):
    """Outputs identified by a slug, possible targets of PARTREF."""
    TOC_LEVEL = 0  # indent level in table of contents
    sourcefile: str = "???"  # the originating pathname
    slug: str  # the file/dir basename by which we refer to the part
    title: str  # title: value

    def __repr__(self):
        return self.slug


class Partscontainer(Part):  # for Course, Chapter, Taskgroup, Task and their Builders, see course.py
    """A Part that can contain other Parts."""
    zipdirs: list['Zipdir'] = []
    
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


class Zipfile(Part):
    """xy.zip Outputfiles that are named Parts, plus the exceptional case itree.zip."""
    pass


class RenderedOutput(Outputfile):
    """xy.html Outputfiles that stem from Parts."""
    pass


class Source(Element):
    """Abstract superclass for an input for the build."""
    def do_build(self):
        pass  # a Source only provides a state, not a Product, hence there is no build action.


class Sourcefile(Source):
    """A Source that consists of a single file."""
    sourcefile: str  # full pathname

    def do_evaluate_state(self):
        self.state = self.cache.filestate(self.sourcefile)

    def do_build(self):
        pass  # we are not a Product


class Zipdir(Source):
    """
    OLD: Turn directories named ch/mychapter/mytaskgroup/myzipdir.zip 
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


