import markdown
import xml.etree.ElementTree as etree
import re
import os
import shutil

class Blocks(markdown.blockprocessors.BlockProcessor):
    RE_PARSE_TITLE = r'^(\S+|"[^"]+")\s*(.*)$'
    commands = ["overview", "inline", "resources", "tasks", "toc", "subtoc"]

    def __init__(self, outer, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.outer = outer

    def test(self, parent, block):
        return any(block.startswith("!" + command) for command in self.commands)

    def build_toc(self, parent, toc, subpath, key = None):
        if "file" in toc and toc["file"] and key:
            li = etree.SubElement(parent, "li")
            title = toc["title"]
            if not title:
                title = key
            if not title:
                title = os.path.basename(os.path.dirname(toc["file"]))
            a = etree.SubElement(li, "a")
            href = self.outer.out_name(True, toc["file"])
            if href.startswith(subpath):
                href = href[len(subpath):]
            a.set("href", href)
            if self.target:
                a.set("target", self.target)
            a.text = title
            if "entries" in toc and toc["entries"]:
                parent = etree.SubElement(li, "ol")
        if "entries" in toc and toc["entries"]:
            for key, entry in toc["entries"].items():
                self.build_toc(parent, entry, subpath, key)

    def run(self, parent, blocks):
        block = blocks.pop(0)
        if self.outer.first_pass:
            self.outer.second_pass.add(self.outer.full_name)
        if block.startswith("!toc") or block.startswith("!subtoc"):
            self.target = None
            if " " in block:
                self.target = block.split(" ", 1)[1]
            ol = etree.SubElement(parent, "ol")
            ol.set("class", "toc")
            toc = self.outer.toc
            subpath = ""
            if block.startswith("!subtoc") and not self.outer.first_pass:
                for part in self.outer.root.split(os.sep)[1:]:
                    toc = toc["entries"][part]
                prefix = ""
                root = self.outer.root
                while root.startswith("../"):
                    root = root[3:]
                if os.sep in root:
                    subpath = root.split(os.sep, 1)[1] + "/"
                else:
                    subpath = root + "/"
            self.build_toc(ol, toc, subpath)
            return
        lines = block.splitlines()
        for line in lines:
            match = None
            if line == "!resources":
                filename = os.path.join(self.outer.root, "resources.md")
            elif line == "!tasks":
                filename = [os.path.join(self.outer.root, file) for file in self.outer.files if file != self.outer.file]
                self.outer.redodirectory = not(self.outer.redoing)
            else:
                line = line.split(" ", 1)[1]
                filename = os.path.join(self.outer.root, line)
                if not filename.endswith(".md"):
                    match = re.match(self.RE_PARSE_TITLE, line)
                    if match:
                        filename = os.path.join(self.outer.root, match.group(1), "overview.md")
            if not isinstance(filename, list):
                filename = [filename]
            if self.outer.first_pass:
                for name in filename:
                    if name not in self.outer.inlines:
                        print("need inlining for {}".format(name))
                        self.outer.inlines[name] = None
                continue
            if match:
                title = match.group(2)
                if not title:
                    title = match.group(1)
                div = etree.SubElement(parent, "div")
                div.set("class", "overview")
                a = etree.SubElement(div, "a")
                a.set("href", match.group(1) + "/index.html")
                a.text = title
                parent = div
            for name in filename:
                if name not in self.outer.inlines:
                    print("expected inline not found for {}".format(name))
                    continue
                if self.outer.inlines[name]:
                    self.parser.parseBlocks(parent, self.outer.inlines[name])

class Surrounding(markdown.postprocessors.Postprocessor):
    def __init__(self, outer,  *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.outer, self.header, self.footer = outer, "", ""
        if os.path.isfile("src/header.html"):
            with open("src/header.html", "r", encoding="utf8") as f:
                self.header = f.read()
        if os.path.isfile("src/footer.html"):
            with open("src/footer.html", "r", encoding="utf8") as f:
                self.footer = f.read()

    def run(self, text):
        header, footer = self.header, self.footer
        customheader = self.outer.metadata("header")
        customfooter = self.outer.metadata("footer")
        if customheader or customfooter:
            header, footer = "", "" #we expectesurroundings, so better reset both!
            if os.path.isfile(os.path.join(self.outer.content_dir, customheader)):
                with open(os.path.join(self.outer.content_dir, customheader), "r", encoding="utf8") as f:
                    header = f.read()
            if os.path.isfile(os.path.join(self.outer.content_dir, customfooter)):
                with open(os.path.join(self.outer.content_dir, customfooter), "r", encoding="utf8") as f:
                    footer = f.read()
        return header + text + footer

class Markdown():
    def __init__(self, content_dir, out_dir, toc_depth, **kwargs):
        super().__init__(**kwargs)
        self.first_pass, self.second_pass, self.inlines = True, set(), {}
        self.toc, self.meta = self.toc_entry(), {}
        self.content_dir, self.out_dir, self.toc_depth = content_dir, out_dir, toc_depth
        self.md = markdown.Markdown(extensions = ["admonition", "sane_lists", "smarty", "extra", "meta", "md_in_html"])
        #maybe interesting: progress bar for automatic footer, mermaid
        self.md.parser.blockprocessors.register(Blocks(self, self.md.parser), "proprablocks", 100)
        self.md.postprocessors.register(Surrounding(self, self.md), "proprasurroundings", 100)

    def metadata(self, key):
        if key in self.md.Meta:
            return self.md.Meta[key][0]
        return None

    def toc_entry(self):
        return {"entries": {}, "file": None, "title": None}

    def out_name(self, change_extension = True, full_name = None):
        prefix = ""
        if not full_name:
            full_name = self.full_name
            prefix = self.out_dir
        if change_extension:
            out_name = prefix + full_name[len(self.content_dir):-2] + "html"
        else:
            out_name = prefix + full_name[len(self.content_dir):]
        if not prefix:
            out_name = out_name.lstrip("/")
        else:
            os.makedirs(os.path.dirname(out_name), exist_ok=True)
        return out_name

    def add_inline(self):
        if not os.path.isfile(self.full_name):
            exit("tried to add non-existent inline {}".format(self.full_name))
        with open(self.full_name, "r", encoding="utf8") as f:
            if self.full_name.endswith("/resources.md"):
                self.inlines[self.full_name] = f.readlines()
            else:
                self.inlines[self.full_name] = re.split(r"(?:\r?\n){2,}", f.read())
        #remove meta data
        if re.match(r'^\S+:\s+', self.inlines[self.full_name][0]):
            self.inlines[self.full_name].pop(0)

    def process(self, root, subdirs, files, redoing = False):
        self.root, self.subdirs, self.files = root, subdirs, files
        self.redodirectory, self.redoing = False, redoing
        if "resources.md" in self.files: #put resources to the end to fix inlining
            self.files.remove("resources.md")
            self.files.append("resources.md")
        for file in self.files:
            self.file, self.full_name = file, os.path.join(root, file)
            depth = root.count(os.sep)
            if file.endswith(".md"):
                if self.full_name in self.inlines:
                    print("add as inline {}".format(self.full_name))
                    self.add_inline()
                    continue
                print("processing {}".format(self.full_name))
                self.md.reset().convertFile(input=self.full_name, output=self.out_name())
                self.meta = self.md.Meta
            else:
                shutil.copy(self.full_name, self.out_name(False))
            if depth <= self.toc_depth and file == "index.md":
                parts = root.split(os.sep)
                toc = self.toc
                for part in parts[1:]:
                    toc = toc["entries"].setdefault(part, self.toc_entry())
                toc["file"] = self.full_name
                if "title" in self.meta:
                    toc["title"] = self.meta["title"][0]
            if self.redodirectory and not redoing:
                print("redoing directory")
                self.process(root, subdirs, files, True)
                break

    def finish(self):
        self.first_pass = False
        for full_name in self.second_pass:
            self.root = os.path.dirname(full_name)
            print("second pass for {}".format(full_name))
            self.full_name = full_name
            self.md.reset().convertFile(input=full_name, output=self.out_name())
