#!/usr/bin/env python3
import os
import sys

import sdrl.constants as c
import sdrl.argparser
import sdrl.subcmd  # this is where the subcommands will be found


def main():  # uses sys.argv
    """Calls subcommand given on command line"""
    parser = sdrl.argparser.SedrilaArgParser(description="-")  # description is set lazily
    parser.scan("sdrl.subcmd.*")
    if os.environ.get(c.SEDRILA_COMMAND_ENV) and (len(sys.argv) < 2 or sys.argv[1].startswith("--")):
        print(f"Using existing environment var {c.SEDRILA_COMMAND_ENV}")
        input = os.environ.get(c.SEDRILA_COMMAND_ENV)
        if len(sys.argv) >= 2:
            input += " ".join(sys.argv[1:])
        args = parser.parse_args(input.split(" "))
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