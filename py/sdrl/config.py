"""Represent and handle the contents of the sedrial.yaml config file: Config, Chapter, Taskgroup."""

import functools
import typing as tg

import yaml

import base
import sdrl.task

class Config:
    title: str
    shorttitle: str
    chapterdir: str = 'ch'
    templatedir: str = 'templates'
    chapters: tg.Sequence['Chapter']
    
    def __init__(self, configfile: str):
        yamltext = base.slurp(configfile)
        configdict: base.StrAnyMap = yaml.safe_load(yamltext)
        base.read_and_check(configdict, self,
                            m_attrs='title, shorttitle', 
                            o_attrs='chapterdir, templatedir',
                            f_attrs='chapters')
        self.chapters = [Chapter(self, ch) for ch in configdict['chapters']]

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

class Chapter:
    title: str
    shorttitle: str
    slug: str
    
    config: Config
    taskgroups: tg.Sequence['Taskgroup']
    
    def __init__(self, config: Config, chapter: base.StrAnyMap):
        self.config = config
        base.read_and_check(chapter, self,
                            m_attrs='title, shorttitle, slug', 
                            o_attrs='',
                            f_attrs='taskgroups')
        self.taskgroups = [Taskgroup(self, taskgroup) for taskgroup in chapter['taskgroups']]

    @property
    def filename(self) -> str:
        return f"chapter-{self.slug}.html"

    @property
    def name(self) -> str:
        return self.slug

    def toc_link(self) -> str:
        return f"<a href='{self.filename}'>{self.shorttitle}: {self.title}</a>"


class Taskgroup:
    title: str
    shorttitle: str
    slug: str
    
    chapter: Chapter
    tasks: tg.List[sdrl.task.Task]

    def __init__(self, chapter: Chapter, taskgroup: base.StrAnyMap):
        self.chapter = chapter
        base.read_and_check(taskgroup, self,
                            m_attrs='title, shorttitle, slug', 
                            o_attrs='',
                            f_attrs='taskgroups')
        self.tasks = []

    @property
    def filename(self) -> str:
        return f"{self.name}.html"

    @property
    def name(self) -> str:
        return f"{self.chapter.slug}-{self.slug}"

    def add_task(self, task: sdrl.task.Task):
        task.taskgroup = self
        self.tasks.append(task)
    
    def toc_link(self) -> str:
        return f"  <a href='{self.filename}'>{self.shorttitle}: {self.title}</a>"