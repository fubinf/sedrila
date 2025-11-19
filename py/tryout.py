# This file is separate from the actual application
# we use it for 1-off scripts, often for debugging or testing purposes.
# Each time we need it for a new purpose, we kick out previous stuff.

"""
Test html_for_file() on all .md files in second-level subdirectories.
Usage: python tryout.py <topdir>
"""

import os
import sys
import pathlib
import traceback
import argparse_subcommand as ap_sub

import base as b
import sdrl.participant
import sdrl.webapp as webapp


def second_level_subdirs(topdir: str) -> list[str]:
    """Return all second-level subdirectories (topdir/*/)."""
    toppath = pathlib.Path(topdir)
    dirs = [str(d) for d in toppath.iterdir() if d.is_dir()]
    return sorted(dirs)


def target_files(directory: str) -> list[str]:
    """Return all .md files in a directory (non-recursive)."""
    dirpath = pathlib.Path(directory)
    return sorted([str(f) for f in dirpath.glob("*.prot")])


def test_html_for_file(topdir: str):
    """Test html_for_file() on .md files in second-level subdirs."""
    # Get all subdirectories (these are student directories)
    dirs = second_level_subdirs(topdir)
    if not dirs:
        print(f"No subdirectories found in {topdir}")
        return
    print(f"Found {len(dirs)} subdirectories\n")
    # Process each directory
    for dirname in dirs:
        target_files_list = target_files(dirname)
        if not target_files_list:
            continue
        print(f"{dirname} ({len(target_files_list)} target files)")
        # Try to create context for this directory
        try:
            # Create minimal pargs namespace
            pargs = ap_sub.Namespace()
            pargs.port = webapp.DEFAULT_PORT
            # Create context
            ctx = sdrl.participant.Context(
                pargs=pargs,
                dirs=[dirname],
                is_instructor=True,
                show_size=True
            )
            # Make context available globally for webapp functions
            sdrl.participant._context = ctx
            studentlist = ctx.studentlist
        except Exception as e:
            continue
        # Process each .md file
        for target_file in target_files_list:
            # Convert absolute path to relative path from student directory
            target_path = pathlib.Path(target_file)
            try:
                # Try to make it relative to the student directory
                student_path = pathlib.Path(dirname)
                try:
                    relative_path = "/" + str(target_path.relative_to(student_path))
                except ValueError:
                    print(f"Skipping {target_file}: not in student directory")
                    relative_path = None
                    continue
                # Call html_for_file()
                result = webapp.html_for_file(studentlist, relative_path)
            except Exception as ex:
                # Report exception with separator and filename
                print(f"\n{'-'*80}")
                print(f"EXCEPTION in file: {target_file}")
                print(f"{'-'*80}")
                traceback.print_exc()
                print(f"{'-'*80}\n")
                # Skip remaining files in this directory
                break


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <topdir>")
        print("  topdir: directory containing student work directories")
        sys.exit(1)
    topdir = sys.argv[1]
    if not os.path.isdir(topdir):
        print(f"Error: {topdir} is not a directory")
        sys.exit(1)
    test_html_for_file(topdir)


if __name__ == "__main__":
    main()
