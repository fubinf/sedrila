"""sedrila-specific HTML generation helper routines."""
import typing as tg

DIFFICULTY_SIGN = "&#x29f3;"  # &#x26ab; is always black, &#x23f9; and &#x23fa; are wrong blue symbols on Chrome and Edge
# https://commons.wikimedia.org/wiki/Unicode_circle_shaped_symbols

def as_attribute(text: str) -> str:
    """Cleans text so that it can appear between double quotes in an HTML attribute."""
    return text.replace('"', "'").replace("\n", " ")  # no doublequotes, no line breaks


def breadcrumb(*args):
    """Renders breadcrumb HTML fragment from list of items with breadcrumb_item property."""
    SEPARATOR = " > "
    return "<div>%s</div>" % SEPARATOR.join([arg.breadcrumb_item for arg in args])


def indented_block(text: str, level: tg.Optional[int]) -> str:
    return "".join([
        level * " " if level is not None else "",
        f"<div class='indent{min(level,4)}'>" if level is not None else "<span>",
        text,
        "</div>" if level is not None else "</span>"])

