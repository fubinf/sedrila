"""Represent and handle the contents of the sedrila.yaml config file: course, Chapter, Taskgroup."""

import functools
import glob
import graphlib
import os
import re
import typing as tg

import base as b
import sdrl.html as h
import sdrl.markdown as md

METADATA_FILE = "course.json"  # in student build directory
STATUS_INCOMPLETE = "incomplete"
STATUS_NORMAL = "normal"


def clean_status(context: str, obj: object, include_incomplete: bool) -> None:
    """
    Cuts the 'status' attribute of mydict down to its first word, checks it, reports violations.
    Missing status is allowed.
    If 'include_incomplete', status value STATUS_INCOMPLETE will be ignored
    and no status will be kept at all, so that incomplete tasks/taskgroups/chapters are kept,
    i.e., included in the output as if they were not marked as incomplete.
    """
    if not hasattr(obj, 'status') or not obj.status:
        return
    allowed_values = f"({STATUS_INCOMPLETE}|{STATUS_NORMAL})"
    mm = re.match(allowed_values, obj.status)  # match beginning only
    if not mm:
        b.error(f"{context}: Illegal value of 'status': '{obj.status}'")
        del obj.status
    else:
        obj.status = mm.group(1)  # keep only the relevant first word
        if obj.status == STATUS_INCOMPLETE and include_incomplete:
            del obj.status


class Task:
    DIFFICULTY_RANGE = range(1, len(h.difficulty_levels) + 1)

    srcfile: str  # the originating pathname
    metadata_text: str  # the YAML front matter character stream
    metadata: b.StrAnyDict  # the YAML front matter
    content: str  # the markdown block
    slug: str  # the key by which we access the Task object

    title: str  # title: value
    description: str  # description: value (possibly multiple lines)
    timevalue: tg.Union[int, float]  # task timevalue: (in hours)
    difficulty: int  # difficulty: int from DIFFICULTY_RANGE
    assumes: tg.List[str] = []  # tasknames: This knowledge is assumed to be present
    requires: tg.List[str] = []  # tasknames: These specific results will be reused here
    assumed_by: tg.List[str] = []  # tasknames: inverse of assumes
    required_by: tg.List[str] = []  # tasknames: inverse of requires
    profiles: tg.List[str] = []  # profile shortnames: specialty areas task pertains to
    workhours: float = 0.0  # time student has worked on this according to commit msgs
    accepted: bool = False  # whether instructor has ever marked it 'accept'
    rejections: int = 0  # how often instructor has marked it 'reject'

    taskgroup: 'Taskgroup'  # where the task belongs

    def __init__(self, file: tg.Optional[str], text: str = None, 
                 taskgroup: tg.Optional['Taskgroup'] = None, task: tg.Optional[b.StrAnyDict] = None,
                 include_incomplete: bool = False):
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
        b.copyattrs(file, 
                    self.metadata, self,
                    mustcopy_attrs='title, description, timevalue, difficulty',
                    cancopy_attrs='status, assumes, requires, profiles',  # TODO 2: check profiles against sedrila.yaml
                    mustexist_attrs='')
        clean_status(file, self.metadata, include_incomplete)
        # ----- ensure assumes/requires/profiles are lists:
        if isinstance(self.assumes, str):
            self.assumes = re.split(r", *", self.assumes)
        if isinstance(self.requires, str):
            self.requires = re.split(r", *", self.requires)
        if isinstance(self.profiles, str):
            self.profiles = re.split(r", *", self.profiles)

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
    def to_be_skipped(self) -> bool:
        return (getattr(self, 'status', "") == STATUS_INCOMPLETE or
                self.taskgroup.to_be_skipped or self.taskgroup.chapter.to_be_skipped)

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
        refs = (self._taskrefs('a', 'assumed_by') + self._taskrefs('r', 'required_by') +
                self._taskrefs('A', 'assumes') + self._taskrefs('R', 'requires'))
        profiles = ""
        if self.profiles:
            profiles = f" <span class='profiles-decoration'>({', '.join(self.profiles)})</span>"
        return f"<a {href} {titleattr}>{self.title}</a> {diffsymbol} {timevalue} {refs}{profiles}"

    def as_json(self) -> b.StrAnyDict:
        return dict(slug=self.slug,
                    title=self.title, timevalue=self.timevalue, difficulty=self.difficulty,
                    assumes=self.assumes, requires=self.requires, profiles=self.profiles)

    def from_json(self, taskgroup: 'Taskgroup', task: b.StrAnyDict):
        """Alternative constructor."""
        self.taskgroup = taskgroup
        self.slug = task['slug']
        self.title = task['title']
        self.timevalue = task['timevalue']
        self.difficulty = task['difficulty']
        self.assumes = task['assumes']
        self.requires = task['requires']
        self.profiles = task['profiles']

    def toc_link(self, level=0) -> str:
        return h.indented_block(self.toc_link_text, level)

    @staticmethod
    def _as_list(obj) -> tg.List:
        return obj if isinstance(obj, list) else list(obj)
    
    def _taskrefs(self, label: str, attr_name: str) -> str:
        """Create a toc link dedoration for one set of related tasks."""
        attr_cssclass = "%s-decoration" % attr_name.replace("_", "-")
        attr_label = attr_name.replace("_", " ")
        refslist = getattr(self, attr_name)
        if len(refslist) == 0:
            return ""
        title = "%s: %s" % (attr_label, ", ".join(refslist))
        return ("<span class='%s' title='%s'>%s</span>" %
                (attr_cssclass, title, label))

    @classmethod
    def expand_diff(cls, call: md.Macrocall, name: str, arg1: str, arg2: str) -> str:  # noqa
        assert name == "DIFF"
        level = int(arg1)
        diffrange = cls.DIFFICULTY_RANGE
        if level not in diffrange:
            call.error(f"Difficulty must be in range {min(diffrange)}..{max(diffrange)}")
            return ""
        return h.difficulty_symbol(level)


md.register_macros(('DIFF', 1, Task.expand_diff))  # noqa


class Item:
    """Common superclass for course, Chapter, Taskgroup (but not Task, although similar)."""
    title: str
    shorttitle: str
    metadata: b.StrAnyDict  # the YAML front matter
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

    @property
    def to_be_skipped(self) -> bool:
        return getattr(self, 'status', "") == STATUS_INCOMPLETE

    def as_json(self) -> b.StrAnyDict:
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
    configfile: str
    baseresourcedir: str = 'baseresources'
    chapterdir: str = 'ch'
    templatedir: str = 'templates'
    instructors: tg.List[b.StrAnyDict]
    chapters: tg.List['Chapter']
    taskorder: tg.List[Task]  # If task B assumes or requires A, A will be before B in this list.

    def __init__(self, configfile: str, read_contentfiles: bool, include_incomplete: bool):
        self.configfile = configfile
        configdict = b.slurp_yaml(configfile)
        b.copyattrs(configfile, 
                    configdict, self,
                    mustcopy_attrs='title, shorttitle, instructors, profiles',
                    cancopy_attrs='baseresourcedir, chapterdir, templatedir',
                    mustexist_attrs='chapters')
        if read_contentfiles and os.path.isfile(self.inputfile):
            b.read_partsfile(self, self.inputfile)
        self.chapters = [Chapter(self, ch, read_contentfiles, include_incomplete) 
                         for ch in configdict['chapters']]
        self._check_links()
        self._add_inverse_links()
        self._compute_taskorder()

    @property
    def breadcrumb_item(self) -> str:
        titleattr = f"title=\"{h.as_attribute(self.title)}\""
        return f"<a href='index.html' {titleattr}>{self.shorttitle}</a>"

    @property
    def inputfile(self) -> str:
        return f"{self.chapterdir}/index.md"

    @property
    def outputfile(self) -> str:
        return "index.html"

    @functools.cached_property
    def chapterdict(self) -> tg.Mapping[str, 'Chapter']:
        return {ch.slug: ch for ch in self.chapters}

    @functools.cached_property
    def taskgroupdict(self) -> tg.Mapping[str, 'Taskgroup']:
        return {tgroup.slug: tgroup for tgroup in self._all_taskgroups()}

    @functools.cached_property
    def taskdict(self) -> tg.Mapping[str, Task]:
        result = dict()
        for t in self._all_tasks():
            if t.name in result:
                b.error(f"duplicate task: '{t.inputfile}'\t'{result[t.name].inputfile}'")
            else:
                result[t.name] = t
        return result

    def as_json(self) -> b.StrAnyDict:
        result = dict(baseresourcedir=self.baseresourcedir, 
                      chapterdir=self.chapterdir,
                      templatedir=self.templatedir,
                      instructors=self.instructors,
                      chapters=[chapter.as_json() for chapter in self.chapters])
        result.update(super().as_json())
        return result

    def chapter(self, slug: str) -> tg.Optional['Chapter']:
        """Return Chapter for given slug or None if no such Chapter exists."""
        return self.chapterdict.get(slug)

    def taskgroup(self, slug: str) -> tg.Optional[Task]:
        """Return Taskgroup for given slug or None if no such task exists."""
        return self.taskgroupdict.get(slug)

    def task(self, taskname: str) -> tg.Optional[Task]:
        """Return Task for given taskname or None if no such task exists."""
        return self.taskdict.get(taskname)

    def _all_taskgroups(self) -> tg.Generator['Taskgroup', None, None]:
        """To be used only for initializing taskgroupdict, so we can assume all taskgroups to be known"""
        for chapter in self.chapters:
            for taskgroup in chapter.taskgroups:
                yield taskgroup

    def _all_tasks(self) -> tg.Generator[Task, None, None]:
        """To be used only for initializing taskdict, so we can assume all tasks to be known"""
        for chapter in self.chapters:
            for taskgroup in chapter.taskgroups:
                for task in taskgroup.tasks:
                    yield task

    def volume_report_per_chapter(self) -> tg.Sequence[tg.Tuple[str, int, float]]:
        """Tuples of (chaptername, num_tasks, timevalue_sum)"""
        result = []
        for chapter in (c for c in self.chapters if not c.to_be_skipped):
            num_tasks = sum((1 for t in self.taskdict.values() if t.taskgroup.chapter == chapter))
            timevalue_sum = sum((t.timevalue for t in self.taskdict.values() if t.taskgroup.chapter == chapter))
            result.append((chapter.shorttitle, num_tasks, timevalue_sum))
        return result

    def volume_report_per_difficulty(self) -> tg.Sequence[tg.Tuple[int, int, float]]:
        """Tuples of (difficulty, num_tasks, timevalue_sum)"""
        result = []
        for difficulty in Task.DIFFICULTY_RANGE:
            num_tasks = sum((1 for t in self.taskdict.values() 
                             if t.difficulty == difficulty and not t.to_be_skipped))
            timevalue_sum = sum((t.timevalue for t in self.taskdict.values() 
                                 if t.difficulty == difficulty and not t.to_be_skipped))
            result.append((difficulty, num_tasks, timevalue_sum))
        return result

    def _add_inverse_links(self):
        """add Task.required_by/Task.assumed_by lists."""
        for taskname, task in self.taskdict.items():
            task.assumed_by = []  # so we do not append to the class attribute
            task.required_by = []
        for taskname, task in self.taskdict.items():
            for assumed_taskname in task.assumes:
                assumed_task = self.task(assumed_taskname)
                if assumed_task:
                    assumed_task.assumed_by.append(taskname)
            for required_taskname in task.requires:
                required_task = self.task(required_taskname)
                if required_task:
                    required_task.required_by.append(taskname)

    def _check_links(self):
        for task in self.taskdict.values():
            b.debug(f"Task '{task.slug}'\tassumes {task.assumes},\trequires {task.requires}")
            for assumed in task.assumes:
                if not self._task_or_taskgroup_exists(assumed):
                    b.error(f"{task.slug}:\t assumed task or taskgroup '{assumed}' does not exist")
            for required in task.requires:
                if not self._task_or_taskgroup_exists(required):
                    b.error(f"{task.slug}:\t required task or taskgroup '{required}' does not exist")
            for profile in task.profiles:
                if profile not in self.profiles:
                    b.error(f"{task.slug}:\t profile '{profile}' does not exist")

    def _compute_taskorder(self):
        """
        Set self.taskorder such that it respects the 'assumes' and 'requires'
        dependencies globally (across all taskgroups and chapters).
        The attribute will be used for ordering the tasks when rendering a taskgroup.
        """
        # ----- prepare dependency graph for topological sorting:
        graph = dict()  # maps a task to a set of tasks it depends on.
        for mytaskname, mytask in self.taskdict.items():
            dependencies = set()  # collection of all tasks required or assumed by mytask
            for assumedtask in mytask.assumes:
                if assumedtask in self.taskdict:
                    dependencies.add(self.taskdict[assumedtask])
            for requiredtask in mytask.requires:
                if requiredtask in self.taskdict:
                    dependencies.add(self.taskdict[requiredtask])
            graph[mytask] = dependencies
        # ----- compute taskorder (or report dependency cycle if one is found):
        try:
            self.taskorder = list(graphlib.TopologicalSorter(graph).static_order())
        except graphlib.CycleError as exc:
            msg = "Some tasks' 'assumes' or 'requires' dependencies form a cycle:\n"
            b.critical(msg + exc.args[1])

    def _task_or_taskgroup_exists(self, name: str) -> bool:
        return name in self.taskdict or name in self.taskgroupdict


class Chapter(Item):
    description: str
    slug: str
    course: Course
    taskgroups: tg.Sequence['Taskgroup']
    
    def __init__(self, course: Course, chapter: b.StrAnyDict, read_contentfiles: bool, include_incomplete: bool):
        self.course = course
        context = f"chapter in {course.configfile}"
        b.copyattrs(context, 
                    chapter, self,
                    mustcopy_attrs='title, shorttitle, slug',
                    cancopy_attrs='status',
                    mustexist_attrs='taskgroups')
        clean_status(context, self, include_incomplete)
        if read_contentfiles:
            b.read_partsfile(self, self.inputfile)
            b.copyattrs(context, 
                        self.metadata, self,
                        mustcopy_attrs='description',
                        cancopy_attrs='todo',
                        mustexist_attrs='', overwrite=False)
        self.taskgroups = [Taskgroup(self, taskgroup, read_contentfiles, include_incomplete) 
                           for taskgroup in (chapter.get('taskgroups') or [])]

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

    @property
    def toc_link_text(self) -> str:
        titleattr = f"title=\"{h.as_attribute(self.description)}\""
        return f"<a href='{self.outputfile}' {titleattr}>{self.title}</a>"

    def as_json(self) -> b.StrAnyDict:
        result = dict(slug=self.slug, 
                      taskgroups=[taskgroup.as_json() for taskgroup in self.taskgroups])
        result.update(super().as_json())
        return result

    def toc_link(self, level=0) -> str:
        return h.indented_block(self.toc_link_text, level)


class Taskgroup(Item):
    description: str
    slug: str
    chapter: Chapter
    tasks: tg.List['Task']

    def __init__(self, chapter: Chapter, taskgroup: b.StrAnyDict, read_contentfiles: bool, include_incomplete: bool):
        self.chapter = chapter
        context = f"taskgroup in chapter {chapter.slug}"
        b.copyattrs(context, 
                    taskgroup, self,
                    mustcopy_attrs='title, shorttitle, slug',
                    cancopy_attrs='tasks, status',
                    mustexist_attrs='taskgroups')
        if read_contentfiles:
            b.read_partsfile(self, self.inputfile)
            b.copyattrs(context,
                        self.metadata, self,
                        mustcopy_attrs='description',
                        cancopy_attrs='minimum, todo',
                        mustexist_attrs='', overwrite=False)
        clean_status(context, self, include_incomplete)
        if read_contentfiles:
            self._create_tasks()
        else:
            self.tasks = [Task(file=None, taskgroup=self, task=task, include_incomplete=include_incomplete) 
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

    @property
    def toc_link_text(self) -> str:
        titleattr = f"title=\"{h.as_attribute(self.description)}\""
        return f"<a href='{self.outputfile}' {titleattr}>{self.title}</a>"

    @property
    def to_be_skipped(self) -> bool:
        return super().to_be_skipped or self.chapter.to_be_skipped

    def as_json(self) -> b.StrAnyDict:
        result = dict(slug=self.slug, 
                      tasks=[task.as_json() for task in self.tasks])
        result.update(super().as_json())
        return result

    def toc_link(self, level=0) -> str:
        return h.indented_block(self.toc_link_text, level)

    def _add_task(self, task: Task):
        task.taskgroup = self
        self.tasks.append(task)

    def _create_tasks(self):
        """Finds and reads task files."""
        self.tasks = []
        chapterdir = self.chapter.course.chapterdir
        filenames = glob.glob(f"{chapterdir}/{self.chapter.slug}/{self.slug}/*.md")
        for filename in filenames:
            if not filename.endswith("index.md"):
                self._add_task(Task(filename))
