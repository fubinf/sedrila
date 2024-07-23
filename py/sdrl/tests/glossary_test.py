# pytest tests

import base as b
import sdrl.markdown as md
import sdrl.glossary
import sdrl.macros as macros

import tests.testbase as tb

expected_ref_myterm = """
<div class='glossary-term-block'>
<a id='myterm'></a>
<span class='glossary-term-heading'>myterm</span>

</div>

<div class='glossary-term-linkblock'>
 <div class='glossary-term-links-explainedby'>
   ExplainingPart
 </div>
 <div class='glossary-term-links-mentionedby'>
  mypart2, mypart
 </div>
</div>
"""


expected_output = """File 'src2':
   [TERM0::impossibleterm]': [TERM0] can only be used in the glossary
File 'glossary.md':
   [TERM0::myterm]: Term 'myterm' is already defined
File 'py/sdrl/tests/data/glossary.md':
   This term lacks a definition: ['mynoterm']
"""


def test_glossary(capsys):
    # ----- prepare dummy glossary:
    b._testmode_reset()
    macros._testmode_reset()
    macros.register_macro('PARTREF', 1, macros.MM.INNER, lambda mc: mc.arg1)  # render plain partname
    glossary = sdrl.glossary.Glossary('glossary', chapterdir="py/sdrl/tests/data",  # contains a title-only glossary.md
                                      directory=tb.get_directory())
    md.render_markdown("", "", "", b.Mode.STUDENT, dict())  # must initialize md
    # ----- add term references:
    glossary.explains("ExplainingPart", "myterm")
    ref_myterm = macros.expand_macros("src",  "mypart", "[TERMREF::myterm]") 
    ref_myterm2 = macros.expand_macros("src2",  "mypart2", "[TERMREF2::myterm::-s]") 
    ref_myterm2b = macros.expand_macros("src",  "mypart", "[TERMREF2::myterm::mytrm2]") 
    ref_mynoterm = macros.expand_macros("src",  "mypart", "[TERMREF::mynoterm]")  # undefined term
    # ----- add term definitions:
    premature_def = macros.expand_macros("src2",  "glossary", "[TERM0::impossibleterm]")  # --> error msg
    glossary_html = glossary.render(b.Mode.STUDENT)
    def_myterm_a = macros.expand_macros("glossary.md",  "glossary", "[TERM0::myterm]") 
    def_myterm_b = macros.expand_macros("glossary.md",  "glossary", "[TERM0::myterm]")
    # ----- check for undefined terms:
    glossary.report_issues()
    # ----- prepare checking:
    out, err = capsys.readouterr()
    print(out)  # print captured output so we can see it, too
    # ----- check term references:
    assert ref_myterm == "<a href='glossary.html#myterm' class='glossary-termref-term'>myterm<span class='glossary-termref-suffix'></span></a>"
    assert ">myterms<" in ref_myterm2
    assert ">mytrm2<" in ref_myterm2b
    assert ">mynoterm<" in ref_mynoterm  # renders just like an existing one
    # ----- check term definitions:
    print(def_myterm_a)
    assert def_myterm_a == expected_ref_myterm
    # ----- check error output:
    assert out == expected_output