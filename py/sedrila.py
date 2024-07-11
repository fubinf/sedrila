#!/usr/bin/env python3

import argparse_subcommand as ap_sub
import os
import sys

import base as b
import sdrl.subcmd  # this is where the subcommands will be found

description = f"sedrila {b.SEDRILA_VERSION}: Tool for 'self-driven lab' (SeDriLa) university courses."

moduletype = type(sdrl)
functiontype = type(lambda: 1)


def main():  # uses sys.argv
    """Calls subcommand given on command line"""
    parser = ap_sub.ArgumentParser(description=description)
    parser.scan("sdrl.subcmd.*")
    if os.environ.get(b.SEDRILA_COMMAND_ENV) and len(sys.argv) < 2:
        print(f"Using existing environment var {b.SEDRILA_COMMAND_ENV}")
        args = parser.parse_args(os.environ.get(b.SEDRILA_COMMAND_ENV).split(" "))
    else:
        args = parser.parse_args()
    parser.execute_subcommand(args)


if __name__ == "__main__":
    mode = '!pdb'  # profile, pdb, normal
    if mode == 'profile':
        import cProfile
        cProfile.run('main()', sort='cumulative')
    elif mode == 'pdb':
        try:
            main()
        except:
            import pdb
            pdb.post_mortem()
    else:
        main()  # normal life