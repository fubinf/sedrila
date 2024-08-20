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
        # the development tree (and tar version of the package) have this structure:
        #   pyproject.toml
        #   py/sdrl/argparser.py
        # in contrast, the whl version of the package has this structure:
        #   pyproject.toml
        #   sdrl/argparser.py
        # our logic needs to work for both.  We try the whl version first:
        topdir = os.path.dirname(os.path.dirname(__file__))
        pyprojectfile = os.path.join(topdir, "pyproject.toml")
        if not os.path.exists(pyprojectfile):  # we have the tar or development tree here:
            topdir = os.path.dirname(topdir)  # go from py to top in dev tree
            pyprojectfile = os.path.join(topdir, "pyproject.toml")  # this ought to work now
        with open(pyprojectfile, 'rb') as f:
            toml = tomllib.load(f)
            return toml['tool']['poetry']['version']


