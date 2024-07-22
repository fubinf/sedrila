"""Helper functionality extracted from Parts and Pieces to make them lighter."""
import glob
import os
import re
import typing as tg

import jinja2
import yaml

import base as b
import sdrl.directory as dir
import sdrl.elements as el
import sdrl.html as h


class PartbuilderMixin(el.DependenciesMixin):  # to be mixed into a Part class
    directory: dir.Directory
    metadata_text: str  # the YAML front matter character stream
    metadata: b.StrAnyDict  # the YAML front matter
    content: str  # the markdown block
    stage: str = ''  # stage: value
    skipthis: bool  # do not include this chapter/taskgroup/task in generated site
    toc: str  # table of contents

    @property
    def breadcrumb_item(self) -> str:
        return "(undefined)"

    @property
    def to_be_skipped(self) -> bool:
        return ...  # defined in concrete part classes

    @property
    def toc_entry(self) -> str:
        classes = f"stage-{self.stage}" if self.stage else "no-stage"
        return h.indented_block(self.toc_link_text, self.TOC_LEVEL, classes)  # noqa

    @property
    def toc_link_text(self) -> str:
        titleattr = f"title=\"{self.title}\""  # noqa
        return f"<a href='{self.outputfile}' {titleattr}>{self.slug}</a>"  # noqa

    def do_build(self):
        body_s = self.directory.get_the(el.Body_s, self.name).value  # noqa
        body_i = self.directory.get_the(el.Body_i, self.name).value  # noqa
        self.render_structure(self.course, self, body_s, self.targetdir_s)  # noqa
        self.render_structure(self.course, self, body_i, self.targetdir_i)  # noqa

    def as_json(self) -> b.StrAnyDict:
        return dict(title=self.title)  # noqa

    def evaluate_stage(self, context: str, course) -> None:
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

    def find_zipdirs(self):
        """find all dirs (not files!) *.zip in self.sourcefile dir (not below!), warns about *.zip files"""
        inputdir = os.path.dirname(self.sourcefile)  # noqa
        zipdirs = glob.glob(f"{inputdir}/*.zip")
        for zipdirname in zipdirs:
            if os.path.isdir(zipdirname):
                zipfilename = os.path.basename(zipdirname)
                self.directory.make_the(el.Zipdir, zipdirname)
                self.directory.make_the(el.Zipfile, zipfilename, parent=self.my_course, 
                                        sourcefile=zipdirname, title=zipfilename)
            else:
                b.warning(f"'{zipdirname}' is a file, not a dir, and will be ignored.", file=self.sourcefile)
    
    def make_std_dependencies(self, toc: tg.Optional[el.Part], body_buildwrapper: el.Buildwrapper = None):
        self.add_dependency(self.directory.make_the(el.Sourcefile, self.sourcefile))  # noqa
        self._make(el.Topmatter, sourcefile=self.sourcefile)  # noqa
        self._make(el.Content)
        self._make(el.IncludeList_s)
        self._make(el.IncludeList_i)
        self._make(el.Body_s, sourcefile=self.sourcefile, buildwrapper=body_buildwrapper)  # noqa
        self._make(el.Body_i, sourcefile=self.sourcefile, buildwrapper=body_buildwrapper)  # noqa
        if toc:
            self.add_dependency(self.directory.make_or_get_the(el.Toc, toc.name, part=toc))

    def process_topmatter(self, sourcefile: str, topmatter: b.StrAnyDict, course):
        assert False  # must be defined in concrete classes

    def read_partsfile(self, file: str):
        """
        Reads files consisting of YAML metadata, then Markdown text, separated by a tiple-dash line.
        Stores metadata into self.metadata, rest into self.content.
        """
        SEPARATOR = "---\n"
        # ----- obtain file contents:
        text = b.slurp(file)
        if SEPARATOR not in text:
            b.error(f"{self.sourcefile}: triple-dash separator is missing")  # noqa
            return
        self.metadata_text, self.content = text.split(SEPARATOR, 1)
        # ----- parse metadata
        try:
            # ----- parse YAML data:
            self.metadata = yaml.safe_load(self.metadata_text)
        except yaml.YAMLError as exc:
            b.error(f"{self.sourcefile}: metadata YAML is malformed: {str(exc)}")  # noqa
            self.metadata = dict()  # use empty metadata as a weak replacement

    def render_structure(self, course, part: el.Part, body: str, targetdir: str):
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(course.templatedir), autoescape=False)
        template = env.get_template(self.TEMPLATENAME)  # noqa
        output = template.render(sitetitle=course.title,
                                 breadcrumb=h.breadcrumb(*self.structure_path()[::-1]),
                                 title=part.title,
                                 linkslist_top=getattr(part, 'linkslist_top', ""),
                                 linkslist_bottom=getattr(part, 'linkslist_bottom', ""),
                                 part=self,
                                 toc=part.toc,
                                 content=body)
        b.spit(f"{targetdir}/{self.outputfile}", output)  # noqa
        b.info(f"{targetdir}/{self.outputfile}")  # noqa

    def structure_path(structure: el.Part) -> list[el.Part]:
        """List of nested parts, from a given part up to the course."""
        import sdrl.course
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

    def _make(self, mytype, **kwargs):  # abbrev
        self.add_dependency(self.directory.make_the(mytype, self.name, **kwargs))  # noqa


def toc(structure: el.Part) -> str:
    """Return a table-of-contents HTML fragment for the given structure via structural recursion."""
    import sdrl.course
    parts = structure.structure_path()
    fulltoc = len(parts) == 1  # path only contains course
    assert isinstance(parts[-1], sdrl.course.Coursebuilder)
    course = tg.cast(sdrl.course.Coursebuilder, parts[-1])
    result = ['']  # start with a newline
    for chapter in course.chapters:  # noqa
        if chapter.to_be_skipped:
            continue
        result.append(chapter.toc_entry)
        if not fulltoc and chapter not in parts:
            continue
        for taskgroup in chapter.taskgroups:
            effective_tasklist = [t for t in course.taskorder 
                                  if t in taskgroup.tasks and not t.to_be_skipped]
            if taskgroup.to_be_skipped or not effective_tasklist:
                continue
            result.append(taskgroup.toc_entry)
            if not fulltoc and taskgroup not in parts:
                continue
            for task in effective_tasklist:
                result.append(task.toc_entry)
    result.append(course.glossary.toc_entry)
    return "\n".join(result)
