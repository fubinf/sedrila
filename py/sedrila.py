#!/usr/bin/env python3

import argparse_subcommand as ap_sub
import os

import base as b
import sdrl.subcmd  # this is where the subcommands will be found

description = "Tool for 'self-driven lab' (SeDriLa) university courses."

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
    print_profile = False
    if print_profile:
        import cProfile
        cProfile.run('main()')
    else:
        main()  # normal life