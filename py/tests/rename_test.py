import sdrl.rename 


def test_replace_requires_assumes():
    def r_ra(line):
        return sdrl.rename._replace_requires_assumes(line, "ol-d", "new")

    # ----- matches:
    assert r_ra("assumes: ol-d") == "assumes: new"
    assert r_ra("requires: a,  ol-d,b") == "requires: a,  new,b"
    assert r_ra("requires:ol-d") == "requires:new"

    # ----- non-matches:
    assert r_ra(" assumes: ol-d") == " assumes: ol-d"
    assert r_ra("assumes ol-d") == "assumes ol-d"
    assert r_ra("assumes: aol-d") == "assumes: aol-d"
    assert r_ra("assumes: ol-d-e") == "assumes: ol-d-e"

    
def test_replace_macros():
    def r_m(line):
        return sdrl.rename._replace_macros(line, "ol-d", "new")

    # ----- matches:
    assert r_m("a [PARTREF::ol-d] b") == "a [PARTREF::new] b"
    assert r_m("a[PARTREFMANUAL::ol-d::manualstuff]b") == "a[PARTREFMANUAL::new::manualstuff]b"
    assert r_m("[INCLUDE::ol-d]") == "[INCLUDE::new]"
    assert r_m("[INCLUDE::/a/b/ol-d/c]") == "[INCLUDE::/a/b/new/c]"
    assert r_m("[INCLUDE::ol-d/c]") == "[INCLUDE::new/c]"
    assert r_m("[INCLUDE::/a/b/ol-d]") == "[INCLUDE::/a/b/new]"
    assert r_m("[INCLUDE::ALT:/a/b/ol-d/c]") == "[INCLUDE::ALT:/a/b/new/c]"
    assert r_m("[INCLUDE::ALT:ol-d/c]") == "[INCLUDE::ALT:new/c]"
    assert r_m("[INCLUDE::ALT:/a/b/ol-d]") == "[INCLUDE::ALT:/a/b/new]"
    assert r_m("[TREEREF::ol-d/c]") == "[TREEREF::new/c]"
    assert r_m("[PROT::ALT:/a/b/ol-d]") == "[PROT::ALT:/a/b/new]"
    # ----- non-matches:
    assert r_m("[INCLUDE::ol-de]") == "[INCLUDE::ol-de]"
    assert r_m("[INCLUDE::a-ol-d]") == "[INCLUDE::a-ol-d]"


def test_rewrite_prot():
    def r_p(line):
        return sdrl.rename._replace_protline(line, "ol-d", "new")

    # ----- matches:
    assert r_p("ol-d") == "new"
    assert r_p("user@host ~/abc/ol-d ") == "user@host ~/abc/new "
    assert r_p("user@host ~/abc/ol-d/def") == "user@host ~/abc/new/def"
    assert r_p("python ol-d.py") == "python new.py"
    # ----- non-matches:
    assert r_p("ol-d-e") == "ol-d-e"
    assert r_p("a-ol-d") == "a-ol-d"

