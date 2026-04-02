#!/usr/bin/env python3
import sys
import click

import base as b
import sdrl.argparser
import sdrl.subcmd  # this is where the subcommands will be found
from sdrl.subcmd.ui2 import ui2


def main():  # uses sys.argv
    """Calls subcommand given on command line"""
    if sys.platform == 'win32':
        b.critical("sedrila does not run directly on Windows. Please use WSL.")

    # simple check if we use the new command UI
    if len(sys.argv) >= 2 and sys.argv[1] == "ui2":
        # new cli
        @click.group
        def dummy(): pass # dummy to consume 1 layer of subcommands
        dummy.add_command(ui2)
        dummy() # replace this with real call to ui2 in the future
    else:
        # old cli (will be removed)
        parser = sdrl.argparser.SedrilaArgParser(description="-")  # description is set lazily
        parser.scan("sdrl.subcmd.*")
        args = parser.parse_args()
        try:
            parser.execute_subcommand(args)
        except b.CritialError:
            pass  # b.critical has already printed a message


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
        try:
            main()  # normal life
        except KeyboardInterrupt:
            pass  # quit silently
