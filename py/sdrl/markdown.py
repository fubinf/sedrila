"""Markdown rendering with sedrila-specific bells and/or whistles."""

import markdown

def render_markdown(markdown_markup: str) -> str:
    """Generates HTML from Markdown in sedrila manner."""
    return markdown.markdown(markdown_markup)