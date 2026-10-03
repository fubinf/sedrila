import os

import argparse_subcommand as ap_sub


class SedrilaArgParser(ap_sub.ArgumentParser):
    """One-trick pony class for obtaining the expensive description only when needed."""

    def format_help(self):
        self.description = f"sedrila {self.get_version()}: Tool for 'self-driven lab' (SeDriLa) university courses."
        return super().format_help()

    @staticmethod
    def get_version() -> str:
        import tomllib
        # In the development tree (and the tar version of the package), pyproject.toml is one level
        # above the sedrila package.  The whl version does not contain it, but has package metadata.
        topdir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        pyprojectfile = os.path.join(topdir, "pyproject.toml")
        if os.path.exists(pyprojectfile):
            with open(pyprojectfile, 'rb') as f:
                toml = tomllib.load(f)
                return toml['project']['version']
        import importlib.metadata
        return importlib.metadata.version("sedrila")


