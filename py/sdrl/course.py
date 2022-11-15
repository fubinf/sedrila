"""Represent and handle the contents of the sedrila.yaml config file: course, Chapter, Taskgroup."""

import functools
import json
import os
import typing as tg

import yaml

import base as b
import sdrl.html as h


METADATA_FILE = "course.json"  # in student build directory

class Task:
    srcfile: str  # the originating pathname
    metadata_text: str  # the entire YAML character stream
    metadata: b.StrAnyMap  # the YAML front matter
    content: str  # the entire first markdown block
    instructorcontent: str  # the entire second markdown block
    slug: str  # the key by which we access the Task object

    title: str  # title: value
    description: str  # description: value (possibly multiple lines)
    effort: tg.Union[int, float]  # effort: (in half hours)
    difficulty: str  # difficulty: value (one of Task.difficulty_levels)
    assumes: tg.Sequence[str] = []  # tasknames: This knowledge is assumed to be present
    requires: tg.Sequence[str] = []  # tasknames: These specific results will be reused here
    todo: tg.Sequence[tg.Any] = []  # list of potentially YAML stuff

    taskgroup: str  # where the task belongs

    def __init__(self, file: str, text: str = None):
        """Reads task from a file or multiline string."""
        b.read_partsfile(self, file, text)
        # ----- get taskname from filename:
        nameparts = os.path.basename(self.srcfile).split('.')
        assert len(nameparts) == 2  # taskname, suffix 'md'
        self.slug = nameparts[0]  # must be globally unique
        b.copyattrs(self.metadata, self,
                    mustcopy_attrs='title, description, effort, difficulty',
                    cancopy_attrs='assumes, requires, todo',
                    mustexist_attrs='')
        # ----- ensure assumes and requires are lists:
        if isinstance(self.assumes, str):
            self.assumes = [self.assumes]
        if isinstance(self.requires, str):
            self.requires = [self.requires]
        # ----- semantic checks:
        ...  # TODO 2

    @property
    def breadcrumb_item(self) -> str:
        return f"<a href='{self.outputfile}'>{self.slug}</a>"

    @property
    def outputfile(self) -> str:
        return f"{self.name}.html"

    @property
    def name(self) -> str:
        return self.slug

    def as_json(self) -> b.StrAnyMap:
        return dict(slug=self.slug,
                    title=self.title, effort=self.effort, difficulty=self.difficulty,
                    assumes=self.assumes, requires=self.requires)

    @classmethod
    def from_json(cls, taskgroup: 'Taskgroup', task: b.StrAnyMap) -> 'Task':
        """Alternative constructor."""
        self = cls.__new__()
        self.taskgroup = taskgroup
        self.slug = task['slug']
        self.title = task['title']
        self.effort = task['effort']
        self.difficulty = task['difficulty']
        self.assumes = task['assumes']
        self.requires = task['requires']
        return self

    def toc_link(self, level=0) -> str:
        description = h.as_attribute(self.description)
        href = f"href='{self.outputfile}'"
        titleattr = f"title=\"{description}\""
        diffsymbol = h.difficulty_symbol(self.difficulty)
        effort = f"<span title='Effort: {self.effort} hours'>{self.effort}h"
        return h.indented_block(f"<a {href} {titleattr}>{self.title}</a> {diffsymbol} {effort}", level)

    def _as_list(self, obj) -> tg.List:
        return obj if isinstance(obj, list) else list(obj)


class Item:
    """Common superclass for course, Chapter, Taskgroup (but not Task, although similar)."""
    title: str
    shorttitle: str
    metadata: b.StrAnyMap  # the YAML front matter
    content: str
    instructorcontent: str
    othercontent: str
    toc: str

    @property
    def breadcrumb_item(self) -> str:
        return "(undefined)"

    @property
    def inputfile(self) -> str:
        return "(undefined)"

    @property
    def outputfile(self) -> str:
        return "(undefined)"
    
    def as_json(self) -> b.StrAnyMap:
        return dict(title=self.title, shorttitle=self.shorttitle)


class Course(Item):
    """
    The master data object for this run.
    Can be initialized in two different ways: 
    - From a handwritten YAML file (read_contentfiles=True). 
      Will then read all content for a build.
    - From a metadata file generated during build (read_contentfiles=False)
      for bookkeeping/reporting.
    """
    baseresourcedir: str = 'baseresources'
    chapterdir: str = 'ch'
    templatedir: str = 'templates'
    chapters: tg.Sequence['Chapter']
    
    def __init__(self, configfile: str, read_contentfiles: bool):
        configdict: b.StrAnyMap
        configtext = b.slurp(configfile)
        if configfile.endswith('.yaml'):
            configdict = yaml.safe_load(configtext)
        elif configfile.endswith('.json'):
            configdict = json.loads(configtext)
        else:
            raise ValueError(f"unknown file type: '{configfile}'. Must be .yaml or .json")
        b.copyattrs(configdict, self,
                    mustcopy_attrs='title, shorttitle, instructors',
                    cancopy_attrs='baseresourcedir, chapterdir, templatedir',
                    mustexist_attrs='chapters')
        if read_contentfiles:
            b.read_partsfile(self, self.inputfile)
        self.chapters = [Chapter(self, ch, read_contentfiles) for ch in configdict['chapters']]

    @property
    def breadcrumb_item(self) -> str:
        titleattr = f"title=\"{h.as_attribute(self.title)}\""
        return f"<a href='welcome.html' {titleattr}>{self.shorttitle}</a>"

    @property
    def inputfile(self) -> str:
        return f"{self.chapterdir}/index.md"

    @property
    def outputfile(self) -> str:
        return "welcome.html"

    @functools.cached_property
    def taskdict(self) -> tg.Mapping[str, Task]:
        return { t.name: t for t in self.all_tasks() }
    
    def as_json(self) -> b.StrAnyMap:
        result = dict(baseresourcedir=self.baseresourcedir, 
                      chapterdir=self.chapterdir,
                      templatedir=self.templatedir,
                      chapters=[chapter.as_json() for chapter in self.chapters])
        result.update(super().as_json())
        return result

    def task(self, taskname: str) -> Task:
        return self.taskdict[taskname]

    def all_tasks(self) -> tg.Generator[Task, None, None]:
        for chapter in self.chapters:
            for taskgroup in chapter.taskgroups:
                for task in taskgroup.tasks:
                    yield task

class Chapter(Item):
    slug: str
    course: Course
    taskgroups: tg.Sequence['Taskgroup']
    
    def __init__(self, course: Course, chapter: b.StrAnyMap, read_contentfiles: bool):
        self.course = course
        b.copyattrs(chapter, self,
                    mustcopy_attrs='title, shorttitle, slug',
                    cancopy_attrs='',
                    mustexist_attrs='taskgroups')
        if read_contentfiles:
            b.read_partsfile(self, self.inputfile)
        b.copyattrs(self.metadata, self,
                    mustcopy_attrs='description',
                    cancopy_attrs='todo',
                    mustexist_attrs='', overwrite=False)
        self.taskgroups = [Taskgroup(self, taskgroup, read_contentfiles) for taskgroup in chapter['taskgroups']]

    @property
    def breadcrumb_item(self) -> str:
        titleattr = f"title=\"{h.as_attribute(self.title)}\""
        return f"<a href='{self.outputfile}' {titleattr}>{self.shorttitle}</a>"

    @property
    def inputfile(self) -> str:
        return f"{self.course.chapterdir}/{self.slug}/index.md"

    @property
    def outputfile(self) -> str:
        return f"chapter-{self.slug}.html"

    @property
    def name(self) -> str:
        return self.slug

    def as_json(self) -> b.StrAnyMap:
        result = dict(slug=self.slug, 
                      taskgroups=[taskgroup.as_json() for taskgroup in self.taskgroups])
        result.update(super().as_json())
        return result

    def toc_link(self, level=0) -> str:
        titleattr = f"title=\"{h.as_attribute(self.description)}\""
        return h.indented_block(f"<a href='{self.outputfile}' {titleattr}>{self.title}</a>", level)


class Taskgroup(Item):
    description: str
    slug: str
    chapter: Chapter
    tasks: tg.List['Task']

    def __init__(self, chapter: Chapter, taskgroup: b.StrAnyMap, read_contentfiles: bool):
        self.chapter = chapter
        b.copyattrs(taskgroup, self,
                    mustcopy_attrs='title, shorttitle, slug',
                    cancopy_attrs='',
                    mustexist_attrs='taskgroups')
        if read_contentfiles:
            b.read_partsfile(self, self.inputfile)
        b.copyattrs(self.metadata, self,
                    mustcopy_attrs='description',
                    cancopy_attrs='todo',
                    mustexist_attrs='', overwrite=False)
        if read_contentfiles:
            self.tasks = []  # will be added by reader
        else:
            self.tasks = [Task.from_json(self, task, read_contentfiles)
                          for task in taskgroup['tasks']]

    @property
    def breadcrumb_item(self) -> str:
        titleattr = f"title=\"{h.as_attribute(self.title)}\""
        return f"<a href='{self.outputfile}' {titleattr}>{self.shorttitle}</a>"

    @property
    def inputfile(self) -> str:
        return f"{self.chapter.course.chapterdir}/{self.chapter.slug}/{self.slug}/index.md"

    @property
    def outputfile(self) -> str:
        return f"{self.name}.html"

    @property
    def name(self) -> str:
        return f"{self.chapter.slug}-{self.slug}"

    def add_task(self, task: Task):
        task.taskgroup = self
        self.tasks.append(task)
    
    def as_json(self) -> b.StrAnyMap:
        result = dict(slug=self.slug, 
                      tasks=[task.as_json() for task in self.tasks])
        result.update(super().as_json())
        return result

    def toc_link(self, level=0) -> str:
        titleattr = f"title=\"{h.as_attribute(self.description)}\""
        return h.indented_block(f"<a href='{self.outputfile}' {titleattr}>{self.title}</a>", level)
