#!/usr/bin/env python3
import sys
import click

import sedrila.base.base as b
import sedrila.base2.argparser
import sedrila.cmd  # this is where the subcommands will be found
import sedrila.cmd.cli


def main():  # uses sys.argv
    """Calls subcommand given on command line"""
    if sys.platform == 'win32':
        b.critical("sedrila does not run directly on Windows. Please use WSL.")
    if len(sys.argv) >= 2 and sys.argv[1] == "old":
        # legacy cli (will be removed)  TODO 3 after 2027-04
        sys.argv.pop(1)  # consume 'old' prefix
        parser = sedrila.base2.argparser.SedrilaArgParser(description="-")  # description is set lazily
        parser.scan("sedrila.cmd.*")
        args = parser.parse_args()
        try:
            parser.execute_subcommand(args)
        except b.CritialError:
            pass  # b.critical has already printed a message
    else:
        # new CLI:
        try:
            sedrila.cmd.cli.cli()
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
