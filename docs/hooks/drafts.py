"""
MkDocs hook: keep the pages marked as drafts out of the published site.

A page with ``draft: true`` in its front matter is a draft: ``mkdocs serve`` shows it,
marked as such, and ``mkdocs build``, which publishes the site, leaves it out, with its
entries in the navigation and in the previous and next links. A line of a published page
that links to a draft is left out too, so that no link breaks: write such mentions on
lines of their own, such as a table row or a sentence. Use it for a study whose page is
not ready to be public.
"""
import posixpath
import re
from typing import Any

from mkdocs.structure.files import Files, InclusionLevel
from mkdocs.utils.meta import get_data

_LINK = re.compile(r"\]\(([^)\s#]+)")
# Whether the site is served, with its drafts, rather than built to be published.
_STATE = {"serving": False}


def on_startup(command: str, **_: Any) -> None:
    """Remember whether the site is served or published."""
    _STATE["serving"] = command == "serve"


def on_files(files: Files, **_: Any) -> Files:
    """Mark as drafts the pages whose front matter says ``draft: true``."""
    for file in files.documentation_pages():
        _, meta = get_data(file.content_string)
        if meta.get("draft") is True:
            file.inclusion = InclusionLevel.DRAFT
    return files


def on_page_markdown(markdown: str, page: Any, files: Files, **_: Any) -> str:
    """When publishing, leave out the lines of a page that link to a draft."""
    if _STATE["serving"]:
        return markdown
    folder = posixpath.dirname(page.file.src_uri)

    def links_a_draft(line: str) -> bool:
        for target in _LINK.findall(line):
            linked = files.get_file_from_path(posixpath.normpath(posixpath.join(folder, target)))
            if linked is not None and linked.inclusion == InclusionLevel.DRAFT:
                return True
        return False

    return "".join(line for line in markdown.splitlines(keepends=True) if not links_a_draft(line))


def _is_draft(item: Any) -> bool:
    file = getattr(item, "file", None)
    return file is not None and file.inclusion == InclusionLevel.DRAFT


def _without_drafts(items: list) -> list:
    """The items of a navigation without the drafts, and without the sections left empty."""
    kept = []
    for item in items:
        if getattr(item, "children", None):
            item.children = _without_drafts(item.children)
            if item.children:
                kept.append(item)
        elif not _is_draft(item):
            kept.append(item)
    return kept


def on_nav(nav: Any, **_: Any) -> Any:
    """When publishing, leave the drafts out of the navigation and of previous and next."""
    if _STATE["serving"]:
        return nav
    nav.items = _without_drafts(nav.items)
    nav.pages = [page for page in nav.pages if not _is_draft(page)]
    bookended = [None, *nav.pages, None]
    for before, page, after in zip(bookended, bookended[1:], bookended[2:]):
        page.previous_page, page.next_page = before, after
    return nav
