"""
Class model for the stuff taking part in the incremental build.
Read the architecture description in docs/internal_notes.md first.

The items involved in the build process as inputs, outputs, intermediate products, 
or non-product pure-computation work steps are called Element.
They are arranged in the following inheritance hierarchy:

```
Element
  Product
    Piece
      Body
          Body_s
          Body_i
          Glossarybody
      Byproduct
        Content
        ItemList
          IncludeList_s
          IncludeList_i
          TermrefList
      FreshPiece
        LinkslistBottom
        Tocline
      Toc
      Topmatter
    Outputfile
      CopiedFile
      Part
        Partscontainer
          Course
          Chapter
          Taskgroup
        Task
        Glossary
        Zipfile
  Source
    Configelement
    Sourcefile
    Zipdir
  Step
    DerivedMetadata
```


## How states drive the build

Any element can be `AS_BEFORE` or `HAS_CHANGED` or `MISSING` (the latter not for `Sources`).
These are defined in `cache.State`.
If the element is `MISSING`, it will be built, which turns the state into `HAS_CHANGED`.
If it `HAS_CHANGED`, it will be re-built.
If it is `AS_BEFORE`, it will be re-built only if a dependency `HAS_CHANGED`.


## Methods involved in the build

The above three state-related rules are implemented by the framework method `Element.build()`,
which relies on three Element-type-specific methods:  
- `check_existing_resource()` performs the state check by means of the cache.
- `my_dependencies()` returns the Elements this Element depends on.
- `do_build()` implements the actual build step for this particular type of element.


## How data are represented in the cache

`Steps` and `Outputfiles` need and have no cache representation.

`Pieces` have a `value` that is stored in the cache;
it is either a `str` or a `list[str]` or a `b.StrAnyDict`.

`Sources` are represented in the cache only by cache keys, with an empty value.
This serves to determine their state:
- cache key missing: `MISSING`.
- cache key written to cache in the present run: `HAS_CHANGED`.
- cache key is in persistent cache from a previous run: `AS_BEFORE` or `HAS_CHANGED`, 
  depending on the file's mtime (or file tree's youngest mtime).


## How data are represented in the build

`Elements` all have a number of attributes for management purposes, see the `Element` class.
Most are submitted to the constructor call, but for convenience, 
some of these are inherited via a `part` attribute.
In contrast to these purely organizational data, there is _substantial_ data that supports the
specific purpose of each type of element:

`Steps` are pure computation. They modify the data of `Parts`, but have no data representation themselves.

`CopiedFiles` are represented by their file only.

`Parts` are represented by a complex object as defined in `course.py`.
This object is created at initialization time, perhaps modified during a `Step`,
and turned into a file during `do_build()`, when that is called.

`Pieces` are represented by their `value` attribute as described above.


## Special Element types

All Element types in principle follow the build logic described under "methods involved" above.
However, some do it in an odd way:

`Byproducts` have no `do_build()` themselves and so never set their own `value` themselves.
Instead, their `value` is set by some other `Piece`'s `do_build()`.

`FreshPieces` do not use the cache to retrieve a previous value if they are `AS_BEFORE`.
Instead, they _always_ retrieve the previous value, _always_ re-build themselves, and then compare
the two in order to determine whether they are `AS_BEFORE` or `HAS_CHANGED`.
This means the build step happens in `check_existing_resource()` and `do_build()` only writes
a changed outcome to the cache.
"""

import os.path
import shutil
import typing as tg
import zipfile

import yaml

import base as b
import cache as c
import sdrl.directory as dir
import sdrl.macros as macros
import sdrl.markdown as md


class Element:  # abstract class
    """
    Common superclass of the stuff taking part in incremental build: Sources and Products.
    Directory defines an ordering of these classes A, B, C such that if any B has any A as a dependency,
    A will be before B in the ordering. This allows building Elements simply in order A, B, C, ...
    build() is mostly generic and consists of calls to the class-specific framework filler methods
    check_existing_resource(), my_dependencies() and do_build().
    """
    name: str  # path, filename, or partname
    part: 'Part'  # where to find inherited attrs, only set for non-Parts
    directory: dir.Directory  # inherited
    sourcefile: str  # path, inherited
    state: c.State
    dependencies: list['Element']

    def __init__(self, name: str, *args, **kwargs):
        self.name = name
        self.dependencies = []
        for key, val in kwargs.items():
            setattr(self, key, val)  # store all keyword args in same-named attr
        self._inherit_from_part()

    def __repr__(self):
        return self.cache_key

    @property
    def cache(self) -> c.SedrilaCache:
        return self.directory.cache

    @property
    def cache_key(self) -> str:
        return f"{self.name}__{self.__class__.__name__.lower()}__"  # e.g. MyPart__body_i__

    @property
    def statelabel(self) -> str:
        return f"{self.state}{'*' if isinstance(self, Byproduct) else ''}"

    def build(self):
        """Generic framework operation."""
        self.check_existing_resource()
        if self.state != c.State.AS_BEFORE:
            b.debug(f"{self.__class__.__name__}.build({self.name}) local state:\t{self.statelabel} ")
            do_it()
            return
        for dep in self.my_dependencies():
            if dep.state != c.State.AS_BEFORE:
                which = f"{dep.__class__.__name__}({dep.name})"
                b.debug(f"{self.__class__.__name__}.build({self.name}) dependency {which} state:\t{dep.statelabel}")
                do_it()
                return
        # b.debug(f"{self.__class__.__name__}.build({self.name}) state:\t{self.statelabel}")

    def check_existing_resource(self):
        """
        Category-specific: To be implemented differently in Source, Piece, Outputfile.
        Set state==MISSING if no resource exists,
        set state==HAS_CHANGED if Source has changed (check may involve cache),
        set state==AS_BEFORE (and perhaps read Piece from cache) otherwise.
        """
        assert False, f"{self.__class__.__name__}.{self.name}.check_existing_resource() not defined"

    def my_dependencies(self) -> tg.Iterable['Element']:
        return self.dependencies

    def do_build(self):
        """Class-specific: perform actual build work."""
        assert False, f"{self.__class__.__name__}.do_build({self.name}) not defined"

    def add_dependency(self, dep: 'Element'):
        self.dependencies.append(dep)

    def cached_str(self) -> tuple[str, c.State]:
        return self.cache.cached_str(self.cache_key)

    def cached_list(self) -> tuple[list[str], c.State]:
        return self.cache.cached_list(self.cache_key)

    def cached_set(self) -> tuple[set[str], c.State]:
        return self.cache.cached_set(self.cache_key)

    def cached_dict(self) -> tuple[b.StrAnyDict, c.State]:
        return self.cache.cached_dict(self.cache_key)

    def _inherit_from_part(self):
        if getattr(self, 'part', None):  # inherit attrs, to make construction simpler:
            self.directory = self.part.directory
            self.sourcefile = self.part.sourcefile
            self.course = self.part.course


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
    READFUNC = dict(str=SC.cached_str, list=SC.cached_list, set=SC.cached_set, dict=SC.cached_dict)
    WRITEFUNC = dict(str=SC.write_str, list=SC.write_list, set=SC.write_set, dict=SC.write_dict)
    value: c.Cacheable  # build result, from Cache or from do_build()
    
    def check_existing_resource(self):
        value, self.state = self.READFUNC[self.CACHED_TYPE](self.cache, self.cache_key)
        if value is not None:
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
        b.debug(f"encache_built_value({self.cache_key}, c:{b.caller()}): "
                f"cache: {cache_state},{'same' if self.value == cache_value else 'different'}_value"
                f" --> {self.state}")

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

    def check_existing_resource(self):
        super().check_existing_resource()
        if self.cache.is_dirty(self.sourcefile):
            self.state = c.State.HAS_CHANGED  # force re-build for previous dirty files

    def do_build(self):
        # --- prepare:
        content = self.directory.get_the(Content, self.name)
        # --- build body_s and byproduct includeslist_s:
        # includeslist_s gets filled when building self, but is a dependency of self!
        # As a dependency, it gets built earlier, so the includes_s found here will come into effect
        # only during the next run, via the cache.
        includeslist_s = self.directory.get_the(IncludeList_s, self.name)
        macros.switch_part(self.name)
        mddict = md.render_markdown(self.sourcefile, self.name, content.value, b.Mode.STUDENT, 
                                    self.course.blockmacro_topmatter)
        html, includes_s, termrefs_s = (mddict['html'], mddict['includefiles'], mddict['termrefs'])
        self.encache_built_value(html)
        includeslist_s.encache_built_value(includes_s)
        # --- build byproducts body_i and includeslist_i:
        body_i = self.directory.get_the(Body_i, self.name)
        includeslist_i = self.directory.get_the(IncludeList_i, self.name)
        macros.switch_part(self.name)  # again, to reset the counters
        mddict = md.render_markdown(self.sourcefile, self.name, content.value, b.Mode.INSTRUCTOR, 
                                    self.course.blockmacro_topmatter)
        html, includes_i, termrefs_i = (mddict['html'], mddict['includefiles'], mddict['termrefs'])
        body_i.encache_built_value(html)
        includeslist_i.encache_built_value(includes_i)
        # --- build byproduct termreflist:
        termrefs = list(termrefs_s | termrefs_i)
        if len(termrefs) > 0:  # this part has at least 1 TERMREF: create a TermrefList for it
            termreflist = self.directory.make_the(TermrefList, self.name, 
                                                  part=self.part)  # implicit dependency of glossary
            termreflist.encache_built_value(termrefs)

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


class ItemList(DependenciesMixin, Byproduct):  # abstract class
    """Abstract superclass for lists of names of dependencies."""
    CACHED_TYPE = 'list'  # which kind of value is in the cache


class IncludeList_s(ItemList):
    """List of names of files INCLUDEd by a Part in its student version."""
    def __init__(self, name: str, *args, **kwargs):
        super().__init__(name, *args, **kwargs)
        includelist, state = self.cached_list()
        if state == c.State.MISSING:
            return
        for includefile in includelist:
            self.add_dependency(self.directory.make_or_get_the(Sourcefile, includefile, 
                                                               part=self.part, posthoc=True))


class IncludeList_i(IncludeList_s):
    """List of names of files INCLUDEd by a Part in its instructor version."""
    pass  # all functionality is generic


class TermrefList(ItemList):
    """
    List of names of terms TERMREF'd by Part or term self.name.
    Many of these will be empty, therefore TermrefList objects are created only if needed.
    They are implicit dependencies of the Glossary.
    """
    pass


class Toc(DependenciesMixin, Piece):
    """HTML for the toc of a Part."""
    part: 'Part'

    def do_build(self):
        self.value = self.part.toc
        self.encache_built_value(self.value)

    def add_tocline(self, task: 'sdrl.course.Task'):
        self.add_dependency(self.directory.make_or_get_the(Tocline, task.name, task=task))  # noqa


class FreshPiece(Piece):
    """Pieces of Tasks that are always built. The cache only determines whether it has changed."""
    FRESH_ATTR = '?'  # attr of task that represents the piece's value
    part: 'sdrl.course.Taskbuilder'

    def check_existing_resource(self):
        cached_value, cached_state = self.READFUNC[self.CACHED_TYPE](self.cache, self.cache_key)
        self.value = getattr(self.part, self.FRESH_ATTR)  # in fact freshly built
        if cached_value is None:
            self.state = c.State.MISSING
        elif cached_value == self.value:
            self.state = c.State.AS_BEFORE
        else:
            self.state = c.State.HAS_CHANGED
        # b.debug(f"{self.__class__.__name__}({self.name}).state = {self.state}")

    def do_build(self):
        # self.value is already set to the current value by check_existing_resource
        self.encache_built_value(self.value)


class Tocline(FreshPiece):
    """HTML for the toc entry of a Task."""
    FRESH_ATTR = 'toc_link_text'


class LinkslistBottom(FreshPiece):
    """HTML for the assumedBy/requiredBy links of a Task."""
    FRESH_ATTR = 'linkslist_bottom'


class Topmatter(Piece):
    """Metadata from a Part file. Byproduct: Content."""
    CACHED_TYPE = 'dict'  # which kind of value is in the cache
    
    def do_build(self):
        SEPARATOR = "---\n"
        content_elem = self.directory.get_the(Content, self.name)  # our byproduct
        # ----- obtain file contents:
        text = b.slurp(self.sourcefile)
        if SEPARATOR not in text:
            b.error(f"triple-dash separator is missing", file=self.sourcefile)
            return
        topmatter_text, content_text = text.split(SEPARATOR, 1)
        # ----- parse metadata
        try:
            value = yaml.safe_load(topmatter_text) or dict()  # avoid None for empty topmatter
        except yaml.YAMLError as exc:
            b.error(f"metadata YAML is malformed: {str(exc)}", file=self.sourcefile)
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
            self.cache.record_file(self.name, self.cache_key)

    def check_existing_resource(self):
        if not os.path.exists(self.outputfile_s) or not os.path.exists(self.outputfile_i):
            self.state = c.State.MISSING
        else:
            self.state = c.State.AS_BEFORE


class CopiedFile(Outputfile):
    """For resources which are copied verbatim. The data lives in the file system, hence no value."""
    def do_build(self):
        b.debug(f"copying '{self.sourcefile}'\t-> '{self.targetdir_s}'")
        shutil.copy(self.sourcefile, self.outputfile_s)
        b.debug(f"copying '{self.sourcefile}'\t-> '{self.targetdir_i}'")
        shutil.copy(self.sourcefile, self.outputfile_i)


class Part(Outputfile):  # abstract class for Course, Chapter, Taskgroup, Task and their Builders, see course.py
    """Outputs identified by a slug, possible targets of PARTREF."""
    TOC_LEVEL = 0  # indent level in table of contents
    slug: str  # the file/dir basename by which we refer to the part
    title: str  # title: value
    parttype: dict[str, type['Part']]  # for using X vs XBuilder for sub-Parts
    parent: 'Partscontainer'
    course: 'Coursebuilder'

    def __init__(self, name: str, *args, **kwargs):
        super().__init__(name, *args, **kwargs)
        self.slug = self.name
        if getattr(self, 'parent', None):  # inherit parent attrs, to make X and XBuilder simpler:
            self.directory = self.parent.directory
            self.course = self.parent.course
            self.parttype = self.parent.parttype
            if getattr(self.parent, 'targetdir_s', None):
                self.targetdir_s = self.parent.targetdir_s
                self.targetdir_i = self.parent.targetdir_i

    @property
    def outputfile(self) -> str:
        return f"{self.name}.html"

    @property
    def toc(self) -> str:
        return "((TOC))"  # override in concrete Part classes

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
    pass


class Zipfile(Part):
    """xy.zip Outputfiles that are named Parts, plus the exceptional case itree.zip."""
    instructor_only: bool = False

    @property
    def innerpath(self) -> str:
        return self.name[:-len(".zip")]  # e.g. myzipdir

    @property
    def outputfile(self) -> str:  # like for non-Parts
        return self.name

    @property
    def to_be_skipped(self) -> bool:
        return False  # TODO 3: should be skipped if no [PARTREF] to it exists, unless instructor_only

    def check_existing_resource(self):
        s_ok = os.path.exists(self.outputfile_s) or self.instructor_only
        i_ok = os.path.exists(self.outputfile_i)
        self.state = c.State.AS_BEFORE if s_ok and i_ok else c.State.MISSING

    def do_build(self):
        b.info(self.outputfile_i)
        with zipfile.ZipFile(self.outputfile_i, mode='w', 
                             compression=zipfile.ZIP_DEFLATED) as archive:  # prefer deflate for build speed
            self._zip_the_files(archive)
        if not self.instructor_only:
            b.info(self.outputfile_s)
            shutil.copy(self.outputfile_i, self.outputfile_s)
    
    def my_dependencies(self) -> tg.Iterable['Element']:
        return [self.directory.get_the(Zipdir, self.sourcefile)]
    
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


class Source(Element):  # abstract class
    """
    Abstract superclass for an input for the build.
    A Source only provides a state, not a Product, hence no build action and no value.
    The data resides either in the file system or is supplied upon instantiation. 
    """
    def do_build(self):
        pass  # Sources need no building, only checking


class Sourcefile(Source):
    """A Source that consists of a single file. Its name is the sourcefile's full path."""
    posthoc: bool  # flag "this object did not yet exist during the Sourcefile.build() phase" 

    def __init__(self, name, *args, **kwargs):
        super().__init__(name, *args, **kwargs)
        self.sourcefile = self.name
        if getattr(self, 'posthoc', False):
            # whenever a Sourcefile is first created when it is found as an includefile in a markdown render 
            # (i.e. on first build or for a new includefile), posthoc=True is passed to the constructor.
            # In this case, we must do cache.record_file() immediately or else the file would be considered
            # new (and may trigger lots of rebuild actions) during the next build.
            self.cache.record_file(self.sourcefile, self.cache_key)

    def check_existing_resource(self):
        self.state = self.cache.filestate(self.name, self.cache_key)
        if self.state != c.State.AS_BEFORE:
            self.cache.record_file(self.name, self.cache_key)


class Zipdir(Source):
    """A directory tree *.zip/** to be turned into a same-named ZIP file."""

    def __init__(self, zipdirpath: str, *args, **kwargs):
        super().__init__(zipdirpath, *args, **kwargs)
        assert zipdirpath[-1] != '/'  # dirprefix must not end with a slash, else our logic would break
        self.sourcefile = zipdirpath  # e.g. ch/mychapter/mytaskgroup/myzipdir.zip 
        self.slug = self.title = os.path.basename(zipdirpath)  # e.g. myzipdir.zip

    def check_existing_resource(self):
        """HAS_CHANGED if any file in the tree is new or the set of filenames differs from cache."""
        # ----- analyze Zipdir tree:
        current_filelist = []
        new_file_found = False
        for dirpath, dirnames, filenames in os.walk(self.sourcefile):
            for filename in sorted(filenames):
                sourcename = f"{dirpath}/{filename}"
                if self.cache.is_recent(sourcename):
                    new_file_found = True
                current_filelist.append(sourcename)
        current_fileset = set(current_filelist)
        # ----- determine state according to changes and cache:
        old_fileslist, cache_state = self.cache.cached_list(self.cache_key)
        old_fileset = set(old_fileslist or [])
        filesets_differ = old_fileset != current_fileset
        if cache_state == c.State.MISSING or new_file_found or filesets_differ:
            b.debug(f"Zipdir.check({self.name}): cache {cache_state}, new_file {new_file_found}, "
                    f"filesets differ {filesets_differ}")
            self.cache.write_list(self.cache_key, current_filelist)
            self.state = c.State.HAS_CHANGED
        else:
            self.state = c.State.AS_BEFORE


class Step(Element):
    """Pseudo-element that does not represent data, but computation."""
    def check_existing_resource(self):
        self.state = c.State.HAS_CHANGED  # do_build() must always be called.
