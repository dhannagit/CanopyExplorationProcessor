"""Remove only Canopy Exploration Processor-managed environments, including long Windows paths."""

import argparse
import os
from pathlib import Path
import re
import shutil
import stat
import sys


def extended_path(path: str) -> str:
    if os.name != "nt":
        return path
    if path.startswith("\\\\"):
        return "\\\\?\\UNC\\" + path[2:]
    return "\\\\?\\" + path


def reject_link_ancestors(path: str) -> None:
    for ancestor in reversed((Path(path), *Path(path).parents)):
        try:
            attributes = os.lstat(extended_path(str(ancestor)))
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(attributes.st_mode) or getattr(attributes, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise ValueError("Managed environment ancestors must not be links or junctions")


def remove_readonly(function, path: str, error: BaseException) -> None:
    if not isinstance(error, PermissionError):
        raise error
    attributes = os.lstat(path)
    if getattr(attributes, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        raise error
    if not getattr(attributes, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_READONLY:
        raise error
    os.chmod(path, stat.S_IREAD | stat.S_IWRITE)
    function(path)


def remove_environment(install_directory: str, release_name: str) -> None:
    if not re.fullmatch(r"release-[a-f0-9]{32}", release_name):
        raise ValueError("Invalid managed release identifier")
    if not os.path.isabs(install_directory) or install_directory.startswith(("\\\\?\\", "\\\\.\\")):
        raise ValueError("Use a normal absolute installation directory")
    installation = os.path.abspath(install_directory)
    if os.path.dirname(installation) == installation:
        raise ValueError("Installation directory must not be a filesystem root")
    target = os.path.join(installation, "envs", release_name)
    reject_link_ancestors(target)
    executable = os.path.normcase(os.path.realpath(sys.executable))
    normalized_target = os.path.normcase(os.path.abspath(target))
    try:
        running_inside_target = os.path.commonpath((normalized_target, executable)) == normalized_target
    except ValueError:
        running_inside_target = False
    if running_inside_target:
        raise ValueError("Cleanup Python must run outside the environment being removed")
    try:
        attributes = os.lstat(extended_path(target))
    except FileNotFoundError:
        return
    if not stat.S_ISDIR(attributes.st_mode):
        raise ValueError("Managed environment must be a directory")
    shutil.rmtree(extended_path(target), onexc=remove_readonly)
    if os.path.lexists(extended_path(target)):
        raise OSError("Managed environment was not completely removed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-directory", required=True)
    parser.add_argument("--release-name", required=True)
    arguments = parser.parse_args()
    remove_environment(arguments.install_directory, arguments.release_name)


if __name__ == "__main__":
    main()