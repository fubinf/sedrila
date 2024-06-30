import re

import yaml

import base as b
import cache
import sdrl.directory as dir
import sdrl.html as h



class PartbuilderMixin:  # to be mixed into a Part class
    cache: cache.SedrilaCache
    directory: dir.Directory
    metadata_text: str  # the YAML front matter character stream
    metadata: b.StrAnyDict  # the YAML front matter
    content: str  # the markdown block
    linkslist_top: str = ''  # generated HTML of cross reference links
    linkslist_bottom: str = ''  # generated HTML of cross reference links
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
        return h.indented_block(self.toc_link_text, self.TOC_LEVEL, classes)

    @property
    def toc_link_text(self) -> str:
        titleattr = f"title=\"{self.title}\""
        return f"<a href='{self.outputfile}' {titleattr}>{self.slug}</a>"

    def as_json(self) -> b.StrAnyDict:
        return dict(title=self.title)

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
            self.metadata = dict()  # use empty metadata as a weak replacement
