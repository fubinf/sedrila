#!/usr/bin/env python3

import argparse
import typing as tg

import sdrl.subcmd.author  # for course developers
import sdrl.subcmd.instructor  # for people who check submissions
import sdrl.subcmd.student  # for course students 

description = "Tool for 'self-driven lab' (SeDriLa) university courses."

moduletype = type(sdrl)  # TODO: get this from stdlib
functiontype = type(lambda: 1)  # TODO: get this from stdlib


def main():  # uses sys.argv
    """Calls subcommand given on command line"""
    subcmd_package = sdrl.subcmd
    argparser = setup_argparser(subcmd_package, description)
    pargs = argparser.parse_args()
    subcmd = pargs.subcmd
    submodulename = subcmd.replace('-', '_')  # CLI command my-command corresponds to module sdrl.my_command
    module = getattr(subcmd_package, submodulename)
    module.execute(pargs)


def setup_argparser(superpkg, description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    subparsers = parser.add_subparsers(dest='subcmd', required=True)
    for attrname in dir(superpkg):
        myattr = getattr(superpkg, attrname)
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
    print_profile = False
    if print_profile:
        import cProfile
        cProfile.run('main()')
    else:
        main()  # normal life