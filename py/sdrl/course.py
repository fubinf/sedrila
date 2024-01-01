"""
Represent and handle the contents of SeDriLa: Course, Chapter, Taskgroup, Task.
There are two ways how these objects can be instantiated:
In 'author' mode, 'read_contentfiles' is true and metadata comes from sedrila.yaml and the partfiles.
Otherwise, 'read_contentfiles' is false and metadata comes from METADATA_FILE. 
"""

import functools
import glob
import graphlib
import os
import re
import typing as tg

import yaml

import base as b
import sdrl.html as h
import sdrl.markdown as md

class Structurepart:
    """Common superclass"""
    TOC_LEVEL = 0  # indent level in table of contents
    sourcefile: str = "???"  # the originating pathname
    outputfile: str  # the target pathname
    metadata_text: str  # the YAML front matter character stream
    metadata: b.StrAnyDict  # the YAML front matter
    content: str  # the markdown block
    slug: str  # the file/dir basename by which we refer to the part
    title: str  # title: value
    shorttitle: str  # shorttitle: value
    stage: str = ''  # stage: value
    skipthis: bool  # do not include this chapter/taskgroup/task in generated site
    toc: str  # table of contents

    @property
    def breadcrumb_item(self) -> str:
        return "(undefined)"

    @property
    def toc_entry(self) -> str:
        classes = f"stage-{self.stage}" if self.stage else "no-stage"
        return h.indented_block(self.toc_link_text, self.TOC_LEVEL, classes)


    def as_json(self) -> b.StrAnyDict:
        return dict(title=self.title, shorttitle=self.shorttitle)

    def evaluate_stage(self, context: str, course: 'Course') -> None:
        """
        Cut the 'stage' attribute down to its first word, check it against course.stages, report violations.
        Set self.skipthis according to course.include_stage.
        """
        self.skipthis = False  # default case
        # ----- handle parts with no 'stage:' given:
        if not getattr(self, 'stage', ''):
            return
        # ----- extract first word from stage:
        mm = re.match(r'\w+', self.stage)  # match first word
        stageword = mm.group(0) if mm else ''
        # ----- handle parts with unknown stage (error):
        try:
            stage_index = course.stages.index(stageword)
        except ValueError:
            b.error(f"{context}: Illegal value of 'stage': '{stageword}'")
            return
        # ----- handle parts with known stage:
        self.skipthis = course.include_stage_index > stage_index

    def read_partsfile(self, file: str):
        """
        Reads files consisting of YAML metadata, then Markdown text, separated by a tiple-dash line.
        Stores metadata into self.metadata, rest into self.content.
        """
        SEPARATOR = "---\n"
        # ----- obtain file contents:
        self.sourcefile = file
        text = b.slurp(file)
        if SEPARATOR not in text:
            b.error(f"{self.sourcefile}: triple-dash separator is missing")
            return
        self.metadata_text, self.content = text.split(SEPARATOR, 1)
        # ----- parse metadata
        try:
            # ----- parse YAML data:
            self.metadata = yaml.safe_load(self.metadata_text)
        except yaml.YAMLError as exc:
            b.error(f"{self.sourcefile}: metadata YAML is malformed: {str(exc)}")


class Task(Structurepart):
    DIFFICULTY_RANGE = range(1, len(h.difficulty_levels) + 1)
    TOC_LEVEL = 2  # indent level in table of contents

    timevalue: tg.Union[int, float]  # task timevalue: (in hours)
    difficulty: int  # difficulty: int from DIFFICULTY_RANGE
    assumes: list[str] = []  # tasknames: This knowledge is assumed to be present
    requires: list[str] = []  # tasknames: These specific results will be reused here
    assumed_by: list[str] = []  # tasknames: inverse of assumes
    required_by: list[str] = []  # tasknames: inverse of requires
    profiles: list[str] = []  # profile shortnames: specialty areas task pertains to
    workhours: float = 0.0  # time student has worked on this according to commit msgs
    accepted: bool = False  # whether instructor has ever marked it 'accept'
    rejections: int = 0  # how often instructor has marked it 'reject'

    taskgroup: 'Taskgroup'  # where the task belongs

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
        titleattr = f"title=\"{self.slug}\""
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

    def from_file(self, file: str, taskgroup: 'Taskgroup') -> 'Task':
        """Initializer used in author mode"""
        self.read_partsfile(file)
        # ----- get taskdata from filename:
        nameparts = os.path.basename(self.sourcefile).split('.')
        assert len(nameparts) == 2  # taskname, suffix 'md'
        self.slug = nameparts[0]  # must be globally unique
        self.outputfile = f"{self.slug}.html"
        b.copyattrs(file,
                    self.metadata, self,
                    mustcopy_attrs='title, timevalue, difficulty',
                    cancopy_attrs='stage, assumes, requires, profiles',  # TODO 2: check profiles against sedrila.yaml
                    mustexist_attrs='')
        self.evaluate_stage(file, taskgroup.chapter.course)

        # ----- ensure assumes/requires/profiles are lists:
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

        _handle_strlist('assumes')
        _handle_strlist('requires')
        _handle_strlist('profiles')
        return self

    def from_json(self, task: b.StrAnyDict, taskgroup: 'Taskgroup') -> 'Task':
        """Initializer used in student and instructor mode"""
        self.taskgroup = taskgroup
        self.slug = task['slug']
        self.title = task['title']
        self.timevalue = task['timevalue']
        self.difficulty = task['difficulty']
        self.assumes = task['assumes']
        self.requires = task['requires']
        self.profiles = task['profiles']
        return self

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
    def expand_diff(cls, call: md.Macrocall) -> str:  # noqa
        assert call.macroname == "DIFF"
        level = int(call.arg1)
        diffrange = cls.DIFFICULTY_RANGE
        if level not in diffrange:
            call.error(f"Difficulty must be in range {min(diffrange)}..{max(diffrange)}")
            return ""
        return h.difficulty_symbol(level)


class Course(Structurepart):
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
    blockmacro_topmatter: dict[str, str]
    instructors: list[b.StrAnyDict]
    profiles: list[str]  # list of all allowed profile shortnames
    chapters: list['Chapter']
    taskorder: list[Task]  # If task B assumes or requires A, A will be before B in this list.
    stages: list[str]  # list of allowed values of stage in parts 
    include_stage: str  # lowest stage that parts must have to be included in output
    include_stage_index: int  # index in stages list, or len(stages) if include_stage is ""

    def __init__(self, configfile: str, read_contentfiles: bool, include_stage: str):
        self.configfile = configfile
        configdict = b.slurp_yaml(configfile)
        b.copyattrs(configfile, 
                    configdict, self,
                    mustcopy_attrs='title, shorttitle, instructors, profiles, stages',
                    cancopy_attrs='baseresourcedir, chapterdir, templatedir, blockmacro_topmatter',
                    mustexist_attrs='chapters')
        self.outputfile = "index.html"
        if read_contentfiles:
            self.read_partsfile(f"{self.chapterdir}/index.md")
        if include_stage in self.stages:
            self.include_stage = include_stage
            self.include_stage_index = self.stages.index(include_stage)
        else:
            if include_stage != '':  # empty is allowed
                b.error(f"'--include_stage {include_stage}' not allowed, must be one of [self.stages]")
            self.include_stage = ''  # include only parts with no stage
            self.include_stage_index = len(self.stages)
        self.chapters = [Chapter(self, ch, read_contentfiles) 
                         for ch in configdict['chapters']]
        self._check_links()
        self._add_inverse_links()
        self._compute_taskorder()

    @property
    def breadcrumb_item(self) -> str:
        titleattr = f"title=\"{h.as_attribute(self.title)}\""
        return f"<a href='index.html' {titleattr}>{self.shorttitle}</a>"

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
            if t.slug in result:
                b.error(f"duplicate task: '{t.sourcefile}'\t'{result[t.slug].sourcefile}'")
            else:
                result[t.slug] = t
        return result

    def as_json(self) -> b.StrAnyDict:
        result = dict(baseresourcedir=self.baseresourcedir, 
                      chapterdir=self.chapterdir,
                      templatedir=self.templatedir,
                      instructors=self.instructors,
                      profiles=self.profiles,
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


class Chapter(Structurepart):
    course: Course
    taskgroups: tg.Sequence['Taskgroup']
    
    def __init__(self, course: Course, chapter: b.StrAnyDict, read_contentfiles: bool):
        self.course = course
        context = f"chapter in {course.configfile}"
        b.copyattrs(context, 
                    chapter, self,
                    mustcopy_attrs='title, shorttitle, slug',
                    cancopy_attrs='stage',
                    mustexist_attrs='taskgroups')
        self.evaluate_stage(context, course)
        if read_contentfiles:
            self.read_partsfile(f"{self.course.chapterdir}/{self.slug}/index.md")
            b.copyattrs(context, 
                        self.metadata, self,
                        mustcopy_attrs='',
                        cancopy_attrs='todo',
                        mustexist_attrs='', overwrite=False)
        self.taskgroups = [Taskgroup(self, taskgroup, read_contentfiles) 
                           for taskgroup in (chapter.get('taskgroups') or [])]

    @property
    def breadcrumb_item(self) -> str:
        titleattr = f"title=\"{h.as_attribute(self.title)}\""
        return f"<a href='{self.outputfile}' {titleattr}>{self.shorttitle}</a>"

    @property
    def outputfile(self) -> str:
        return f"chapter-{self.slug}.html"

    @property
    def to_be_skipped(self) -> bool:
        return self.skipthis

    @property
    def toc_link_text(self) -> str:
        titleattr = f"title=\"{self.slug}\""
        return f"<a href='{self.outputfile}' {titleattr}>{self.title}</a>"

    def as_json(self) -> b.StrAnyDict:
        result = dict(slug=self.slug, 
                      taskgroups=[taskgroup.as_json() for taskgroup in self.taskgroups])
        result.update(super().as_json())
        return result


class Taskgroup(Structurepart):
    TOC_LEVEL = 1  # indent level in table of contents
    chapter: Chapter
    tasks: list['Task']

    def __init__(self, chapter: Chapter, taskgroupdict: b.StrAnyDict, read_contentfiles: bool):
        self.chapter = chapter
        context = f"taskgroup in chapter {chapter.slug}"
        b.copyattrs(context,
                    taskgroupdict, self,
                    mustcopy_attrs='title, shorttitle, slug',
                    cancopy_attrs='tasks, stage',
                    mustexist_attrs='taskgroups')
        self.outputfile = f"{self.slug}.html"
        if read_contentfiles:
            self.read_partsfile(f"{self.chapter.course.chapterdir}/{self.chapter.slug}/{self.slug}/index.md")
            b.copyattrs(context,
                        self.metadata, self,
                        mustcopy_attrs='',
                        cancopy_attrs='minimum, todo',
                        mustexist_attrs='', overwrite=False)
        self.evaluate_stage(context, chapter.course)
        if read_contentfiles:
            self._create_tasks()
        else:
            self.tasks = [Task().from_json(taskdict, taskgroup=self)
                          for taskdict in taskgroupdict['tasks']]

    @property
    def breadcrumb_item(self) -> str:
        titleattr = f"title=\"{h.as_attribute(self.title)}\""
        return f"<a href='{self.outputfile}' {titleattr}>{self.shorttitle}</a>"

    @property
    def toc_link_text(self) -> str:
        titleattr = f"title=\"{self.slug}\""
        return f"<a href='{self.outputfile}' {titleattr}>{self.title}</a>"

    @property
    def to_be_skipped(self) -> bool:
        return self.skipthis or self.chapter.to_be_skipped

    def as_json(self) -> b.StrAnyDict:
        result = dict(slug=self.slug, 
                      tasks=[task.as_json() for task in self.tasks])
        result.update(super().as_json())
        return result

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
                self._add_task(Task().from_file(filename, taskgroup=self))
