"""
Represent and handle the contents of SeDriLa: Course, Chapter, Taskgroup, Task.
There are two ways how these objects can be instantiated:
In 'author' mode, metadata comes from sedrila.yaml and the partfiles.
Otherwise, metadata comes from METADATA_FILE. 
"""
import dataclasses
import enum
import functools
import glob
import graphlib
import numbers
import os
import re
import typing as tg

import base as b
import cache
import sdrl.directory as dir
import sdrl.elements as el
import sdrl.glossary as glossary
import sdrl.html as h
import sdrl.macros as macros
import sdrl.partbuilder

sedrila_libdir = os.path.dirname(os.path.dirname(__file__))  # either 'py' (for dev install) or top-level
if sedrila_libdir.endswith('py'):  # we are a dev install and must go one more level up:
    sedrila_libdir = os.path.dirname(sedrila_libdir)


class Task(el.Part):
    DIFFICULTY_RANGE = range(1, len(h.difficulty_levels) + 1)
    TOC_LEVEL = 2  # indent level in table of contents

    timevalue: tg.Union[int, float]  # task timevalue: (in hours)
    difficulty: int  # difficulty: int from DIFFICULTY_RANGE
    assumes: list[str] = []  # tasknames: This knowledge is assumed to be present
    requires: list[str] = []  # tasknames: These specific results will be reused here
    workhours: float = 0.0  # time student has worked on this according to commit msgs
    accepted: bool = False  # whether instructor has ever marked it 'accept'
    rejections: int = 0  # how often instructor has marked it 'reject'

    taskgroup: 'Taskgroup'  # where the task belongs

    @property
    def remaining_attempts(self) -> int:
        return max(0, self.allowed_attempts - self.rejections)

    @property
    def allowed_attempts(self) -> int:
        course = self.taskgroup.chapter.course
        return int(course.allowed_attempts_base + course.allowed_attempts_hourly*self.timevalue)

    def from_json(self, task: b.StrAnyDict, taskgroup: 'Taskgroup') -> 'Task':
        """Initializer used in student and instructor mode. Ignores all additional attributes."""
        self.taskgroup = taskgroup
        self.slug = task['slug']
        self.title = task['title']
        self.timevalue = task['timevalue']
        self.difficulty = task['difficulty']
        self.assumes = task['assumes']
        self.requires = task['requires']
        return self

    def __hash__(self) -> int:
        return hash(self.slug)


@functools.total_ordering
class Taskbuilder(Task, sdrl.partbuilder.PartbuilderMixin):
    explains: list[str] = []  # terms (for backlinks in glossary)
    assumed_by: list[str] = []  # tasknames: inverse of assumes
    required_by: list[str] = []  # tasknames: inverse of requires

    taskgroup: 'Taskgroupbuilder'  # where the task belongs

    @property
    def remaining_attempts(self) -> int:
        return max(0, self.allowed_attempts - self.rejections)

    @property
    def allowed_attempts(self) -> int:
        course = self.taskgroup.chapter.course
        return int(course.allowed_attempts_base + course.allowed_attempts_hourly*self.timevalue)

    @property
    def breadcrumb_item(self) -> str:
        return f"<a href='{self.outputfile}'>{self.slug}</a>"

    @property
    def to_be_skipped(self) -> bool:
        return (self.skipthis or
                self.taskgroup.to_be_skipped or self.taskgroup.chapter.to_be_skipped)

    @property
    def toc_link_text(self) -> str:
        href = f"href='{self.outputfile}'"
        titleattr = f"title=\"{self.title}\""
        diffsymbol = h.difficulty_symbol(self.difficulty)
        timevalue = ("<span class='timevalue-decoration' title='Timevalue: %s hours'>%s</span>" %
                     (self.timevalue, self.timevalue))
        refs = (self._taskrefs('assumed_by') + self._taskrefs('required_by') +
                self._taskrefs('assumes') + self._taskrefs('requires'))
        return f"<a {href} {titleattr}>{self.slug}</a> {diffsymbol} {timevalue}{refs}"

    def as_json(self) -> b.StrAnyDict:
        return dict(slug=self.slug,
                    title=self.title, timevalue=self.timevalue, difficulty=self.difficulty,
                    assumes=self.assumes, requires=self.requires)

    def from_file(self, file: str, taskgroup: 'Taskgroupbuilder') -> 'Taskbuilder':
        self.read_partsfile(file)
        # ----- get taskdata from file:
        filename = os.path.basename(self.sourcefile)
        mm = re.fullmatch(r"(.+)\.md", filename)
        assert mm, filename  # we only get handed .md files here 
        self.slug = mm.group(1)  # must be globally unique
        self.outputfile = f"{self.slug}.html"
        b.copyattrs(file,
                    self.metadata, self,
                    mustcopy_attrs='title, timevalue, difficulty',
                    cancopy_attrs='stage, explains, assumes, requires',
                    mustexist_attrs='',
                    typecheck=dict(timevalue=numbers.Number, difficulty=int))
        self.evaluate_stage(file, taskgroup.chapter.course)
        taskgroup.chapter.course.namespace_add(self.sourcefile, self)

        # ----- ensure explains/assumes/requires are lists:
        def _handle_strlist(attrname: str):
            attrvalue = getattr(self, attrname)
            if isinstance(attrvalue, str):
                setattr(self, attrname, re.split(r", *", attrvalue))
            elif not attrvalue:
                setattr(self, attrname, [])
            else:
                msg = f"'{file}': value of '%s:' must be a (non-empty) string"
                b.error(msg % attrname)
                setattr(self, attrname, [])

        _handle_strlist('explains')
        _handle_strlist('assumes')
        _handle_strlist('requires')
        # ----- add to glossary:
        if self.explains:
            for term in self.explains:
                taskgroup.chapter.course.glossary.explains(self.slug, term)
        # ----- done:
        return self

    def _taskrefs(self, attr_name: str) -> str:
        """Create a toc link dedoration for one set of related tasks."""
        attr_cssclass = "%s-decoration" % attr_name.replace("_", "-")
        attr_label = attr_name.replace("_", " ")
        refslist = getattr(self, attr_name)
        if len(refslist) == 0:
            return ""
        title = "%s: %s" % (attr_label, ", ".join(refslist))
        return ("<span class='%s' title='%s'>%s</span>" %
                (attr_cssclass, title, ""))  # label is provided by CSS

    @classmethod
    def expand_diff(cls, call: macros.Macrocall) -> str:  # noqa
        assert call.macroname == "DIFF"
        level = int(call.arg1)
        diffrange = cls.DIFFICULTY_RANGE
        if level not in diffrange:
            call.error(f"Difficulty must be in range {min(diffrange)}..{max(diffrange)}")
            return ""
        return h.difficulty_symbol(level)

    def __eq__(self, other):
        return other.slug == self.slug

    def __lt__(self, other):
        if not isinstance(other, type(self)):
            return NotImplemented
        return (self.difficulty < other.difficulty or
                (self.difficulty == other.difficulty and self.slug < other.slug))

    def __hash__(self) -> int:
        return hash(self.slug)


class CacheMode(enum.Enum):
    UNCACHED = 0  # read and render everything afresh 
    WRITE = 1  # read metadata, write cache, render everything afresh 
    READ = 3  # read metadata from cache, reuse rendered files


class Course(el.Partscontainer):
    """
    The master data object for this run.
    Can be initialized in two different ways: 
    - as Coursebuilder: From a handwritten YAML file. 
      Will then read all content for a build.
    - as Course: From a metadata file generated during build
      for bookkeeping/reporting.
    """
    AUTHORMODE_ATTRS = ''

    configfile: str
    breadcrumb_title: str
    instructors: list[b.StrAnyDict]
    chapters: list['Chapter']
    namespace: dict[str, el.Part]  # the parts known so far
    init_data: b.StrAnyDict = {}
    allowed_attempts: str  # "2 + 0.5/h" or so, int+decimal, h is the task timevalue multiplier
    allowed_attempts_base: int  # the int part of allowed_attempts
    allowed_attempts_hourly: float  # the decimal part of allowed_attempts

    def __init__(self, name, *args, **kwargs):
        print(f"Course:{type(self).__name__}.__init__({kwargs})")
        super().__init__(name, *args, **kwargs)
        self.sourcefile = self.configfile
        configdict = b.slurp_yaml(self.configfile)
        b.copyattrs(self.configfile,
                    configdict, self,
                    mustcopy_attrs=('title, breadcrumb_title, instructors, allowed_attempts' +
                                    self.AUTHORMODE_ATTRS),
                    cancopy_attrs=('baseresourcedir, itreedir, templatedir, '
                                   'blockmacro_topmatter, htaccess_template, init_data'),
                    mustexist_attrs='chapters',
                    report_extra=bool(self.AUTHORMODE_ATTRS))
        self.allowed_attempts_base, self.allowed_attempts_hourly = self._parse_allowed_attempts()
        self.slug = self.breadcrumb_title
        self.outputfile = "index.html"
        self.namespace = dict()
        self.namespace_add(self.configfile, self)
        self._init_parts(configdict, self.include_stage)
        
    @property
    def breadcrumb_item(self) -> str:
        titleattr = f"title=\"{h.as_attribute(self.title)}\""
        return f"<a href='index.html' {titleattr}>{self.breadcrumb_title}</a>"

    @functools.cached_property
    def taskgroupdict(self):
        return {tgroup.slug: tgroup for tgroup in self._all_taskgroups()}

    @functools.cached_property
    def taskdict(self):
        result = dict()
        for t in self._all_tasks():
            if t.slug in result:
                b.error(f"duplicate task: '{t.sourcefile}'\t'{result[t.slug].sourcefile}'")
            else:
                result[t.slug] = t
        return result

    def task(self, taskname: str):
        """Return Task for given taskname or None if no such task exists."""
        return self.taskdict.get(taskname)

    def get_part(self, context: str, partname: str) -> el.Part:
        """Return part for given partname or self (and create an error) if no such part exists."""
        if partname in self.namespace:
            return self.namespace[partname]
        b.error(f"{context}: part '{partname}' does not exist")
        return self

    def namespace_add(self, context: str, newpart: el.Part):
        name = newpart.slug
        if name in self.namespace:
            b.error("%s: name collision: %s and %s" %
                    (context, self._slugfilename(self.namespace[name]), self._slugfilename(newpart)))
        else:
            self.namespace[name] = newpart

    def _all_taskgroups(self) -> tg.Generator['Taskgroup', None, None]:
        """To be used only for initializing taskgroupdict, so we can assume all taskgroups to be known"""
        for chapter in self.chapters:
            for taskgroup in chapter.taskgroups:
                yield taskgroup

    def _all_tasks(self):
        """To be used only for initializing taskdict, so we can assume all tasks to be known"""
        for chapter in self.chapters:
            for taskgroup in chapter.taskgroups:
                for task in taskgroup.tasks:
                    yield task

    def _init_parts(self, configdict: dict, include_stage: str):
        self.chapters = [Chapter(self, ch) 
                         for ch in configdict['chapters']]

    def _parse_allowed_attempts(self) -> tuple[int, float]:
        mm = re.match(r"(\d+)\s?\+\s?(\d+\.\d+)\s?/\s?h", self.allowed_attempts)
        if not mm:
            msg1 = f"'allowed_attempts' must have a format exactly like '2 + 0.5/h'"
            b.error(f"{self.sourcefile}: {msg1}, not '{self.allowed_attempts}'")
            return 2, 0
        return int(mm.group(1)), float(mm.group(2))

    @staticmethod
    def _slugfilename(p: el.Part) -> str:
        fullpath = p.sourcefile
        basename = os.path.basename(fullpath)
        dirname = os.path.dirname(fullpath)
        if basename == "index.md":
            return dirname
        else:
            return fullpath


class Coursebuilder(Course, sdrl.partbuilder.PartbuilderMixin):
    """Course with the additions required for author mode. (Chapter, Taskgroup, Task have both in one.)"""
    AUTHORMODE_ATTRS = ', chapterdir, altdir, stages'

    baseresourcedir: str = f"{sedrila_libdir}/baseresources"
    chapterdir: str
    altdir: str
    itreedir: str | None
    templatedir: str = f"{sedrila_libdir}/templates"
    blockmacro_topmatter: dict[str, str]
    htaccess_template: str = None  # structure of .htaccess file generated in instructor website
    stages: list[str]  # list of allowed values of stage in parts 

    chapters: list['Chapterbuilder']
    include_stage: str  # lowest stage that parts must have to be included in output
    include_stage_index: int  # index in stages list, or len(stages) if include_stage is ""
    mtime: float  # in READ cache mode: tasks have changed if they are younger than this
    taskorder: list[Taskbuilder]  # If task B assumes or requires A, A will be before B in this list.
    targetdir_s: str  # where to render student output files
    targetdir_i: str  # where to render instructor output files
    glossary: glossary.Glossarybuilder

    @dataclasses.dataclass
    class Volumereport:
        rows: tg.Sequence[tg.Tuple[str, int, float]]
        columnheads: tg.Sequence[str]
    
    def as_json(self) -> b.StrAnyDict:
        result = dict(title=self.title,
                      breadcrumb_title=self.breadcrumb_title,
                      instructors=self.instructors,
                      init_data=self.init_data,
                      allowed_attempts=self.allowed_attempts,
                      chapters=[chapter.as_json() for chapter in self.chapters])
        result.update(super().as_json())
        return result

    def _add_baseresources(self):
        for direntry in os.scandir(self.baseresourcedir):
            # TODO 2: skip and report (jointly) non-file entries
            assert direntry.is_file()
            self.directory.make_the(el.Sourcefile, direntry.path)
            self.directory.make_the(el.Outputfile, direntry.name)

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

    def _collect_zipdirs(self):
        for zd in self.zipdirs:
            self.namespace_add(zd.sourcefile, zd)
        for ch in self.chapters:
            for zd in ch.zipdirs:
                self.namespace_add(zd.sourcefile, zd)
            for tgr in ch.taskgroups:
                for zd in tgr.zipdirs:
                    self.namespace_add(zd.sourcefile, zd)

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
        self.taskorder = self._taskordering_for_toc(graph)

    def _init_parts(self, configdict: dict, include_stage: str):
        self.read_partsfile(f"{self.chapterdir}/index.md")
        self.glossary = glossary.Glossarybuilder(self.chapterdir)
        self.namespace_add("", self.glossary)
        self.find_zipdirs()
        if include_stage in self.stages:
            self.include_stage = include_stage
            self.include_stage_index = self.stages.index(include_stage)
        else:
            if include_stage != '':  # empty is allowed
                b.error(f"'--include_stage {include_stage}' not allowed, must be one of {self.stages}")
            self.include_stage = ''  # include only parts with no stage
            self.include_stage_index = len(self.stages)
        self.chapters = [Chapterbuilder(self, ch) 
                         for ch in configdict['chapters']]
        self._add_baseresources()
        self._collect_zipdirs()
        self._check_links()
        self._add_inverse_links()
        self._compute_taskorder()

    def _task_or_taskgroup_exists(self, name: str) -> bool:
        return name in self.taskdict or name in self.taskgroupdict

    @staticmethod
    def _taskordering_for_toc(graph) -> list[Taskbuilder]:
        sorter = graphlib.TopologicalSorter(graph)
        sorter.prepare()
        result = []
        try:
            while sorter.is_active():
                node_group = sorted(sorter.get_ready())
                result.extend(node_group)
                sorter.done(*node_group)        
        except graphlib.CycleError as exc:
            msg = "Some tasks' 'assumes' or 'requires' dependencies form a cycle:\n"
            b.critical(msg + exc.args[1])
        return result

    def _volume_report(self, rowitems: tg.Iterable, column1head: str,
                       select: tg.Callable[[Task, tg.Any], bool],
                       render: tg.Callable[[tg.Any], str],
                       include_all=False) -> Volumereport:
        """Tuples of (category, num_tasks, timevalue_sum)."""
        result = []
        for row in rowitems:
            num_tasks = sum((1 for t in self.taskdict.values() if select(t, row) and not t.to_be_skipped))
            timevalue_sum = sum((t.timevalue for t in self.taskdict.values() if select(t, row) and not t.to_be_skipped))
            if num_tasks > 0 or include_all:
                result.append((render(row), num_tasks, timevalue_sum))
        return self.Volumereport(result, (column1head, "#Tasks", "Timevalue"))

    def volume_report_per_chapter(self) -> Volumereport:
        return self._volume_report(self.chapters, "Chapter",
                                   lambda t, c: t.taskgroup.chapter == c, lambda c: c.slug)

    def volume_report_per_difficulty(self) -> Volumereport:
        return self._volume_report(Task.DIFFICULTY_RANGE, "Difficulty",
                                   lambda t, d: t.difficulty == d, lambda d: h.difficulty_levels[d-1])

    def volume_report_per_stage(self) -> Volumereport:
        return self._volume_report(self.stages + [None], "Stage",
                                   lambda t, s: t.stage == s, lambda s: s or "done", include_all=True)


class Chapter(el.Partscontainer):
    course: Course
    taskgroups: list['Taskgroup']

    def __init__(self, course: Course, chapter: b.StrAnyDict):
        self.course = course
        context = f"chapter in {course.configfile}"
        self._init_from_dict(context, chapter)
        course.namespace_add(self.sourcefile, self)
        self.taskgroups = [Taskgroup(self, taskgroup)
                           for taskgroup in (chapter.get('taskgroups') or [])]

    def _init_from_dict(self, context: str, chapter: b.StrAnyDict):
        b.copyattrs(context,
                    chapter, self,
                    mustcopy_attrs='slug',
                    mustexist_attrs='taskgroups',
                    cancopy_attrs='title')


class Chapterbuilder(Chapter, sdrl.partbuilder.PartbuilderMixin):
    course: Coursebuilder
    taskgroups: list['Taskgroupbuilder']

    def __init__(self, course: Coursebuilder, chapter: b.StrAnyDict):
        self.course = course
        context = f"chapter in {course.configfile}"
        self._init_from_dict(context, chapter)
        self._init_from_file(context, course)
        course.namespace_add(self.sourcefile, self)
        self.taskgroups = [Taskgroupbuilder(self, taskgroup)
                           for taskgroup in (chapter.get('taskgroups') or [])]

    def _init_from_file(self, context: str, course: Coursebuilder):
        self.read_partsfile(f"{self.course.chapterdir}/{self.slug}/index.md")
        b.copyattrs(context,
                    self.metadata, self,
                    mustcopy_attrs='title',
                    cancopy_attrs='stage, todo',
                    mustexist_attrs='',
                    overwrite=True)
        self.find_zipdirs()
        self.evaluate_stage(context, course)

    @property
    def breadcrumb_item(self) -> str:
        titleattr = f"title=\"{h.as_attribute(self.title)}\""
        return f"<a href='{self.outputfile}' {titleattr}>{self.slug}</a>"

    @property
    def outputfile(self) -> str:
        return f"chapter-{self.slug}.html"

    @property
    def to_be_skipped(self) -> bool:
        return self.skipthis

    def as_json(self) -> b.StrAnyDict:
        result = dict(slug=self.slug,
                      taskgroups=[taskgroup.as_json() for taskgroup in self.taskgroups])
        result.update(super().as_json())
        return result


class Taskgroup(el.Partscontainer):
    TOC_LEVEL = 1  # indent level in table of contents
    chapter: Chapter
    tasks: list['Task']

    def __init__(self, chapter: Chapter, taskgroupdict: b.StrAnyDict):
        self.chapter = chapter
        context = f"taskgroup in chapter '{chapter.slug}'"
        self._init_from_dict(context, taskgroupdict)
        chapter.course.namespace_add(self.sourcefile, self)
        self.tasks = [Task(taskdict['slug']).from_json(taskdict, taskgroup=self)
                      for taskdict in taskgroupdict['tasks']]

    def _init_from_dict(self, context: str, taskgroupdict: b.StrAnyDict):
        b.copyattrs(context,
                    taskgroupdict, self,
                    mustcopy_attrs='slug',
                    cancopy_attrs='tasks, title',
                    mustexist_attrs='taskgroups')


class Taskgroupbuilder(Taskgroup, sdrl.partbuilder.PartbuilderMixin):
    chapter: Chapterbuilder
    tasks: list['Taskbuilder']

    def __init__(self, chapter: Chapterbuilder, taskgroupdict: b.StrAnyDict):
        self.chapter = chapter
        context = f"taskgroup in chapter '{chapter.slug}'"
        self._init_from_dict(context, taskgroupdict)
        self.outputfile = f"{self.slug}.html"
        context = f"taskgroup '{self.slug}' in chapter '{chapter.slug}'"
        self._init_from_file(context, chapter)
        chapter.course.namespace_add(self.sourcefile, self)
        self._create_tasks()

    @property
    def breadcrumb_item(self) -> str:
        titleattr = f"title=\"{h.as_attribute(self.title)}\""
        return f"<a href='{self.outputfile}' {titleattr}>{self.slug}</a>"

    @property
    def to_be_skipped(self) -> bool:
        return self.skipthis or self.chapter.to_be_skipped

    def as_json(self) -> b.StrAnyDict:
        result = dict(slug=self.slug, 
                      tasks=[task.as_json() for task in self.tasks])
        result.update(super().as_json())
        return result

    def _add_task(self, task: Taskbuilder):
        task.taskgroup = self
        self.tasks.append(task)

    def _create_tasks(self):
        """Finds and reads task files."""
        self.tasks = []
        chapterdir = self.chapter.course.chapterdir
        filenames = glob.glob(f"{chapterdir}/{self.chapter.slug}/{self.slug}/*.md")
        for filename in filenames:
            if not filename.endswith("index.md"):
                self._add_task(Taskbuilder().from_file(filename, taskgroup=self))

    def _init_from_file(self, context, chapter):
        self.read_partsfile(f"{self.chapter.course.chapterdir}/{self.chapter.slug}/{self.slug}/index.md")
        b.copyattrs(context,
                    self.metadata, self,
                    mustcopy_attrs='title',
                    cancopy_attrs='minimum, stage, todo',
                    mustexist_attrs='',
                    overwrite=True)
        self.find_zipdirs()
        self.evaluate_stage(context, chapter.course)
