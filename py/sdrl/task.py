"""Representation and operations for a single task within a SeDriLa course."""
import logging
import os.path
import typing as tg

import base as b
import sdrl.html as h

logger = logging.getLogger()

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

    def __init__(self, file: str, text: str=None):
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
        #----- semantic checks:
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

    def toc_link(self, level=0) -> str:
        description = h.as_attribute(self.description)
        href = f"href='{self.outputfile}'"
        titleattr = f"title=\"{description}\""
        diffsymbol = h.difficulty_symbol(self.difficulty)
        effort = f"<span title='Effort: {self.effort} hours'>{self.effort}h"
        return h.indented_block(f"<a {href} {titleattr}>{self.title}</a> {diffsymbol} {effort}", level)

    def _as_list(self, obj) -> tg.List:
        return obj if isinstance(obj, list) else list(obj)


Tasks = tg.Mapping[str, Task]  # taskname -> task