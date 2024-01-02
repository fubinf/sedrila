# pytest tests

import base as b
import sdrl.markdown as md

    
def test_perhaps_suppress_instructorinfo():
    md.md.mode = b.Mode.STUDENT  # turns on the suppression
    content = "one [SECTION::forinstructor::x] two [ENDSECTION] three"
    assert md.SedrilaPreprocessor(md.md).perhaps_suppress_instructorinfo(content) == "one  three"