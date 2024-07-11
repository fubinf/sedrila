"""
Class model for the stuff taking part in the incremental build.
See the architecture description in README.md.
"""

import collections.abc
import glob
import os.path
import shutil
import typing as tg
import zipfile

import yaml

import base as b
import cache as c
import sdrl.directory as dir
import sdrl.html as h
import sdrl.macros as macros
import sdrl.markdown as md


class Top:  # abstract class
    """This class' only purpose is terminating the super().__init__() call chain."""
    def __init__(self, *args, **kwargs):
        pass  # because object() does not support the (self, *args, **kwargs) signature


class Element(Top):  # abstract class
    """
    Common superclass of the stuff taking part in incremental build: Sources and Products.
    Directory defines an ordering of these classes A, B, C such that if any B has any A as a dependency,
    A will be before B in the ordering. This allows building Elements simply in order A, B, C, ...
    build() is mostly generic and consists of calls to the class-specific framework filler methods
    check_existing_resource(), my_dependencies() and do_build().
    """
    name: str  # path, filename, or partname
    state: c.State
    cache: c.SedrilaCache
    directory: dir.Directory

    def __init__(self, name: str, *args, **kwargs):
        self.name = name
        super().__init__(name, *args, **kwargs)  # many classes inherit this constructor!
        for key, val in kwargs.items():
            setattr(self, key, val)  # store all keyword args in same-named attr

    @property
    def cache_key(self) -> str:
        return f"{self.name}__{self.__class__.__name__.lower()}__"  # e.g. MyPart__body_i__

    @property
    def statelabel(self) -> str:
        f"{self.state}{'*' if isinstance(self, Byproduct) else ''}"

    @property
    def my_course(self):
        import sdrl.course
        return self.directory.get_the(sdrl.course.Course, 'Course')

    def build(self):
        """Generic framework operation."""
        self.check_existing_resource()
        if self.state != c.State.AS_BEFORE:
            b.debug(f"{self.__class__.__name__}.build({self.name}) local state:\t{self.statelabel} ")
            self.do_build()
            self.state = c.State.HAS_CHANGED
            return
        for dep in self.my_dependencies():
            if dep.state != c.State.AS_BEFORE:
                which = f"{dep.__class__.__name__}({dep.name})"
                b.debug(f"{self.__class__.__name__}.build({self.name}) dependency {which} state:\t{dep.statelabel}")
                self.do_build()
                self.state = c.State.HAS_CHANGED
                return
        b.debug(f"{self.__class__.__name__}.build({self.name}) state:\t{self.state}")

    def check_existing_resource(self):
        """
        Category-specific: To be implemented differently in Source, Piece, Outputfile.
        Set state==MISSING if no resource exists,
        set state==HAS_CHANGED if Source has changed (check may involve cache),
        set state==AS_BEFORE (and perhaps read Piece from cache) otherwise.
        """
        assert False, f"{self.__class__.__name__}.{self.name}.check_existing_resource() not defined"

    def my_dependencies(self) -> tg.Iterable['Element']:
        """Class-specific. Either fixed (and enumerated here) or stored in 'dependencies'."""
        return []  # default: no dependencies

    def do_build(self):
        """Class-specific: perform actual build work."""
        assert False, f"{self.__class__.__name__}.{self.name}.do_build() not defined"

    def cached_str(self) -> tuple[str, c.State]:
        return self.cache.cached_str(self.cache_key)

    def cached_list(self) -> tuple[list[str], c.State]:
        return self.cache.cached_list(self.cache_key)

    def cached_dict(self) -> tuple[b.StrAnyDict, c.State]:
        return self.cache.cached_dict(self.cache_key)



class Product(Element):  # abstract class
    """Abstract superclass for any kind of thing that gets built."""
    pass


class Piece(Product):  # abstract class
    """
    Abstract superclass for an internal outcome of build, managed in the cache or with help of the cache.
    Pieces have a value that is set by check_existing_resource() (if in the cache) or by do_build()
    or both.
    """
    CACHED_TYPE = 'str'  # which kind of value is in the cache
    SC = c.SedrilaCache  # abbrev
    READFUNC = dict(str=SC.cached_str, list=SC.cached_list, dict=SC.cached_dict)
    WRITEFUNC = dict(str=SC.write_str, list=SC.write_list, dict=SC.write_dict)
    value: c.Cacheable  # build result, from Cache or from do_build()
    
    @property
    def cache_key(self) -> str:
        return f"{self.name}__{self.__class__.__name__.lower()}__"

    def check_existing_resource(self):
        value, self.state = self.READFUNC[self.CACHED_TYPE](self.cache, self.cache_key)
        if value is not None:
            assert self.state == c.State.AS_BEFORE  # cache write happens only later
            self.value = value  # do not set it to None

    def encache_built_value(self, value):
        """
        Where Outputfile elements directly produce an effect during do_build(),
        Pieces only live in the cache. This method puts them there and sets value.
        However, a freshly built value is still AS_BEFORE if it is the same as in the cache.
        """
        self.value = value
        cache_value, cache_state = self.READFUNC[self.CACHED_TYPE](self.cache, self.cache_key)
        if cache_state != c.State.MISSING and self.value == cache_value:
            self.state = c.State.AS_BEFORE
        else: 
            self.state = c.State.HAS_CHANGED
            self.WRITEFUNC[self.CACHED_TYPE](self.cache, self.cache_key, self.value)

    def has_value(self) -> bool:
        return hasattr(self, 'value')


class Byproduct(Piece):  # abstract class
    """
    A Byproduct gets built not by its own do_build() but by its main Product's,
    which must be built first and will set the Byproduct's 'value' attr and cache entry.
    Byproduct.do_build() only verifies that value is set.
    check_existing_resource() retrieves the cache entry iff value is not set (when the
    main Product did not need to be built).
    Byproducts rely on their main Product's dependency checking; they have no dependenies of their own. 
    """
    def check_existing_resource(self):
        if self.has_value():  # if main product was built, all is done already
            pass 
        else:  # main product was not built, need to read cache
            super().check_existing_resource()
            assert self.has_value() or self.state == c.State.MISSING

    def my_dependencies(self) -> list[Element]:
        return []

    def do_build(self):
        pass  # Byproducts get built by their corresponding main product


class Body_s(Piece):
    """Student HTML page text content.  Byproducts: Body_i, IncludeList_s, IncludeList_i."""
    sourcefile: str

    def do_build(self):
        # --- prepare:
        macros.switch_part(self.name)
        content = self.directory.get_the(Content, self.name)
        # --- build body_s and byproduct includeslist_s:
        # includeslist_s gets filled when building self, but is a dependency of self!
        # As a dependency, it gets built earlier, so the includes_s found here will come into effect
        # only during the next run, via the cache.
        includeslist_s = self.directory.get_the(IncludeList_s, self.name)
        html, includes_s = md.render_markdown(self.sourcefile, self.name, 
                                              content.value, b.Mode.STUDENT, 
                                              self.my_course.blockmacro_topmatter)
        self.encache_built_value(html)
        includeslist_s.encache_built_value(includes_s)
        # --- build byproducts body_i and includeslist_i:
        body_i = self.directory.get_the(Body_i, self.name)
        includeslist_i = self.directory.get_the(IncludeList_i, self.name)
        html, includes_i = md.render_markdown(self.sourcefile, self.name, 
                                              content.value, b.Mode.INSTRUCTOR, 
                                              self.my_course.blockmacro_topmatter)
        body_i.encache_built_value(html)
        includeslist_i.encache_built_value(includes_i)

    def my_dependencies(self) -> list[Element]:
        return [
            self.directory.get_the(Content, self.name),
            self.directory.get_the(IncludeList_s, self.name),
            self.directory.get_the(IncludeList_i, self.name),
        ]


class Body_i(Byproduct, Body_s):
    """Just like Body_s, but for instructor HTML. Byproduct of Body_s."""
    pass  # all functionality is generic, see Body_s.build()


class Content(Byproduct):
    """Markdown part of a Part sourcefile. Byproduct of Topmatter."""
    pass


class ItemList(Byproduct):  # abstract class
    """Abstract superclass for lists of names of dependencies."""
    CACHED_TYPE = 'list'  # which kind of value is in the cache
    dependencies: list['Element']
    pass


class AssumedByList(ItemList):
    """List of names of Parts that assume this Part."""
    pass


class IncludeList_s(ItemList):
    """List of names of files INCLUDEd by a Part in its student version."""
    def __init__(self, name: str, *args, **kwargs):
        super().__init__(name, *args, **kwargs)
        includelist, state = self.cached_list()
        if state == c.State.MISSING:
            return
        self.dependencies = []
        for includefile in includelist:
            self.dependencies.append(self.directory.make_or_get_the(Sourcefile, includefile, cache=self.cache))

    def my_dependencies(self) -> tg.Iterable['Element']:
        return self.dependencies


class IncludeList_i(IncludeList_s):
    """List of names of files INCLUDEd by a Part in its instructor version."""
    pass  # all functionality is generic


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
    """Metadata from a Part file. Byproduct: Content."""
    CACHED_TYPE = 'dict'  # which kind of value is in the cache
    sourcefile: str
    
    def do_build(self):
        SEPARATOR = "---\n"
        content_elem = self.directory.get_the(Content, self.name)  # our byproduct
        # ----- obtain file contents:
        text = b.slurp(self.sourcefile)
        if SEPARATOR not in text:
            b.error(f"{self.sourcefile}: triple-dash separator is missing")
            return
        topmatter_text, content_text = text.split(SEPARATOR, 1)
        # ----- parse metadata
        try:
            value = yaml.safe_load(topmatter_text) or dict()  # avoid None for empty topmatter
        except yaml.YAMLError as exc:
            b.error(f"{self.sourcefile}: metadata YAML is malformed: {str(exc)}")
            value = dict()  # use empty metadata as a weak replacement
        # ----- use the pieces:
        self.encache_built_value(value)
        content_elem.encache_built_value(content_text)

    def my_dependencies(self) -> list['Element']:
        return [self.directory.get_the(Sourcefile, self.sourcefile)]


class Outputfile(Product):  # abstract class
    """Superclass for Products ending up in one file per targetdir."""
    targetdir_s: str  # student dir, if any
    targetdir_i: str  # instructor dir, if any
    sourcefile: str  # the originating pathname, so we can find the Sourcefile object, if any
    
    @property
    def outputfile(self) -> str:  # but different for Parts
        return self.name

    @property
    def outputfile_s(self) -> str:
        return os.path.join(self.targetdir_s, self.outputfile)

    @property
    def outputfile_i(self) -> str:
        return os.path.join(self.targetdir_i, self.outputfile)

    def build(self):
        super().build()
        if self.state != c.State.AS_BEFORE:  # do_build() was called, file was written
            self.cache.record_file(self.name)

    def check_existing_resource(self):
        sourcefile_state = self.directory.get_the(Sourcefile, self.sourcefile).state
        if not os.path.exists(self.outputfile_s) or not os.path.exists(self.outputfile_i):
            self.state = c.State.MISSING
        elif sourcefile_state == c.State.AS_BEFORE:
            self.state = c.State.AS_BEFORE
        else:
            self.state = c.State.HAS_CHANGED
        # b.debug(f"Outputfile.check({self.outputfile}): {self.state}")


class CopiedFile(Outputfile):
    """For resources which are copied verbatim. The data lives in the file system, hence no value."""
    def do_build(self):
        b.debug(f"copying '{self.sourcefile}'\t-> '{self.targetdir_s}'")
        shutil.copy(self.sourcefile, os.path.join(self.targetdir_s, self.outputfile))
        b.debug(f"copying '{self.sourcefile}'\t-> '{self.targetdir_i}'")
        shutil.copy(self.sourcefile, os.path.join(self.targetdir_i, self.outputfile))


class Part(Outputfile):  # abstract class for Course, Chapter, Taskgroup, Task and their Builders, see course.py
    """Outputs identified by a slug, possible targets of PARTREF."""
    TOC_LEVEL = 0  # indent level in table of contents
    slug: str  # the file/dir basename by which we refer to the part
    title: str  # title: value
    parent: 'Part'  # does not exist for Course
    parttype: dict[str, type['Part']]

    def __init__(self, name: str, *args, **kwargs):
        super().__init__(name, *args, **kwargs)
        self.slug = self.name
        if getattr(self, 'parent', None):  # inherit parent attrs, to make X and XBuilder simpler:
            self.cache = self.parent.cache
            self.directory = self.parent.directory
            self.parttype = self.parent.parttype
            self.targetdir_s = self.parent.targetdir_s
            self.targetdir_i = self.parent.targetdir_i

    def __repr__(self):
        return self.name

    @property
    def outputfile_s(self) -> str:
        return f"{self.name}.html"

    def check_existing_resource(self):
        self.state = c.State.AS_BEFORE  # Parts' state changes all come from dependencies

    def render_structure(self, templatename: str, sitetitle: str, 
                         toc: str, body: str, linkslist_top: str, linkslist_bottom: str, 
                         targetdir: str):
        template = self.my_course.get_template(templatename)
        output = template.render(sitetitle=sitetitle,
                                 breadcrumb=h.breadcrumb(*self.structure_path()[::-1]),
                                 title=self.title,
                                 linkslist_top=linkslist_top,
                                 linkslist_bottom=linkslist_bottom,
                                 part=self,
                                 toc=toc,
                                 content=body)
        b.spit(f"{targetdir}/{self.outputfile}", output)
        b.info(f"{targetdir}/{self.outputfile}")

    def structure_path(self) -> list['Part']:
        """List of nested parts, from a given part up to the course."""
        import sdrl.course
        structure = self
        path = []
        if isinstance(structure, sdrl.course.Task):
            path.append(structure)
            structure = structure.taskgroup
        if isinstance(structure, sdrl.course.Taskgroup):
            path.append(structure)
            structure = structure.chapter
        if isinstance(structure, sdrl.course.Chapter):
            path.append(structure)
            structure = structure.course
        if isinstance(structure, sdrl.course.Course):
            path.append(structure)
        return path

class Partscontainer(Part):  # abstract class
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


class Source(Element):  # abstract class
    """
    Abstract superclass for an input for the build.
    A Source only provides a state, not a Product, hence no build action and no value.
    The data resides either in the file system or is supplied upon instantiation. 
    """
    def do_build(self):
        pass  # 

    def needs_value(self) -> bool:
        return True  # value is always missing


class Sourcefile(Source):
    """A Source that consists of a single file. Its name is the sourcefile's full path."""
    def __init__(self, name, *args, **kwargs):
        super().__init__(name, *args, **kwargs)
        assert name

    def check_existing_resource(self):
        self.state = self.cache.filestate(self.name)

    def do_build(self):
        if self.state != c.State.AS_BEFORE:
            self.cache.record_file(self.name)


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
