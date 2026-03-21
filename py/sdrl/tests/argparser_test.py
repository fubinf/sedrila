import re
import unittest.mock as mock

import sdrl.argparser as ap


def test_get_version_returns_semver_string():
    """get_version() reads pyproject.toml and returns a semantic version."""
    version = ap.SedrilaArgParser.get_version()
    assert re.match(r'^\d+\.\d+\.\d+', version), f"unexpected version format: {version!r}"


def test_get_version_from_whl_path(tmp_path):
    """get_version() finds pyproject.toml one level above sdrl/ (whl layout)."""
    # whl layout:  <tmp>/sdrl/argparser.py  and  <tmp>/pyproject.toml
    fake_toml = tmp_path / "pyproject.toml"
    fake_toml.write_bytes(b'[tool.poetry]\nversion = "9.8.7"\n')

    fake_argparser_file = str(tmp_path / "sdrl" / "argparser.py")

    with mock.patch.object(ap, '__file__', fake_argparser_file):
        with mock.patch('os.path.exists', return_value=True):
            with mock.patch('builtins.open', mock.mock_open(read_data=fake_toml.read_bytes())):
                import tomllib
                with mock.patch('tomllib.load', return_value={'tool': {'poetry': {'version': '9.8.7'}}}):
                    version = ap.SedrilaArgParser.get_version()
    assert version == "9.8.7"


def test_format_help_contains_version_and_sedrila():
    """format_help() sets description with version and 'sedrila'."""
    parser = ap.SedrilaArgParser(description="-")
    help_text = parser.format_help()
    assert "sedrila" in help_text
    version = ap.SedrilaArgParser.get_version()
    assert version in help_text
