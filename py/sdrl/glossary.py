"""Data structure, macros, and page generation for a glossary page (term dictionary and cross-reference)"""
import typing as tg

import base as b
import cache
import sdrl.constants as c
import sdrl.elements as el
import sdrl.macros as macros
import sdrl.markdown as md
import sdrl.partbuilder


class Glossary(sdrl.partbuilder.PartbuilderMixin, el.Part):
    """
    Processed in two phases: in phase 1, term references and term definitions are collected.
    Links to term definitions can already be generated because they have a canonical form:
    An anchor will exist on the glossary page for each alias of a term.
    In phase 2, the collected data are used to generate the actual glossary page or error messages.
    Defines macros TERM0 and TERM to be used in the glossary file and
    TERMREF to be used anywhere.
    """
    TEMPLATENAME = 'glossary.html'
    body_s: el.Body_s  # we derive body_i 
    course: 'sdrl.course.Coursebuilder'
    explainedby: dict[str, set[str]]  # explainedby[term] == partnames_with_explain
    mentionedby: dict[str, set[str]]  # mentionedby[term] == partnames_with_termref
    termdefs: set[str]  # what has a [TERMx] in glossary.md
    term_linkslist: tg.Optional[list[str]]  # the lines of the linksblock
    rendered_content: str = ''  # results of render(); re-render would report duplicate definitions
    includefiles: list[str]  # files INCLUDEd while rendering the glossary
    
    def __init__(self, name, **kwargs):
        super().__init__(name, **kwargs)
        self.read_partsfile(self.sourcefile)
        b.copyattrs(self.sourcefile, self.metadata, self,
                    mustcopy_attrs='title',
                    cancopy_attrs='stage',
                    mustexist_attrs='')
        self.explainedby = dict()
        self.mentionedby = dict()
        self.termdefs = set()
        self.term_linkslist = None  # set by [TERM], used and unset by [ENDTERM]
        self.register_macros_phase1()
        self.directory.make_the(el.Sourcefile, self.sourcefile)
        self.make_dependency(el.Topmatter, part=self)
        self.make_dependency(el.Glossarybody, part=self, includelist_class=el.IncludeList_s,
                             switch_macros_op=self.register_macros_phase2)
        self.make_dependency(el.Toc, part=self)

    def check_existing_resource(self):
        super().check_existing_resource()
        if self.state == cache.State.AS_BEFORE and self.cache.is_dirty(self.sourcefile):
            self.state = cache.State.HAS_CHANGED  # ensure repetition of error messages

    def do_build(self):
        b.debug(f"do_build({self.cache_key}):")
        body = self.directory.get_the(el.Glossarybody, self.name).value  # noqa
        self.render_structure(self.course, self, body, self.targetdir_s)  # noqa
        self.render_structure(self.course, self, body, self.targetdir_i, info=False)  # noqa
        self.report_issues()

    @property
    def sourcefile(self) -> str:
        return f"{self.course.chapterdir}/{c.AUTHOR_GLOSSARY_BASENAME}.md"

    @property
    def toc(self) -> str:
        """Return a chapters-only table of contents for the glossary."""
        result = ['']  # start with a newline
        for chapter in self.course.chapters:  # noqa
            if chapter.to_be_skipped:
                continue
            result.append(chapter.toc_entry)
        result.append(self.toc_entry)
        return "\n".join(result)

    @property
    def toc_link_text(self) -> str:
        return f"<a href='{self.outputfile}'>{self.title}</a>"

    def explains(self, partname: str, term: str):  # called by author.py
        if term not in self.explainedby:
            self.explainedby[term] = set()
        if not self.course.get_part(self.sourcefile, partname).to_be_skipped:
            self.explainedby[term].add(partname)

    def mentions(self, partname: str, term: str):
        if term not in self.mentionedby:
            self.mentionedby[term] = set()
        if not self.course.get_part(self.sourcefile, partname).to_be_skipped:
            self.mentionedby[term].add(partname)

    def fill_mentionedbylists(self):
        """
        explainedby is filled because of Part.process_topmatter().
        mentionedby is incompletely filled because most markdown does not get rendered in a given build.
        We fill it here properly from the TermrefList objects.
        """
        for termreflist in self.directory.get_all(el.TermrefList):
            for term in termreflist.value:
                self.mentions(termreflist.part.name, term)

    def render(self, mode: b.Mode):
        """We render only once, because the glossary will not contain [INSTRUCTOR] calls."""
        if not self.rendered_content:
            self.register_macros_phase2()
            mddict = md.render_markdown(self.sourcefile, self.name, self.content, mode, dict())
            self.rendered_content, self.includefiles = (mddict['html'], mddict['includefiles'])
    
    def report_issues(self):
        terms_explained = set(self.explainedby.keys())
        terms_mentioned = set(self.mentionedby.keys())
        undefined_terms = (terms_explained | terms_mentioned) - self.termdefs
        if undefined_terms:
            what = "This term lacks" if len(undefined_terms) == 1 else "These terms lack"
            b.error(f"{what} a definition: {sorted(undefined_terms)}", file=self.sourcefile)

    def register_macros_phase1(self):
        macros.register_macro("TERMREF", 1, macros.MM.INNER, self._expand_termref)
        macros.register_macro("TERMREF2", 2, macros.MM.INNER, self._expand_termref)
        # --- the following will be redefined in phase2:
        macros.register_macro("TERM0", 1, macros.MM.INNER, self._complain_term)
        macros.register_macro("TERM", 1, macros.MM.BLOCKSTART, self._complain_term)
        macros.register_macro("ENDTERM", 0, macros.MM.BLOCKEND, self._ignore_endtermlong)

    def register_macros_phase2(self):
        macros.register_macro("TERM0", 1, macros.MM.INNER, self._expand_term0, redefine=True)
        macros.register_macro("TERM", 1, macros.MM.BLOCKSTART, self._expand_term, redefine=True)
        macros.register_macro("ENDTERM", 0, macros.MM.BLOCKEND, self._expand_endterm, redefine=True)

    def _expand_termref(self, macrocall: macros.Macrocall) -> str:
        term = macrocall.arg1
        label = term if not macrocall.arg2 else macrocall.arg2  # unify calls to TERMREF and TERMREF2
        if label.startswith("-"):  # arg2 is meant to be a suffix
            label = f"{term}{label[1:]}"
        elif label.startswith("&ndash;"):  # e.g. [TERMREF2::class::--like] for 'class-like', but
            # Markdown extension smarty has garbled the '--' into '&ndash;' 
            label = f"{term}-{label[len('&ndash;'):]}"
        target = "%s.html#%s" % (c.AUTHOR_GLOSSARY_BASENAME, b.slugify(term))
        self._macro_mentions(macrocall, term)
        return (f"<a href='{target}' class='glossary-termref-term'>"
                f"{label}<span class='glossary-termref-suffix'></span></a>")

    def _complain_term(self, mc: macros.Macrocall) -> str:  # noqa
        b.error(f"{mc.macrocall_text}': [{mc.macroname}] can only be used in the glossary", file=mc.filename)
        return ""  # no expansion in phase 1

    def _ignore_endtermlong(self, macrocall: macros.Macrocall) -> str:  # noqa
        return ""

    def _expand_term0(self, macrocall: macros.Macrocall) -> str:
        """[TERM0::term|second form of term|third form|and so on], no definition text is supplied"""
        macrocall.arg2 = ""  # empty body
        return self._expand_termdef(macrocall)

    def _expand_term(self, macrocall: macros.Macrocall) -> str:
        """[TERM::term|second form of term|et cetera]"""
        open_body = "\n<div class='glossary-term-body'>\n\n"
        result = "".join(self._expand_any_termdef(macrocall)) + open_body
        return result
    
    def _expand_termdef(self, macrocall: macros.Macrocall) -> str:
        """allows two-argument macro calls that include a short definition"""
        termdef = macrocall.arg2
        result = self._expand_any_termdef(macrocall)
        # ----- generate body:
        if termdef:
            result.append(f"<span class='glossary-term-body'>{termdef}</span>\n\n")
        # ----- generate linkblock:
        result.extend(self.term_linkslist)
        self.term_linkslist = None
        # ----- done!:
        return "".join(result)

    def _expand_endterm(self, macrocall: macros.Macrocall) -> str:
        """[ENDTERM]  (a [TERM] has to be open)"""
        close_body = "\n\n</div>\n"
        if self.term_linkslist is not None:
            result = self.term_linkslist
            self.term_linkslist = None
            return close_body + "".join(result)
        else:
            b.error(f"[ENDTERM] is lacking its [TERM::...]", file=macrocall.filename)
            return ""

    @staticmethod
    def _collect_parts(termrefdict: dict[str, set[str]], termslist: list[str]) -> set[str]:
        """
        termslist is the list of aliases of a term.
        termrefdict maps a term (main or alias) to a set of partnames refering to it.
        Returns the set of partnames refering to one of the terms in termslist: The union
        of the respective termrefdict entry sets.
        """
        result = set()
        for term in termslist:
            if term in termrefdict:
                result |= termrefdict[term]
        return result

    def _expand_any_termdef(self, macrocall: macros.Macrocall) -> list[str]:  # [TERM0], [TERM]
        """Sets self.term_linkslist as a side effect."""
        separator = '|'
        myfile, mypart = macrocall.filename, macrocall.partname
        terms = macrocall.arg1
        termslist = terms.split(separator)
        headingtext = " | ".join(termslist)  # we keep the original order
        result = []
        # ----- report duplicate entries:
        for term in termslist:
            if term in self.termdefs:
                b.error(f"{macrocall.macrocall_text}: Term '{term}' is already defined", file=macrocall.filename)
            self.termdefs.add(term)
        # ----- open block:
        result.append("\n<div class='glossary-term-block'>\n")
        # ----- generate anchors:
        anchors = ("<a id='%s'></a>\n" % b.slugify(term) for term in termslist)
        result.extend(anchors)
        # ----- generate heading:
        result.append(f"<span class='glossary-term-heading'>{headingtext}</span>\n")
        # ----- generate links:
        links = []
        explainedby_names = self._collect_parts(self.explainedby, termslist)
        mentionedby_names = self._collect_parts(self.mentionedby, termslist)
        explainedby_links = sorted((f"[PARTREF::{p}]" for p in explainedby_names))
        mentionedby_links = sorted((f"[PARTREF::{p}]" for p in mentionedby_names))
        any_links = explainedby_links or mentionedby_links
        if any_links:
            links.append("\n<div class='glossary-term-linkblock'>\n")
        if explainedby_links:
            links.append(" <div class='glossary-term-links-explainedby'>\n   ")
            links.append(macros.expand_macros(myfile, mypart,  ", ".join(explainedby_links)))
            links.append("\n </div>\n")
        if mentionedby_links:
            links.append(" <div class='glossary-term-links-mentionedby'>\n")
            links.append("  " + macros.expand_macros(myfile, mypart, ", ".join(mentionedby_links)))
            links.append("\n </div>\n")
        if any_links:
            links.append("</div>\n")
        # ----- close block:
        result.append("\n</div>\n")
        if self.term_linkslist is not None:
            b.error(f"{macrocall.macrocall_text} is preceeded by a [TERM] with no [ENDTERM]", 
                    file=macrocall.filename)
        self.term_linkslist = links
        # ----- done!:
        return result

    def _macro_mentions(self, macrocall: macros.Macrocall, term: str):  # called by phase 1 TERMREF macro expansion
        partname = macrocall.partname
        if partname and partname != c.AUTHOR_GLOSSARY_BASENAME:  # avoid links from glossary to itself
            macrocall.md.termrefs.add(term)
