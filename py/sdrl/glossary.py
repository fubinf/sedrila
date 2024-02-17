"""Data structure, macros, and page generation for a glossary page (term dictionary and cross-reference)"""

import typing as tg

import base as b
import sdrl.html as h
import sdrl.macros as macros
import sdrl.markdown as md
import sdrl.part as part


class Glossary(part.Structurepart):
    """
    Processed in two phases: in phase 1, term references and term definitions are collected.
    Links to term definitions can already be generated because they have a canonical form:
    An anchor will exist on the glossary page for each alias of a term.
    In phase 2, the collected data are used to generate the actual glossary page or error messages.
    Defines macros TERM0 and TERM to be used in the glossary file and
    TERMREF to be used anywhere.
    """
    chapterdir: str  # where to find GLOSSARY_FILE
    explainedby: dict[str, set[str]]  # explainedby[term] == partnames_with_explain
    mentionedby: dict[str, set[str]]  # mentionedby[term] == partnames_with_termref
    termdefs: set[str]  # what has a [TERMx] in glossary.md
    term_linkslist: tg.Optional[list[str]]  # the lines of the linksblock
    rendered_content: str = ''  # cached results of render() to avoid reporting duplicate definitions
    
    def __init__(self, chapterdir: str):
        self.chapterdir = chapterdir
        self.read_partsfile(f"{self.chapterdir}/{b.GLOSSARY_BASENAME}.md")
        b.copyattrs(self.sourcefile, self.metadata, self,
                    mustcopy_attrs='title',
                    cancopy_attrs='stage',
                    mustexist_attrs='')
        self.outputfile = f"{b.GLOSSARY_BASENAME}.html"
        self.slug = b.GLOSSARY_BASENAME
        self.explainedby = dict()
        self.mentionedby = dict()
        self.termdefs = set()
        self.term_linkslist = None  # set by [TERM], used and unset by [ENDTERM]
        self._register_macros_phase1()

    @property
    def breadcrumb_item(self) -> str:
        titleattr = f"title=\"{h.as_attribute(self.slug)}\""
        return f"<a href='{self.outputfile}' {titleattr}>{self.title}</a>"

    @property
    def toc_link_text(self) -> str:
        return self.breadcrumb_item

    def explains(self, partname: str, term: str):  # called by author.py
        if term not in self.explainedby:
            self.explainedby[term] = set()
        self.explainedby[term].add(partname)

    def render(self, mode: b.Mode) -> str:
        """We render only once, because the glossary will not contain [INSTRUCTOR] calls."""
        if not self.rendered_content:
            self._register_macros_phase2()
            self.rendered_content= md.render_markdown(self.sourcefile, self.slug, self.content, mode, dict())
        return self.rendered_content
    
    def report_issues(self):
        terms_explained = set(self.explainedby.keys())
        terms_mentioned = set(self.mentionedby.keys())
        undefined_terms = (terms_explained|terms_mentioned) - self.termdefs
        if undefined_terms:
            what = "This term lacks" if len(undefined_terms) == 1 else "These terms lack"
            b.error(f"{self.sourcefile}: {what} a definition: {sorted(undefined_terms)}")

    def _register_macros_phase1(self):
        macros.register_macro("TERMREF", 1, self._expand_termref)
        macros.register_macro("TERMREF2", 2, self._expand_termref)
        macros.register_macro("TERM0", 1, self._complain_term)
        macros.register_macro("TERM", 1, self._complain_term)
        macros.register_macro("ENDTERM", 0, self._ignore_endtermlong)

    def _register_macros_phase2(self):
        macros.register_macro("TERM0", 1, self._expand_term0, redefine=True)
        macros.register_macro("TERM", 1, self._expand_term, redefine=True)
        macros.register_macro("ENDTERM", 0, self._expand_endterm, redefine=True)

    # ----- internals:
    
    # def _pseudoexpand(self, *args, **kwargs):  # for debugging
    #    print("_pseudoexpand(self = ", self, ", args =", args, ", kwargs =", kwargs)
    
    def _expand_termref(self, macrocall: macros.Macrocall) -> str:
        term = macrocall.arg1
        label = term if not macrocall.arg2 else macrocall.arg2  # unify calls to TERMREF and TERMREF2
        if label.startswith("-"):  # arg2 is meant to be a suffix
            label = term + label[1:]
        target = "%s.html#%s" % (b.GLOSSARY_BASENAME, b.slugify(term))
        self._mentions(macrocall.partname, term)
        return f"<a href='{target}' class='glossary-termref-term'>{label}<span class='glossary-termref-suffix'></span></a>"

    def _complain_term(self, mc: macros.Macrocall) -> str:  # noqa
        b.error(f"'{mc.filename}: {mc.macrocall_text}': [{mc.macroname}] can only be used in the glossary")
        return ""  # no expansion in phase 1

    def _ignore_endtermlong(self, macrocall: macros.Macrocall) -> str:  # noqa
        return ""

    def _expand_term0(self, macrocall: macros.Macrocall) -> str:
        """[TERM::term|second form of term|third form|and so on], no definition text is supplied"""
        macrocall.arg2 = ""  # empty body
        return self._expand_termdef(macrocall)

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

    def _expand_term(self, macrocall: macros.Macrocall) -> str:
        """[TERM::term|second form of term|etc]"""
        open_body = "\n<div class='glossary-term-body'>\n\n"
        return "".join(self._expand_any_termdef(macrocall)) + open_body

    def _expand_endterm(self, macrocall: macros.Macrocall) -> str:
        """[ENDTERM]  (a [TERM] has to be open)"""
        close_body = "\n\n</div>\n"
        if self.term_linkslist is not None:
            result = self.term_linkslist
            self.term_linkslist = None
            return close_body + "".join(result)
        else:
            b.error(f"'{macrocall.filename}': [ENDTERM] is lacking its [TERM::...]")
            return ""

    @staticmethod
    def _collect_parts(termrefdict: dict[str, set[str]], termslist: list[str]) -> set[str]:
        """
        termslist is the list of aliases of a term.
        termrefdict maps a term (main or alias) to a set of parts refering to it.
        Returns the set of parts refering to one of the terms in termslist: The union
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
        file, part = macrocall.filename, macrocall.partname
        terms = macrocall.arg1
        termslist = terms.split(separator)
        headingtext = " | ".join(termslist)  # we keep the original order
        result = []
        # ----- report duplicate entries:
        for term in termslist:
            if term in self.termdefs:
                b.error(f"{macrocall.macrocall_text}: Term '{term}' is already defined")
            self.termdefs.add(term)
        # ----- open block:
        result.extend("\n<div class='glossary-term-block'>\n")
        # ----- generate anchors:
        anchors = ("<a id='%s'></a>\n" % b.slugify(term) for term in termslist)
        result.extend(anchors)
        # ----- generate heading:
        result.append(f"<span class='glossary-term-heading'>{headingtext}</span>\n")
        # ----- generate links:
        links = []
        explainedby_names = self._collect_parts(self.explainedby, termslist)
        mentionedby_names = self._collect_parts(self.mentionedby, termslist)
        explainedby_links = sorted((f"[PARTREF::{part}]" for part in explainedby_names))
        mentionedby_links = sorted((f"[PARTREF::{part}]" for part in mentionedby_names))
        any_links = explainedby_links or mentionedby_links
        if any_links:
            links.append("\n<div class='glossary-term-linkblock'>\n")
        if explainedby_links:
            links.append(" <div class='glossary-term-links-explainedby'>\n   ")
            links.append(macros.expand_macros(file, part,  ", ".join(explainedby_links)))
            links.append("\n </div>\n")
        if mentionedby_links:
            links.append(" <div class='glossary-term-links-mentionedby'>\n")
            links.append("  " + macros.expand_macros(file, part, ", ".join(mentionedby_links)))
            links.append("\n </div>\n")
        if any_links:
            links.append("</div>\n")
        # ----- close block:
        result.extend("\n</div>\n")
        if self.term_linkslist is not None:
            b.error("'%s': %s is preceeded by a [TERM] with no [ENDTERM]" %
                    (macrocall.filename, macrocall.macrocall_text))
        self.term_linkslist = links
        # ----- done!:
        return result

    def _mentions(self, partname: str, term: str):  # called by phase 1 TERMREF macro expansion
        if partname and partname != "glossary": #avoid links from glossary to itself
            if term not in self.mentionedby:
                self.mentionedby[term] = set()
            self.mentionedby[term].add(partname)
