"""sedrila-specific HTML generation helper routines."""
import typing as tg

DIFFICULTY_SIGN = "&#x26ab;&#xfe0e;"  # &#x26ab; is an icon and always black, &#xfe0e; is the text-variant selector
# https://commons.wikimedia.org/wiki/Unicode_circle_shaped_symbols

def as_attribute(text: str) -> str:
    """Cleans text so that it can appear between double quotes in an HTML attribute."""
    return text.replace('"', "'").replace("\n", " ")  # no doublequotes, no line breaks


def breadcrumb(*args):
    """Renders breadcrumb HTML fragment from list of items with breadcrumb_item property."""
    SEPARATOR = " > "
    return "<div>%s</div>" % SEPARATOR.join([arg.breadcrumb_item for arg in args])


def difficulty_symbol(level: int) -> str:
    diffclass = f"class='difficulty{level}'"
    circle = f"<span {diffclass} title='Difficulty: {difficulty_symbol}'>{DIFFICULTY_SIGN}</span>"
    return circle


def indented_block(text: str, level: tg.Optional[int]) -> str:
    return "".join([
        level * " " if level is not None else "",
        f"<div class='indent{min(level,4)}'>" if level is not None else "<span>",
        text,
        "</div>" if level is not None else "</span>"])

