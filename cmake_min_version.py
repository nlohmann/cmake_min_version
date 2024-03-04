#!/usr/bin/env python3

import argparse
from datetime import datetime, timedelta
import json
import platform
import math
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Dict, List, Optional, NamedTuple, Tuple, Union, cast

from packaging.version import parse as version_parse
from termcolor import colored

from cmake_downloader import create_version_dict, download_and_extract


class CMakeBinary(NamedTuple):
    version: str
    binary: Union[str, Path]


class ConfigureResult:
    def __init__(self, return_code: int, stderr: str):
        self.success = return_code == 0  # type: bool
        self.proposed_version = None  # type: Optional[str]
        self.reason = None  # type: Optional[str]

        # try to read proposed minimal version from stderr output
        try:
            self.proposed_version = re.findall(r'CMake ([^ ]+) or higher is required.', stderr)[0]

            # support ranges
            if '..' in self.proposed_version:
                self.proposed_version = self.proposed_version.split('..')[0]
            # make sure all versions are major.minor.patch
            if self.proposed_version.count('.') == 1:
                self.proposed_version += '.0'
        except IndexError:
            pass

        try:
            self.reason = re.findall(r'CMake Error at (.*):', stderr)[0]
        except IndexError:
            try:
                self.reason = re.findall(r'CMake Error: ([^\n]+)', stderr)[0]
            except IndexError:
                pass


def latest_patches(version_dict: Dict[str, str]) -> Dict[str, str]:
    versions = sorted([version_parse(version) for version in version_dict.keys()])
    result = []
    for major, minor in set([(version.major, version.minor) for version in versions]):
        result.append([version for version in versions if version.major == major and version.minor == minor][-1])
    return {version.public: version_dict[version.public] for version in result}


def create_version_dirs(tools_dir: Union[str, Path], latest_patch: bool) -> Dict[str, str]:
    tools_dir = Path(tools_dir).absolute()
    tools_dir.mkdir(parents=True, exist_ok=True)

    one_week_ago = datetime.today() - timedelta(days=7)
    urls: Path = tools_dir / 'versions.json'
    try:
        mtime = datetime.fromtimestamp(urls.stat().st_mtime)
    except FileNotFoundError:
        mtime = datetime.min
    if mtime > one_week_ago:
        version_dict = cast(Dict[str, str], json.load(urls.open()))
        if latest_patch:
            version_dict = latest_patches(version_dict)
        return version_dict

    version_dict = create_version_dict('linux')
    pre_release = []
    for version, tarball_url in version_dict.items():
        if version_parse(version).is_prerelease:
            pre_release.append(version)
        else:
            version_dir = tools_dir / Path(tarball_url).name.removesuffix('.tar.gz')
            version_dir.mkdir(exist_ok=True)
            version_dir.touch()

    for version in pre_release:
        del version_dict[version]

    json.dump(version_dict, urls.open('w'))
    if latest_patch:
        version_dict = latest_patches(version_dict)
    return version_dict


def get_cmake_binaries(tools_dir: str, latest_patch: bool) -> Tuple[List[CMakeBinary], Dict[str, str]]:
    version_dict = create_version_dirs(tools_dir, latest_patch)

    binaries = []  # type: List[CMakeBinary]
    if platform.system() == "Windows":
        exe = 'bin/cmake.exe'
    else:
        exe = 'bin/cmake'

    dirnames = Path(tools_dir).absolute().glob('cmake-*')

    for dirname in dirnames:
        try:
            version = re.findall(r'cmake-([^-]+)-', str(dirname))[0]
            if version in version_dict:
                binaries.append(CMakeBinary(version, dirname / exe))
        except IndexError:
            pass

    print(f'Found {len(binaries)} CMake binaries from directory {tools_dir}\n')
    return sorted(binaries, key=lambda x: version_parse(x.version)), version_dict


def get_binary(binary: Union[str, Path], version_dict: Dict[str, str]) -> None:
    binary = Path(binary)
    if binary.exists():
        return

    tools_dir = binary.parent.parent.parent
    version = version_parse(re.findall(r'cmake-(([0-9.]+)(-rc[0-9]+)?)', str(binary))[0][0])
    download_and_extract(url=version_dict[version.public], path=tools_dir, clobber=True)


def try_configure(binary: Union[str, Path], cmake_parameters: List[str], version_dict: Dict[str, str]) -> ConfigureResult:
    get_binary(binary, version_dict)
    tmpdir = tempfile.TemporaryDirectory()
    proc = subprocess.Popen([binary] + cmake_parameters + ['-Wno-dev'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, cwd=tmpdir.name)
    proc.wait()

    stderr = '' if proc.stderr is None else proc.stderr.read().decode('utf-8')
    return ConfigureResult(return_code=proc.returncode, stderr=stderr)


def binary_search(cmake_parameters: List[str], tools_dir: str, latest_patch: bool) -> Optional[CMakeBinary]:
    versions, version_dict = get_cmake_binaries(tools_dir, latest_patch)  # type: Tuple[List[CMakeBinary], Dict[str, str]]
    cmake_versions = [len(cmake.version) for cmake in versions]
    if len(cmake_versions) == 0:
        print(colored('Error: No CMake versions found in the tool dir. Make sure to run the cmake_downloader script first.', 'red'))
        sys.exit(1)
    longest_version_string = max(cmake_versions) + 1  # type: int

    lower_idx = 0  # type: int
    upper_idx = len(versions) - 1  # type: int
    last_success_idx = None  # type: Optional[int]

    steps = 0  # type: int

    while lower_idx <= upper_idx:
        mid_idx = int((lower_idx + upper_idx) / 2)  # type: int
        cmake_binary = versions[mid_idx]  # type: CMakeBinary

        steps += 1
        remaining_versions = upper_idx - lower_idx + 1  # type: int
        remaining_steps = int(math.ceil(math.log2(remaining_versions)))  # type: int

        print('[{progress:3.0f}%] CMake {cmake_version:{longest_version_string}}'.format(
            progress=100.0 * float(steps - 1) / (steps + remaining_steps),
            cmake_version=cmake_binary.version, longest_version_string=longest_version_string), end='', flush=True
        )

        result = try_configure(cmake_binary.binary, cmake_parameters, version_dict)  # type: ConfigureResult

        if result.success:
            print(colored('✔ works', 'green'))
            last_success_idx = mid_idx
            upper_idx = mid_idx - 1
        else:
            print(colored('✘ error', 'red'))
            if result.reason:
                print(f'       {result.reason}')
            proposed_binary = [x for x in versions if x.version == result.proposed_version]
            lower_idx = versions.index(proposed_binary[0]) if len(proposed_binary) else mid_idx + 1

    return versions[last_success_idx] if last_success_idx is not None else None


def full_search(cmake_parameters: List[str], tools_dir: str, latest_patch: bool) -> Optional[CMakeBinary]:
    versions, version_dict = get_cmake_binaries(tools_dir, latest_patch)  # type: Tuple[List[CMakeBinary], Dict[str, str]]
    longest_version_string = max([len(cmake.version) for cmake in versions]) + 1  # type: int

    lower_idx = 0  # type: int
    upper_idx = len(versions) - 1  # type: int
    last_success_idx = None  # type: Optional[int]

    steps = 0  # type: int

    for cmake_binary in versions:
        steps += 1
        remaining_versions = upper_idx - lower_idx + 1  # type: int
        remaining_steps = int(math.ceil(math.log2(remaining_versions)))  # type: int

        print('[{progress:3.0f}%] CMake {cmake_version:{longest_version_string}}'.format(
            progress=100.0 * float(steps - 1) / (steps + remaining_steps),
            cmake_version=cmake_binary.version, longest_version_string=longest_version_string), end='', flush=True
        )

        result = try_configure(cmake_binary.binary, cmake_parameters, version_dict)  # type: ConfigureResult

        if result.success:
            print(colored('✔ works', 'green'))
            if not last_success_idx or last_success_idx > steps - 1:
                last_success_idx = steps - 1
        else:
            print(colored('✘ error', 'red'))
            if result.reason:
                print(f'       {result.reason}')

    return versions[last_success_idx] if last_success_idx is not None else None


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Find the minimal required CMake version for a project.')
    parser.add_argument('params', type=str, nargs='+', help='parameters to pass to CMake')
    parser.add_argument('--latest_patch', action='store_true',
                        help='only download the latest patch version for each release (default: False)')
    parser.add_argument('--tools_directory', metavar='DIR', default='tools',
                        help='path to the CMake binaries (default: "tools")')
    parser.add_argument('--full_search', default=False,
                        help='Searches using a top down approach instead of a binary search (default: False)')
    args = parser.parse_args()

    if args.full_search:
        working_version = full_search(args.params, args.tools_directory, args.latest_patch)
    else:
        working_version = binary_search(args.params, args.tools_directory, args.latest_patch)

    if working_version:
        print('[100%] Minimal working version: {cmake} {version}'.format(
            cmake=colored('CMake', 'blue'), version=colored(working_version.version, 'blue')))

        print(f'\ncmake_minimum_required(VERSION {working_version.version})')

    else:
        print('[100%] {message}'.format(message=colored('ERROR: Could not find working version.', 'red')))
