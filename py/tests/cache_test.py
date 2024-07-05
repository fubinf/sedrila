import os
import tempfile

import pytest

import cache
import testbase

def test_sedrilacache():
    with tempfile.TemporaryDirectory() as tmpdir:
        c = cache.SedrilaCache(tmpdir)
        S = cache.State
        mystr = "value s"
        mylist = ["a", "b"]
        mydict = dict(a="value a", b=1)
        f_new = os.path.join(tmpdir, "f_new")
        f_old = os.path.join(tmpdir, "f_old")
        # ----- Phase 1: Read from empty cache
        assert c.cached_str("s") == (None, S.MISSING)
        assert c.cached_list("l") == (None, S.MISSING)
        assert c.cached_dict("d") == (None, S.MISSING)
        assert c.filestate("f") == S.MISSING
        # ----- Phase 2: Write
        c.write_str("s", mystr)
        c.write_list("l", mylist)
        c.write_dict("d", mydict)
        make_and_record_file(c, f_new)
        make_and_record_file(c, f_old)
        # ----- Phase 3: Read existing and nonexisting
        assert c.cached_str("s") == (mystr, S.HAS_CHANGED)
        assert c.cached_list("l") == (mylist, S.HAS_CHANGED)
        assert c.cached_dict("d") == (mydict, S.HAS_CHANGED)
        assert c.filestate(f_new) == S.HAS_CHANGED
        assert c.cached_str("non-s") == (None, S.MISSING)
        # ----- Phase 4: commit() and start afresh
        c.close()
        c = cache.SedrilaCache(tmpdir)  # simulate a next run of sedrila
        os.utime(f_old, (c.mtime, c.mtime-5))  # make f_old old
        c.timestamp_cached -= 1  # kludge! make f_new look new
        # ----- Phase 5: Read existing
        assert c.cached_str("s") == (mystr, S.AS_BEFORE)
        assert c.cached_list("l") == (mylist, S.AS_BEFORE)
        assert c.cached_dict("d") == (mydict, S.AS_BEFORE)
        assert c.filestate(f_old) == S.AS_BEFORE
        assert c.filestate(f_new) == S.HAS_CHANGED
        # ----- Phase 6: Overwrite
        c.write_str("s", "-")
        c.record_file(f_old)
        c.record_file(f_new)
        # ----- Phase 7: Read old and new
        assert c.cached_str("s") == ("-", S.HAS_CHANGED)
        assert c.cached_list("l") == (mylist, S.AS_BEFORE)
        assert c.cached_dict("d") == (mydict, S.AS_BEFORE)
        # assert c.filestate(f_old) == S.HAS_CHANGED  TODO 1
        # assert c.filestate(f_new) == S.HAS_CHANGED


def make_and_record_file(c, filename):
    with open(filename, mode='w'):
        pass  # just create the file
    c.record_file(filename)
        
        