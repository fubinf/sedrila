# sedrila
Tool infrastructure for building and running "self-driven lab" courses

#Overview

This will map markdown files present in `content` to html files in the target directory `out` in the same directory structure.
Files that are not markdown files will be copied over.

Be aware that starting files with hyperlinks will confuse the meta data plugin.

Costum made commands:

* `!toc` will create a table of contents up to a depth of 2. It reads the `title` meta data

   You can provide an additional argument to define the target attribute for the generated links.
   If the provided target is #, the links will instead link to anchors.

* `!subtoc` will do that, but only display the part of the table of contents related to this pat

   This will not include items of a depth that are not included in the main table of content.

* `!inline file` will inline the contents of another file.

   This will _not_ create an html file for that file and it will only work in sub-directories

* `!resources` is just a shortcut for `!inline resources.md`

   Ideally, there will be some option to reference links provided in there in some way

* `!overview folder` inlines folder/overview.md and the title links to folder/index.html

   A `target` meta data in the overview file can override the link target.

* `!tasks` will inline all other files in the same folder

Each inline will be wrapped in its own div, containing a class named after their respective command.

In addition, an optional `src/header.html` and `src/footer.html` will be prepended/appended to each produced html file.

You can define alternative header and footer files on a per file basis via the `header` and `footer` meta data. Please note that this will override both, even if only one of them is provided,

# Usage

Running main.py will produce the target directory if missing.

If called with the optional argument `clean`, it will remove that directory beforehand.

If called with the optional argument `test`, it will instead run some unit tests
