"""sedrila-specific HTML generation helper routines."""
import sdrl.constants as c


difficulty_levels = ('verylow', 'low', 'medium', 'high')

def as_attribute(text: str) -> str:
    """Cleans text so that it can appear between double quotes in an HTML attribute."""
    return text.replace('"', "'").replace("\n", " ")  # no doublequotes, no line breaks


def breadcrumb(*args):
    """Renders breadcrumb HTML fragment from list of items with breadcrumb_item property."""
    SEPARATOR = " &gt; "
    return '<nav><span class="breadcrumbs">%s</span></nav>' % SEPARATOR.join([arg.breadcrumb_item for arg in args])


def difficulty_symbol(level: int) -> str:
    difficulty_text = difficulty_levels[level - 1]
    diffclass = f"class='difficulty{level}'"
    circle = f"<span {diffclass} title='Difficulty: {difficulty_text}'>{c.HTML_DIFFICULTY_SIGN}</span>"
    return circle


def indented_block(text: str, level: int, classes: str) -> str:
    return "".join([(level+1) * "  ", f"<div class='indent{level} {classes}'>", text, "</div>"])

