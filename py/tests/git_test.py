import git

def test_get_commits():
    # uses fixed knowledge about our own very repo
    commits = git.get_commits()
    first = commits[-1]  # git output is '6492d05\tprechelt@inf.fu-berlin.de\t1663692720\t\tInitial commit'
    second = commits[-2]  # git output is '8cb7d47\tmyname@mynery.eu\t1664980577\t\tSplit of tooling and content'
    assert first.hash == "6492d05"  # hash may become longer some day  
    assert first.author_email == "prechelt@inf.fu-berlin.de"   
    assert first.author_date.hour == 16    
    assert first.subject == "Initial commit"
    assert second.author_email == "myname@mynery.eu"


def test_get_file_version():
    # uses fixed knowledge about our own very repo
    output = git.get_file_version("423d101a73", "py/sdrl/student.py", encoding='utf8')
    assert output == '"""sedrila-specific parts (Ö)"""\n'
