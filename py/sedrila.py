#!/usr/bin/env python3
import argparse_subcommand as ap_sub
import os
import sys

import base as b
import sdrl.subcmd  # this is where the subcommands will be found


class SedrilaArgParser(ap_sub.ArgumentParser):
    """One-trick pony class for obtaining the expensive description only when needed."""
    def format_help(self):
        self.description = f"sedrila {self.get_version()}: Tool for 'self-driven lab' (SeDriLa) university courses."
        return super().format_help()
    
    @staticmethod
    def get_version() -> str:
        import tomllib
        topdir = os.path.dirname(os.path.dirname(__file__))
        pyprojectfile = os.path.join(topdir, "pyproject.toml")
        with open(pyprojectfile, 'rb') as f:
            toml = tomllib.load(f)
            return toml['tool']['poetry']['version']


def main():  # uses sys.argv
    """Calls subcommand given on command line"""
    parser = SedrilaArgParser(description="-")  # description is set lazily
    parser.scan("sdrl.subcmd.*")
    if os.environ.get(b.SEDRILA_COMMAND_ENV) and len(sys.argv) < 2:
        print(f"Using existing environment var {b.SEDRILA_COMMAND_ENV}")
        args = parser.parse_args(os.environ.get(b.SEDRILA_COMMAND_ENV).split(" "))
    else:
        args = parser.parse_args()
    parser.execute_subcommand(args)


if __name__ == "__main__":
    mode = 'normal'  # profile, pdb, normal
    if mode == 'profile':
        import cProfile
        cProfile.run('main()', sort='cumulative')
    elif mode == 'pdb':
        try:
            main()
        except Exception as ex:
            import pdb
            print(str(ex))
            pdb.post_mortem()
    else:
        main()  # normal life