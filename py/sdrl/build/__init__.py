import argparse

import yaml

import base
import sdrl.build.generator
import sdrl.build.reader
import sdrl.config

help = """Creates and renders an instance of a SeDriLa course.
Checks consistency of the course description beforehands.
"""

def configure_argparser(subparser):
    subparser.add_argument('--config', default=base.CONFIG_FILENAME,
                           help="SeDriLa configuration description YAML file")
    subparser.add_argument('targetdir',
                           help="Directory to which output will be written")


def execute(pargs: argparse.Namespace):
    config = sdrl.config.Config(pargs.config)
    sdrl.build.reader.read_and_check(config)
    sdrl.build.generator.generate(pargs, config)

