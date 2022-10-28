"""Shortcut typenames, global constants, basic helpers."""
import typing as tg

CONFIG_FILENAME = "sedrila.yaml"  # plain filename, no directory possible
TEMPLATES_DIR = "templates"

OStr = tg.Optional[str]
StrMap = tg.Mapping[str, str]
StrAnyMap = tg.Mapping[str, tg.Any]  # JSON or YAML structures


def slurp(filename: str) -> str:
    with open(filename, 'rt', encoding='utf8') as f:
        return f.read()


def spit(filename: str, content: str):
    with open(filename, 'wt', encoding='utf8') as f:
        f.write(content)
