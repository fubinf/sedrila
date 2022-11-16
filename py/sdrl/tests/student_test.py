import sdrl.student

def test_parse_taskname_workhours():
    func = sdrl.student.parse_taskname_workhours
    assert func("mystuff 1h remaining msg") == ("mystuff", 1.0)
    assert func("mystuff 1h") == ("mystuff", 1.0)
    assert func("mystuff 1 h") == ("mystuff", 1.0)
    assert func("mystuff 1.0h") == ("mystuff", 1.0)
    assert func("mystuff 1:00h") == ("mystuff", 1.0)
    assert func("my-stuff 1h") == None
    assert func("SomeTask4711 0:01h 1001 nights message") == ("SomeTask4711", 1.0/60)
    assert func("a 11.5h   ") == ("a", 11.50)
    assert func("a 1111:45h") == ("a", 1111.750)
