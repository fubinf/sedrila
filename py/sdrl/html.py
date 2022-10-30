"""sedrila-specific HTML generation helper routines."""
import typing as tg


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

