"""Represent and handle the contents of the sedrila.yaml config file: course, Chapter, Taskgroup."""

import functools
import os
import re
import typing as tg

import base as b
import sdrl.html as h
import sdrl.markdown as md

METADATA_FILE = "course.json"  # in student build directory

class Task:
    DIFFICULTY_RANGE = range(1, len(h.difficulty_levels) + 1)

    srcfile: str  # the originating pathname
    metadata_text: str  # the YAML front matter character stream
    metadata: b.StrAnyMap  # the YAML front matter
    content: str  # the markdown block
    slug: str  # the key by which we access the Task object

    title: str  # title: value
    description: str  # description: value (possibly multiple lines)
    timevalue: tg.Union[int, float]  # task timevalue: (in hours)
    difficulty: str  # difficulty: value (one of Task.difficulty_levels)
    assumes: tg.Sequence[str] = []  # tasknames: This knowledge is assumed to be present
    requires: tg.Sequence[str] = []  # tasknames: These specific results will be reused here
    workhours: float = 0.0  # time student has worked on this according to commit msgs
    accepted: bool = False  # whether instructor has ever marked it 'accept'
    rejections: int = 0  # how often instructor has marked it 'reject'

    taskgroup: str  # where the task belongs

    def __init__(self, file: str, text: str = None, 
                 taskgroup: tg.Optional['Taskgroup']=None, task: tg.Optional[b.StrAnyMap]=None):
        """Reads task from a file or multiline string or initializes via from_json."""
        if taskgroup:
            assert not file
            self.from_json(taskgroup, task)
            return
        b.read_partsfile(self, file, text)
        # ----- get taskdata from filen:
        nameparts = os.path.basename(self.srcfile).split('.')
        assert len(nameparts) == 2  # taskname, suffix 'md'
        self.slug = nameparts[0]  # must be globally unique
        b.copyattrs(self.metadata, self,
                    mustcopy_attrs='title, description, timevalue, difficulty',
                    cancopy_attrs='assumes, requires',
                    mustexist_attrs='')
        # ----- ensure assumes and requires are lists:
        if isinstance(self.assumes, str):
            self.assumes = re.split(r", *", self.assumes)
        if isinstance(self.requires, str):
            self.requires = re.split(r", *", self.requires)

    @property
    def breadcrumb_item(self) -> str:
        return f"<a href='{self.outputfile}'>{self.slug}</a>"

    @property
    def inputfile(self) -> str:
        return self.srcfile

    @property
    def outputfile(self) -> str:
        return f"{self.name}.html"

    @property
    def name(self) -> str:
        return self.slug

    @property
    def toc_link_text(self) -> str:
        description = h.as_attribute(self.description)
        href = f"href='{self.outputfile}'"
        titleattr = f"title=\"{description}\""
        diffsymbol = h.difficulty_symbol(self.difficulty)
        timevalue = f"<span title='Timevalue: {self.timevalue} hours'>{self.timevalue}h"
        return f"<a {href} {titleattr}>{self.title}</a> {diffsymbol} {timevalue}"

    def as_json(self) -> b.StrAnyMap:
        return dict(slug=self.slug,
                    title=self.title, timevalue=self.timevalue, difficulty=self.difficulty,
                    assumes=self.assumes, requires=self.requires)

    def from_json(self, taskgroup: 'Taskgroup', task: b.StrAnyMap):
        """Alternative constructor."""
        self.taskgroup = taskgroup
        self.slug = task['slug']
        self.title = task['title']
        self.timevalue = task['timevalue']
        self.difficulty = task['difficulty']
        self.assumes = task['assumes']
        self.requires = task['requires']

    def toc_link(self, level=0) -> str:
        return h.indented_block(self.toc_link_text, level)

    def _as_list(self, obj) -> tg.List:
        return obj if isinstance(obj, list) else list(obj)

    @classmethod
    def expand_diff(cls, call: md.Macrocall, name: str, arg1: str, arg2: str) -> str:
        assert name == "DIFF"
        level = int(arg1)
        diffrange = cls.DIFFICULTY_RANGE
        if not level in diffrange:
            call.error(f"Difficulty must be in range {min(diffrange)}..{max(diffrange)}")
            return ""
        return h.difficulty_symbol(level)


md.register_macros(('DIFF', 1, Task.expand_diff))


class Item:
    """Common superclass for course, Chapter, Taskgroup (but not Task, although similar)."""
    title: str
    shorttitle: str
    metadata: b.StrAnyMap  # the YAML front matter
    content: str
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
    instructors: tg.List[b.StrAnyMap]
    chapters: tg.Sequence['Chapter']
    
    def __init__(self, configfile: str, read_contentfiles: bool):
        configdict = b.slurp_yaml(configfile)
        b.copyattrs(configdict, self,
                    mustcopy_attrs='title, shorttitle, instructors',
                    cancopy_attrs='baseresourcedir, chapterdir, templatedir',
                    mustexist_attrs='chapters')
        if read_contentfiles:
            b.read_partsfile(self, self.inputfile)
        self.chapters = [Chapter(self, ch, read_contentfiles) for ch in configdict['chapters']]
        self.register_macros()

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
                      instructors=self.instructors,
                      chapters=[chapter.as_json() for chapter in self.chapters])
        result.update(super().as_json())
        return result

    def task(self, taskname: str) -> tg.Optional[Task]:
        """Return Task for given taskname or None if it no such task exists."""
        return self.taskdict.get(taskname)

    def all_tasks(self) -> tg.Generator[Task, None, None]:
        for chapter in self.chapters:
            for taskgroup in chapter.taskgroups:
                for task in taskgroup.tasks:
                    yield task
    
    def register_macros(self):
        ...

    def volume_report_per_chapter(self) -> tg.Sequence[tg.Tuple[str, int, float]]:
        """Tuples of (chaptername, num_tasks, timevalue_sum)"""
        result = []
        for chapter in self.chapters:
            num_tasks = sum((1 for t in self.all_tasks() if t.taskgroup.chapter == chapter))
            timevalue_sum = sum((t.timevalue for t in self.all_tasks() if t.taskgroup.chapter == chapter))
            result.append((chapter.shorttitle, num_tasks, timevalue_sum))
        return result

    def volume_report_per_difficulty(self) -> tg.Sequence[tg.Tuple[int, int, float]]:
        """Tuples of (difficulty, num_tasks, timevalue_sum)"""
        result = []
        for difficulty in Task.DIFFICULTY_RANGE:
            num_tasks = sum((1 for t in self.all_tasks() if t.difficulty == difficulty))
            timevalue_sum = sum((t.timevalue for t in self.all_tasks() if t.difficulty == difficulty))
            result.append((difficulty, num_tasks, timevalue_sum))
        return result


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
                    cancopy_attrs='tasks',
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
            self.tasks = [Task(file=None, taskgroup=self, task=task) for task in taskgroup['tasks']]

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
