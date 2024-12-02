"""
Represent and handle the contents of SeDriLa: Course, Chapter, Taskgroup, Task.
There are two ways how these objects can be instantiated:
In 'author' mode, metadata comes from sedrila.yaml and the partfiles.
Otherwise, metadata comes from METADATA_FILE. 
"""
import dataclasses
import functools
import glob
import graphlib
import itertools
import numbers
import os
import re
import typing as tg

import base as b
import sdrl.constants as c
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
    
    course: 'Course'
    timevalue: tg.Union[int, float]  # task timevalue: (in hours)
    difficulty: int  # difficulty: int from DIFFICULTY_RANGE
    assumes: list[str] = []  # tasknames: This knowledge is assumed to be present
    requires: list[str] = []  # tasknames: These specific results will be reused here
    workhours: float = 0.0  # time student has worked on this according to commit msgs
    is_accepted: bool = False  # whether instructor has ever marked it 'accept'
    rejections: int = 0  # how often instructor has marked it 'reject'

    taskgroup: 'Taskgroup'  # where the task belongs

    def __init__(self, name: str, **kwargs):
        super().__init__(name, **kwargs)
        self.course.namespace_add(self)

    def __hash__(self) -> int:
        return hash(self.name)

    @property
    def allowed_attempts(self) -> int:
        course = self.taskgroup.chapter.course
        return int(course.allowed_attempts_base + course.allowed_attempts_hourly*self.timevalue)

    @property
    def path(self) -> str:
        """Returns 'mychapter/mytaskgroup/self.name'"""
        return f"{self.taskgroup.chapter.name}/{self.taskgroup.name}/{self.name}"

    @property
    def remaining_attempts(self) -> int:
        return max(0, self.allowed_attempts - self.rejections)

    @property
    def sourcefile(self) -> str:
        return f"{self.course.chapterdir}/{self.taskgroup.chapter.name}/{self.taskgroup.name}/{self.name}.md"

    def from_json(self, task: b.StrAnyDict) -> 'Task':
        """Initializer used in student and instructor mode. Ignores all additional attributes."""
        self.taskgroup = tg.cast('Taskgroup', self.parent)
        self.title = task['title']
        self.timevalue = task['timevalue']
        self.difficulty = task['difficulty']
        self.assumes = task['assumes']
        self.requires = task['requires']
        return self


@functools.total_ordering
class Taskbuilder(sdrl.partbuilder.PartbuilderMixin, Task):
    TEMPLATENAME = "task.html"
    explains: list[str] = []  # terms (for backlinks in glossary)
    assumed_by: list[str] = []  # tasknames: inverse of assumes
    required_by: list[str] = []  # tasknames: inverse of requires

    taskgroup: 'Taskgroupbuilder'  # where the task belongs

    def __init__(self, name: str, **kwargs):
        super().__init__(name, **kwargs)
        self.directory.record_the(Task, self.name, self)
        self.make_std_dependencies(use_toc_of=self.taskgroup)
        self.make_dependency(el.LinkslistBottom, part=self)

    def __eq__(self, other):
        return other.name == self.name

    def __lt__(self, other):  # for sorting in Coursebuilder._taskordering_for_toc() 
        if not isinstance(other, type(self)):
            return NotImplemented
        return (self.difficulty < other.difficulty or
                (self.difficulty == other.difficulty and self.name < other.name))

    def __hash__(self) -> int:
        return hash(self.name)

    @property
    def allowed_attempts(self) -> int:
        course = self.taskgroup.chapter.course
        return int(course.allowed_attempts_base + course.allowed_attempts_hourly*self.timevalue)

    @functools.cached_property
    def linkslist_bottom(self) -> str:
        return self._render_task_linkslist('assumed_by', 'required_by')

    @functools.cached_property
    def linkslist_top(self) -> str:
        return self._render_task_linkslist('assumes', 'requires')

    @property
    def remaining_attempts(self) -> int:
        return max(0, self.allowed_attempts - self.rejections)

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
        return f"<a {href} {titleattr}>{self.name}</a> {diffsymbol} {timevalue}{refs}"

    @property
    def toc(self) -> str:
        return self.taskgroup.toc

    def as_json(self) -> b.StrAnyDict:
        return dict(name=self.name, slug=self.name,  # slug for backwards compatibility, TODO 3: remove 2025-01
                    title=self.title, timevalue=self.timevalue, difficulty=self.difficulty,
                    assumes=self.assumes, requires=self.requires)

    def process_topmatter(self, sourcefile: str, topmatter: b.StrAnyDict, course: 'Coursebuilder'):
        b.copyattrs(sourcefile,
                    topmatter, self,
                    mustcopy_attrs='title, timevalue, difficulty',
                    cancopy_attrs='stage, explains, assumes, requires',
                    mustexist_attrs='',
                    typecheck=dict(timevalue=numbers.Number, difficulty=int))
        self.evaluate_stage(sourcefile, course)

        # ----- ensure explains/assumes/requires are lists:
        def _handle_strlist(attrname: str):
            attrvalue = getattr(self, attrname, None)
            if isinstance(attrvalue, str):
                setattr(self, attrname, re.split(r", *", attrvalue))
            elif not attrvalue:
                setattr(self, attrname, [])
            else:
                b.error(f"value of '{attrname}:' must be a (non-empty) string", file=sourcefile)
                setattr(self, attrname, [])

        _handle_strlist('explains')
        _handle_strlist('assumes')
        _handle_strlist('requires')
        # ----- add to glossary:
        if self.explains:
            for term in self.explains:
                course.glossary.explains(self.name, term)
        # ----- done:
        return self

    @classmethod
    def expand_diff(cls, call: macros.Macrocall) -> str:  # noqa
        assert call.macroname == "DIFF"
        level = int(call.arg1)
        diffrange = cls.DIFFICULTY_RANGE
        if level not in diffrange:
            call.error(f"Difficulty must be in range {min(diffrange)}..{max(diffrange)}")
            return ""
        return h.difficulty_symbol(level)

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

    def _render_task_linkslist(self, a_attr: str, r_attr: str) -> str:
        """HTML for the links to assumes/requires (or assumed_by/required_by) related tasks on a task page."""
        links = []
        a_links = sorted((f"[PARTREF::{part}]" for part in getattr(self, a_attr)))
        r_links = sorted((f"[PARTREF::{part}]" for part in getattr(self, r_attr)))
        a_cssname = a_attr.replace("_", "")
        r_cssname = r_attr.replace("_", "")
        any_links = a_links or r_links
        if any_links:
            links.append(f"\n<aside class='{a_cssname}-{r_cssname}-linkblock'>\n")
        if a_links:
            links.append(f" <div class='{a_cssname}-links'>\n   ")
            links.append("  " + macros.expand_macros("-", self.name, ", ".join(a_links)))
            links.append("\n </div>\n")
        if r_links:
            links.append(f" <div class='{r_cssname}-links'>\n")
            links.append("  " + macros.expand_macros("-", self.name, ", ".join(r_links)))
            links.append("\n </div>\n")
        if any_links:
            links.append("</aside>\n")
        return "".join(links)


class Course(el.Part):
    """
    Abstract superclass for the master data object for this run. Can be instantiated in two different forms: 
    - as Coursebuilder (for author): 
      From a handwritten YAML file, called configfile. 
      Will then read all content for a build and employ directory and cache.
    - as CourseSI (for student and instructor): 
      From a JSON metadata file generated during build.
    The present superclass contains the attributes and logic that both have in common.
    """
    MUSTCOPY_ADDITIONAL = '???'  # set in subclasses
    CANCOPY_ADDITIONAL = '???'  # set in subclasses

    context: str  # for error messages: where config data comes from
    configdict: b.StrAnyDict  # all data from c.CONFIGFILE or c.METADATAFILE
    namespace: dict[str, el.Part]  # partname -> part, for obtaining Parts in any of the logic

    instructors: list[b.StrAnyDict]
    init_data: b.StrAnyDict = dict()
    blockmacro_topmatter: dict[str, str] = dict()
    allowed_attempts: str  # "2 + 0.5/h" or so, int+decimal, h is the task timevalue multiplier
    allowed_attempts_base: int  # the int part of allowed_attempts
    allowed_attempts_hourly: float  # the decimal part of allowed_attempts

    def __init__(self, **kwargs):
        super().__init__("...", **kwargs)  # preliminary name!
        self.course = self
        self.namespace = dict()
        self._read_config(self.configdict)
        self.allowed_attempts_base, self.allowed_attempts_hourly = self._parse_allowed_attempts()


    @functools.cached_property  # beware: call this only once initialization is complete!
    def taskdict(self) -> dict[str, Task|Taskbuilder]:
        return {k:v for k,v in self.namespace.items() if isinstance(v, Task)}

    def get_part(self, context: str, partname: str) -> el.Part:
        """Return part for given partname or self (and print error msg) if no such part exists."""
        if partname in self.namespace:
            return self.namespace[partname]
        b.error(f"part '{partname}' does not exist", file=context)
        return self

    def namespace_add(self, newpart: el.Part):
        name = newpart.name
        if name in self.namespace:
            b.critical("Files '%s' and '%s':\n   part name collision" %  # critical because it makes assumptions wrong
                       (self._partpath(self.namespace[name]), self._partpath(newpart)))
        else:
            self.namespace[name] = newpart

    def task(self, taskname: str):
        """Return Task for given taskname or None if no such task exists."""
        return self.taskdict.get(taskname, None)  # noqa

    def _parse_allowed_attempts(self) -> tuple[int, float]:
        mm = re.match(r"(?P<base>\d+)(\s?\+\s?(?P<time>\d+\.\d+)\s?/\s?h)?", self.allowed_attempts)
        if not mm:
            msg1 = f"'allowed_attempts' must have a format exactly like '2 + 0.5/h' or '2'"
            b.error(f"{msg1}, not '{self.allowed_attempts}'", file=getattr(self, 'sourcefile', ''))
            return 2, 0
        return int(mm.group("base")), float(mm.group("time") or "0")

    @staticmethod
    def _partpath(p: el.Part) -> str:
        fullpath = p.sourcefile
        basename = os.path.basename(fullpath)
        dirname = os.path.dirname(fullpath)
        if basename == "index.md":
            return dirname
        else:
            return fullpath

    def _read_config(self, configdict: b.StrAnyDict):
        b.copyattrs(self.context,
                    configdict, self,
                    mustcopy_attrs=('title, name, instructors, allowed_attempts' +
                                    self.MUSTCOPY_ADDITIONAL),
                    cancopy_attrs=('init_data' +
                                   self.CANCOPY_ADDITIONAL),
                    mustexist_attrs='chapters',
                    report_extra=bool(self.MUSTCOPY_ADDITIONAL))


class CourseSI(Course):
    """Course for cmds student and instructor. Init from c.METADATA_FILE."""
    MUSTCOPY_ADDITIONAL = ''
    CANCOPY_ADDITIONAL = ''

    chapters: list['Chapter']

    def __init__(self, configdict: b.StrAnyDict, context: str):
        super().__init__(configdict=configdict, context=context)
        self.parttype = dict(Chapter=Chapter, Taskgroup=Taskgroup, Task=Task)
        self._init_parts(self.configdict)
        
    def _init_parts(self, configdict: dict):
        self.chapters = [Chapter(ch['name'], parent=self, chapterdict=ch)  # noqa
                         for ch in configdict['chapters']]



class Coursebuilder(sdrl.partbuilder.PartbuilderMixin, Course):
    """Course with the additions required for author mode. (Chapter, Taskgroup, Task have both in one.)"""
    MUSTCOPY_ADDITIONAL = ', chapterdir, altdir, stages'
    CANCOPY_ADDITIONAL = ', baseresourcedir, itreedir, templatedir, blockmacro_topmatter, htaccess_template'
    TEMPLATENAME = "homepage.html"

    include_stage: str  # lowest stage that parts must have to be included in output
    targetdir_s: str  # where to render student output files
    targetdir_i: str  # where to render instructor output files

    baseresourcedir: str = f"{sedrila_libdir}/baseresources"
    chapterdir: str
    altdir: str
    itreedir: str | None
    templatedir: str = f"{sedrila_libdir}/templates"
    htaccess_template: str = None  # structure of .htaccess file generated in instructor website
    stages: list[str]  # list of allowed values of stage in parts 

    course: 'Coursebuilder'
    chapters: list['Chapterbuilder']
    include_stage_index: int  # index in stages list, or len(stages) if include_stage is ""
    mtime: float  # in READ cache mode: tasks have changed if they are younger than this
    taskorder: list[Taskbuilder]  # If task B assumes or requires A, A will be before B in this list.
    glossary: glossary.Glossary

    def __init__(self, *, configfile: str, **kwargs):
        self.configfile = self.context = configfile
        self.configdict = b.slurp_yaml(configfile)
        super().__init__(**kwargs)
        self.parttype = dict(Chapter=Chapterbuilder, Taskgroup=Taskgroupbuilder, Task=Taskbuilder)
        self._read_config(self.configdict)
        self._init_parts(self.configdict, self.include_stage)

    @property
    def breadcrumb_item(self) -> str:
        titleattr = f"title=\"{h.as_attribute(self.title)}\""
        return f"<a href='index.html' {titleattr}>{self.name}</a>"

    @property
    def outputfile(self) -> str:
        return "index.html"

    @property
    def sourcefile(self) -> str:
        return f"{self.chapterdir}/index.md"

    @functools.cached_property
    def toc(self) -> str:
        return sdrl.partbuilder.toc(self)

    def add_inverse_links(self):
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

    def as_json(self) -> b.StrAnyDict:
        result = dict(title=self.title,
                      name=self.name, breadcrumb_title=self.name,
                      instructors=self.instructors,
                      init_data=getattr(self, 'init_data', dict()),
                      allowed_attempts=self.allowed_attempts,
                      chapters=[chapter.as_json() for chapter in self.chapters])
        return result

    def check_links(self):
        for task in self.taskdict.values():
            for assumed in task.assumes:
                if not self.namespace.get(assumed, None):
                    b.error(f"assumed part '{assumed}' does not exist", file=task.sourcefile)
            for required in task.requires:
                if not self.namespace.get(required, None):
                    b.error(f"required part '{required}' does not exist", file=task.sourcefile)

    def compute_taskorder(self):
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

    @dataclasses.dataclass
    class Volumereport:
        rows: tg.Sequence[tg.Tuple[str, int, float]]
        columnheads: tg.Sequence[str]

    def volume_report_per_chapter(self) -> Volumereport:
        return self._volume_report(self.chapters, "Chapter",
                                   lambda t, c: t.taskgroup.chapter == c, lambda c: c.name)

    def volume_report_per_difficulty(self) -> Volumereport:
        return self._volume_report(Task.DIFFICULTY_RANGE, "Difficulty",
                                   lambda t, d: t.difficulty == d, lambda d: h.difficulty_levels[d-1])

    def volume_report_per_stage(self) -> Volumereport:
        return self._volume_report(self.stages + [None], "Stage",
                                   lambda t, s: t.stage == s, lambda s: s or "done", include_all=True)

    def _add_baseresources(self):
        for direntry in os.scandir(self.baseresourcedir):
            if direntry.is_file():
                self.directory.make_the(el.Sourcefile, direntry.path)
                self.directory.make_the(el.CopiedFile, direntry.name, sourcefile=direntry.path,
                                        targetdir_s=self.targetdir_s, targetdir_i=self.targetdir_i)
            else:
                b.warning("is not a plain file. Ignored.", file=direntry)

    def _collect_zipdirs(self):
        for zf in self.directory.get_all(el.Zipfile):
            self.namespace_add(zf)

    def _init_parts(self, configdict: dict, include_stage: str):
        self.directory.record_the(Course, self.name, self)
        self.namespace_add(self)
        self.make_std_dependencies(use_toc_of=self)
        # ----- handle include_stage:
        if include_stage in self.stages:
            self.include_stage = include_stage
            self.include_stage_index = self.stages.index(include_stage)
        else:
            if include_stage != '':  # empty is allowed
                b.error(f"'--include_stage {include_stage}' not allowed, must be one of {self.stages}")
            self.include_stage = ''  # include only parts with no stage
            self.include_stage_index = len(self.stages)
        # ----- create Chapters, Taskgroups, Tasks:
        self.chapters = [Chapterbuilder(ch['name'], parent=self, chapterdict=ch) 
                         for ch in configdict['chapters']]
        # ----- create Zipdirs, Glossary:
        self.find_zipdirs()
        self._collect_zipdirs()  # TODO 3: collect only what gets referenced
        self.glossary = glossary.Glossary(c.AUTHOR_GLOSSARY_BASENAME, parent=self)
        self.directory.record_the(glossary.Glossary, self.glossary.name, self.glossary)
        self.namespace_add(self.glossary)
        # ----- create MetadataDerivation and baseresources:
        self.directory.make_the(MetadataDerivation, self.name, part=self, course=self)
        self._add_baseresources()

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


class Chapter(el.Part):
    course: Course
    chapterdict: b.StrAnyDict
    taskgroups: list['Taskgroup']

    def __init__(self, name: str, **kwargs):
        super().__init__(name, **kwargs)
        self.course.namespace_add(self)
        context = f"chapter in {self.course.context}"
        self._init_from_dict(context, self.chapterdict)
        self._init_from_file(context, self.course)
        self.taskgroups = [self.parttype['Taskgroup'](taskgroup['name'], 
                                                      parent=self, chapter=self, 
                                                      taskgroupdict=taskgroup)
                           for taskgroup in (self.chapterdict.get('taskgroups') or [])]

    def _init_from_dict(self, context: str, chapter: b.StrAnyDict):
        b.copyattrs(context,
                    chapter, self,
                    mustcopy_attrs='name',
                    mustexist_attrs='taskgroups',
                    cancopy_attrs='title,slug')

    def _init_from_file(self, context: str, course: Coursebuilder):
        pass  # only present in builder class


class Chapterbuilder(sdrl.partbuilder.PartbuilderMixin, Chapter):
    TEMPLATENAME = "chapter.html"
    course: Coursebuilder
    taskgroups: list['Taskgroupbuilder']


    @property
    def outputfile(self) -> str:
        return f"chapter-{self.name}.html"

    @property
    def sourcefile(self) -> str:
        return f"{self.course.chapterdir}/{self.name}/index.md"

    @property
    def to_be_skipped(self) -> bool:
        return self.skipthis

    @functools.cached_property
    def toc(self) -> str:
        return sdrl.partbuilder.toc(self)

    def as_json(self) -> b.StrAnyDict:
        result = dict(name=self.name, slug=self.name,  # slug for backwards compatibility, TODO 3: remove 2025-01
                      taskgroups=[taskgroup.as_json() for taskgroup in self.taskgroups])
        result.update(super().as_json())
        return result
    
    def process_topmatter(self, sourcefile: str, topmatter: b.StrAnyDict, course: Coursebuilder):
        b.copyattrs(sourcefile,
                    topmatter, self,
                    mustcopy_attrs='title',
                    cancopy_attrs='stage',
                    mustexist_attrs='',
                    overwrite=True)
        self.evaluate_stage(sourcefile, course)

    def _init_from_dict(self, context: str, chapter: b.StrAnyDict):
        super()._init_from_dict(context, chapter)
        self.directory.record_the(Chapter, self.name, self)

    def _init_from_file(self, context: str, course: Coursebuilder):
        self.make_std_dependencies(use_toc_of=self)
        self.find_zipdirs()


class Taskgroup(el.Part):
    TOC_LEVEL = 1  # indent level in table of contents
    course: Course
    chapter: Chapter
    tasks: list['Task']

    def __init__(self, name: str, **kwargs):
        super().__init__(name, **kwargs)
        context = f"taskgroup '{name}' in chapter '{self.chapter.name}'"
        self.course.namespace_add(self)
        self._init_from_dict(context, self.taskgroupdict)
        self._init_from_file(context, self.chapter)
        self._create_tasks()

    def _create_tasks(self):
        self.tasks = [Task(taskdict['name'], parent=self, taskgroup=self).from_json(taskdict)
                      for taskdict in self.taskgroupdict['tasks']]
    
    def _init_from_dict(self, context: str, taskgroupdict: b.StrAnyDict):
        b.copyattrs(context,
                    taskgroupdict, self,
                    mustcopy_attrs='name',
                    cancopy_attrs='tasks, title, slug',
                    mustexist_attrs='taskgroups')

    def _init_from_file(self, context: str, chapter: Chapter):
        pass  # exists only in builder


class Taskgroupbuilder(sdrl.partbuilder.PartbuilderMixin, Taskgroup):
    TEMPLATENAME = "taskgroup.html"
    chapter: Chapterbuilder
    tasks: list['Taskbuilder']

    @property
    def sourcefile(self) -> str:
        return f"{self.course.chapterdir}/{self.chapter.name}/{self.name}/index.md"

    @property
    def to_be_skipped(self) -> bool:
        return self.skipthis or self.chapter.to_be_skipped

    @functools.cached_property
    def toc(self) -> str:
        return sdrl.partbuilder.toc(self)

    def as_json(self) -> b.StrAnyDict:
        result = dict(name=self.name, slug=self.name,  # slug for backwards compatibility, TODO 3: remove 2025-01
                      tasks=[task.as_json() for task in self.tasks])
        result.update(super().as_json())
        return result

    def process_topmatter(self, sourcefile: str, topmatter: b.StrAnyDict, course: Coursebuilder):
        b.copyattrs(sourcefile,
                    topmatter, self,
                    mustcopy_attrs='title',
                    cancopy_attrs='stage',
                    mustexist_attrs='',
                    overwrite=True)
        self.evaluate_stage(sourcefile, course)

    def _add_task(self, task: Taskbuilder):
        task.taskgroup = self
        self.tasks.append(task)

    def _create_tasks(self):
        """Finds and reads task files."""
        self.tasks = []
        filenames = glob.glob(f"{self.course.chapterdir}/{self.chapter.name}/{self.name}/*.md")
        for filename in sorted(filenames):
            if not filename.endswith("index.md"):
                name = os.path.basename(filename[:-3])  # remove .md suffix
                self._add_task(Taskbuilder(name, parent=self, taskgroup=self))

    def _init_from_dict(self, context: str, taskgroupdict: b.StrAnyDict):
        super()._init_from_dict(context, taskgroupdict)
        self.directory.record_the(Taskgroup, self.name, self)

    def _init_from_file(self, context, chapter):
        self.make_std_dependencies(use_toc_of=self)
        self.find_zipdirs()


class MetadataDerivation(el.Step):
    """Copy Topmatter into Parts' attributes, compute assumedby/requiredby/taskorder, check links."""
    course: Coursebuilder

    def do_build(self):
        # ----- copy topmatter into Parts' attributes:
        dir = self.directory
        allparts = list(itertools.chain(dir.get_all(Chapter), dir.get_all(Taskgroup), dir.get_all(Task)))
        for part in allparts:
            topmatter = self.directory.get_the(el.Topmatter, part.name)
            part.process_topmatter(part.sourcefile, topmatter.value, self.course)
            part.evaluate_stage(part.sourcefile, part.course)
        # ----- compute and check stuff:
        self.course.add_inverse_links()
        self.course.compute_taskorder()
        self.course.check_links()
