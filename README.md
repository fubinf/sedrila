# sedrila
Tool infrastructure for building and running "self-driven lab" courses

#Overview

This will map markdown files present in `content` to html files in the target directory `out` in the same directory structure.
Files that are not markdown files will be copied over.

Be aware that starting files with hyperlinks will confuse the meta data plugin.

Costum made commands:

* `!toc` will create a table of contents up to a depth of 2. It reads the `title` meta data
* `!subtoc` will do that, but only display the part of the table of contents related to this pat

   This will not include items of a depth that are not included in the main table of content.

* `!inline file` will inline the contents of another file.

   This will _not_ create an html file for that file and it will only work in sub-directories

* `!resources` is just a shortcut for `!inline resources.md`

   Ideally, there will be some option to reference links provided in there in some way

* `!overview folder title` inlines folder/

In addition, an optional `src/header.html` and `src/footer.html` will be prepended/appended to each produced html file.

# Usage

Running main.py will produce the target directory if missing.
If called with the optional argument `clean`, it will remove that directory beforehand.
