"""Represent and handle the contents of the sedrila.yaml config file: Config, Chapter, Taskgroup."""

import functools
import typing as tg

import yaml

import base as b
import sdrl.html as h
import sdrl.task

class Item:
    """Common superclass for Config (=course), Chapter, Taskgroup (but not Task, although similar)."""
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


class Config(Item):
    """The global configuration for this run."""
    baseresourcedir: str = 'baseresources'
    chapterdir: str = 'ch'
    templatedir: str = 'templates'
    chapters: tg.Sequence['Chapter']
    
    def __init__(self, configfile: str):
        yamltext = b.slurp(configfile)
        configdict: b.StrAnyMap = yaml.safe_load(yamltext)
        b.copyattrs(configdict, self,
                    m_attrs='title, shorttitle',
                    o_attrs='baseresourcedir, chapterdir, templatedir',
                    f_attrs='chapters, instructors')
        b.read_partsfile(self, self.inputfile)
        self.chapters = [Chapter(self, ch) for ch in configdict['chapters']]

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
    def taskdict(self) -> tg.Mapping[str, sdrl.task.Task]:
        return { t.name: t for t in self.all_tasks() }
    
    def task(self, taskname: str) -> sdrl.task.Task:
        return self.taskdict[taskname]

    def all_tasks(self) -> tg.Generator[sdrl.task.Task, None, None]:
        for chapter in self.chapters:
            for taskgroup in chapter.taskgroups:
                for task in taskgroup.tasks:
                    yield task

class Chapter(Item):
    slug: str
    config: Config
    taskgroups: tg.Sequence['Taskgroup']
    
    def __init__(self, config: Config, chapter: b.StrAnyMap):
        self.config = config
        b.copyattrs(chapter, self,
                    m_attrs='title, shorttitle, slug',
                    o_attrs='',
                    f_attrs='taskgroups')
        b.read_partsfile(self, self.inputfile)
        b.copyattrs(self.metadata, self,
                    m_attrs='description',
                    o_attrs='todo',
                    f_attrs='', overwrite=False)
        self.taskgroups = [Taskgroup(self, taskgroup) for taskgroup in chapter['taskgroups']]

    @property
    def breadcrumb_item(self) -> str:
        titleattr = f"title=\"{h.as_attribute(self.title)}\""
        return f"<a href='{self.outputfile}' {titleattr}>{self.shorttitle}</a>"

    @property
    def inputfile(self) -> str:
        return f"{self.config.chapterdir}/{self.slug}/index.md"

    @property
    def outputfile(self) -> str:
        return f"chapter-{self.slug}.html"

    @property
    def name(self) -> str:
        return self.slug

    def toc_link(self, level=0) -> str:
        titleattr = f"title=\"{h.as_attribute(self.description)}\""
        return h.indented_block(f"<a href='{self.outputfile}' {titleattr}>{self.title}</a>", level)


class Taskgroup(Item):
    description: str
    slug: str
    chapter: Chapter
    tasks: tg.List[sdrl.task.Task]

    def __init__(self, chapter: Chapter, taskgroup: b.StrAnyMap):
        self.chapter = chapter
        b.copyattrs(taskgroup, self,
                    m_attrs='title, shorttitle, slug',
                    o_attrs='',
                    f_attrs='taskgroups')
        b.read_partsfile(self, self.inputfile)
        b.copyattrs(self.metadata, self,
                    m_attrs='description',
                    o_attrs='todo',
                    f_attrs='', overwrite=False)
        self.tasks = []

    @property
    def breadcrumb_item(self) -> str:
        titleattr = f"title=\"{h.as_attribute(self.title)}\""
        return f"<a href='{self.outputfile}' {titleattr}>{self.shorttitle}</a>"

    @property
    def inputfile(self) -> str:
        return f"{self.chapter.config.chapterdir}/{self.chapter.slug}/{self.slug}/index.md"

    @property
    def outputfile(self) -> str:
        return f"{self.name}.html"

    @property
    def name(self) -> str:
        return f"{self.chapter.slug}-{self.slug}"

    def add_task(self, task: sdrl.task.Task):
        task.taskgroup = self
        self.tasks.append(task)
    
    def toc_link(self, level=0) -> str:
        titleattr = f"title=\"{h.as_attribute(self.description)}\""
        return h.indented_block(f"<a href='{self.outputfile}' {titleattr}>{self.title}</a>", level)
