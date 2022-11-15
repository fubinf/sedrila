#!/usr/bin/env python3

import argparse
import typing as tg

import sdrl.build  # for course developers and instructors
import sdrl.instructor
import sdrl.student

description = "Tool for 'self-driven lab' (SeDriLa) university courses."

moduletype = type(sdrl)  # TODO: get this from stdlib
functiontype = type(lambda: 1)  # TODO: get this from stdlib


def main():  # uses sys.argv
    """Calls subcommand given on command line"""
    argparser = setup_argparser(sdrl, description)
    pargs = argparser.parse_args()
    subcmd = pargs.subcmd
    submodulename = subcmd.replace('-', '_')  # CLI command my-command corresponds to module sdrl.my_command
    module = getattr(sdrl, submodulename)
    module.execute(pargs)


def setup_argparser(superpkg: str, description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    subparsers = parser.add_subparsers(dest='subcmd', required=True)
    for attrname in dir(superpkg):
        myattr = getattr(sdrl, attrname)
        if not isinstance(myattr, moduletype):
            continue  # skip non-modules
        submodule = myattr  # now we know it _is_ a module
        subcommand_name = attrname.replace('_', '-')
        required_attrs = (('help', str), ('execute', functiontype), ('configure_argparser', functiontype))
        if _misses_any_of(submodule, required_attrs):
            continue  # skip modules that are not proper subcommand modules
        subparser = subparsers.add_parser(subcommand_name, help=submodule.help)
        submodule.configure_argparser(subparser)
    return parser
    

def _misses_any_of(module: moduletype, required: tg.Sequence[tg.Tuple[str, type]]) -> bool:
    for name, _type in required:
        module_elem = getattr(module, name, None)
        if not module_elem or not isinstance(module_elem, _type):
            return True  # this is not a subcommand-shaped submodule
    return False


if __name__ == "__main__":
    main()