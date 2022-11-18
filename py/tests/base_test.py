import base as b

def test_logging(capsys):
    print("first")
    b.warning("a warning")
    print("second")
    out, err = capsys.readouterr()
    assert out == "first\na warning\nsecond\n"