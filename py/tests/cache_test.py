import os
import tempfile

import pytest

import cache
import sdrl.constants as c


def ck(fn: str) -> str:  # pseudo-cache_key function
    return f"{fn}__"


def test_sedrilacache():
    with tempfile.TemporaryDirectory() as tmpdir:
        ca = cache.SedrilaCache(os.path.join(tmpdir, c.CACHE_FILENAME), start_clean=False)  # cache is empty anyway
        S = cache.State
        mystr = "value s"
        mylist = ["a", "b"]
        mydict = dict(a="value a", b=1)
        f_new = os.path.join(tmpdir, "f_new")
        f_old = os.path.join(tmpdir, "f_old")
        # ----- Phase 1: Read from empty cache
        assert ca.cached_str("s") == (None, S.MISSING)
        assert ca.cached_list("l") == ([], S.MISSING)
        assert ca.cached_dict("d") == (dict(), S.MISSING)
        assert ca.filestate("f", ck("f")) == S.MISSING
        # ----- Phase 2: Write
        ca.write_str("s", mystr)
        ca.write_list("l", mylist)
        ca.write_dict("d", mydict)
        make_and_record_file(ca, f_new)
        make_and_record_file(ca, f_old)
        # ----- Phase 3: Read existing and nonexisting
        assert ca.cached_str("s") == (mystr, S.HAS_CHANGED)
        assert ca.cached_list("l") == (mylist, S.HAS_CHANGED)
        assert ca.cached_dict("d") == (mydict, S.HAS_CHANGED)
        assert ca.filestate(f_new, ck(f_new)) == S.HAS_CHANGED
        assert ca.cached_str("non-s") == (None, S.MISSING)
        # ----- Phase 4: commit() and start afresh
        ca.close()
        ca = cache.SedrilaCache(os.path.join(tmpdir, c.CACHE_FILENAME), 
                                start_clean=False)  # simulate a next run of sedrila
        os.utime(f_old, (ca.mtime, ca.mtime-5))  # make f_old old
        ca.timestamp_cached -= 1  # kludge! make f_new look new
        # ----- Phase 5: Read existing
        assert ca.cached_str("s") == (mystr, S.AS_BEFORE)
        assert ca.cached_list("l") == (mylist, S.AS_BEFORE)
        assert ca.cached_dict("d") == (mydict, S.AS_BEFORE)
        assert ca.filestate(f_old, ck(f_old)) == S.AS_BEFORE
        assert ca.filestate(f_new, ck(f_new)) == S.HAS_CHANGED
        # ----- Phase 6: Overwrite
        ca.write_str("s", "-")
        ca.record_file(f_old, ck(f_old))
        ca.record_file(f_new, ck(f_new))
        # ----- Phase 7: Read old and new
        assert ca.cached_str("s") == ("-", S.HAS_CHANGED)
        assert ca.cached_list("l") == (mylist, S.AS_BEFORE)
        assert ca.cached_dict("d") == (mydict, S.AS_BEFORE)
        # assert ca.filestate(f_old, ck(f_old)) == S.HAS_CHANGED  TODO 1
        # assert ca.filestate(f_new, ck(f_new)) == S.HAS_CHANGED


def make_and_record_file(ca, filename):
    with open(filename, mode='w'):
        pass  # just create the file
    ca.record_file(filename, ck(filename))
        
        
