import argparse

import yaml

import base
import sdrl.build.generator
import sdrl.build.reader

help = """Creates and renders an instance of a SeDriLa course.
Checks consistency of the course description beforehands.
"""

def configure_argparser(subparser):
    subparser.add_argument('--config', default=base.CONFIG_FILENAME,
                           help="SeDriLa configuration description YAML file")
    subparser.add_argument('targetdir',
                           help="Directory to which output will be written")


def execute(pargs: argparse.Namespace):
    yamltext = base.slurp(pargs.config)
    config = yaml.safe_load(yamltext)
    tasks = sdrl.build.reader.read_and_check(config)
    sdrl.build.generator.generate(pargs, config, tasks)

