#!/usr/bin/env python3

import argparse
import contextlib
import math
import platform
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from time import time
from typing import List, NamedTuple, Optional

from packaging.version import parse as version_parse
from termcolor import colored


class CMakeBinary(NamedTuple):
    version: str
    binary: Path


class ConfigureResult:
    def __init__(self, return_code: int, stderr: str):
        self.success = return_code == 0  # type: bool
        self.proposed_version = None  # type: Optional[str]
        self.reason = None  # type: Optional[str]
        self.stderr = stderr

        # try to read proposed minimal version from stderr output
        try:
            self.proposed_version = re.findall(r"CMake ([^ ]+) or higher is required.", stderr)[0]

            # support ranges
            if ".." in self.proposed_version:
                self.proposed_version = self.proposed_version.split("..")[0]
            # make sure all versions are major.minor.patch
            if self.proposed_version.count(".") == 1:
                self.proposed_version += ".0"
        except IndexError:
            pass

        try:
            self.reason = re.findall(r"CMake Error at (.*):", stderr)[0]
        except IndexError:
            try:
                self.reason = re.findall(r"CMake Error: ([^\n]+)", stderr)[0]
            except IndexError:
                pass


def get_cmake_binaries(tools_dir: Path) -> List[CMakeBinary]:
    start_time = time()
    binaries = []  # type: List[CMakeBinary]
    if platform.system() == "Windows":
        filenames = tools_dir.rglob("**/bin/cmake.exe")
    else:
        filenames = tools_dir.rglob("**/bin/cmake")

    for filename in filenames:
        with contextlib.suppress(IndexError):
            version = re.findall(r"cmake-([^-]+)-", str(filename))[0]
            binaries.append(CMakeBinary(version, Path(filename).resolve()))

    print(f"Found {len(binaries)} CMake binaries from directory {tools_dir} in {time()-start_time:.2f} seconds\n")
    return sorted(binaries, key=lambda x: version_parse(x.version))


def try_configure(binary: Path, cmake_parameters: List[str]) -> ConfigureResult:
    tmpdir = tempfile.TemporaryDirectory()
    proc = subprocess.Popen(
        [binary, *cmake_parameters, "-Wno-dev"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        cwd=tmpdir.name,
    )
    proc.wait()

    return ConfigureResult(
        return_code=proc.returncode, stderr=proc.stderr.read().decode("utf-8") if proc.stderr else ""
    )


def binary_search(*, cmake_parameters: List[str], tools_dir: Path, error_output: bool) -> Optional[CMakeBinary]:
    versions = get_cmake_binaries(tools_dir)  # type: List[CMakeBinary]
    cmake_versions = [len(cmake.version) for cmake in versions]
    if len(cmake_versions) == 0:
        print(
            colored(
                "Error: No CMake versions found in the tool dir. Make sure to run the cmake_downloader script first.",
                "red",
            ),
        )
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

        print(
            "[{progress:3.0f}%] CMake {cmake_version:{longest_version_string}}".format(
                progress=100.0 * float(steps - 1) / (steps + remaining_steps),
                cmake_version=cmake_binary.version,
                longest_version_string=longest_version_string,
            ),
            end="",
            flush=True,
        )

        result = try_configure(binary=cmake_binary.binary, cmake_parameters=cmake_parameters)  # type: ConfigureResult

        if result.success:
            print(colored("✔ works", "green"))
            last_success_idx = mid_idx
            upper_idx = mid_idx - 1
        else:
            print(colored("✘ error", "red"))
            if error_output:
                for line in result.stderr.splitlines():
                    print(colored(f"       {line}", "yellow"))
            elif result.reason:
                print(colored(f"       {result.reason}", "yellow"))
            proposed_binary = [x for x in versions if x.version == result.proposed_version]
            lower_idx = versions.index(proposed_binary[0]) if len(proposed_binary) else mid_idx + 1

    return versions[last_success_idx] if last_success_idx is not None else None


def full_search(*, cmake_parameters: List[str], tools_dir: Path, error_output: bool) -> Optional[CMakeBinary]:
    versions = get_cmake_binaries(tools_dir)  # type: List[CMakeBinary]
    longest_version_string = max([len(cmake.version) for cmake in versions]) + 1  # type: int
    last_success_idx = None  # type: Optional[int]

    for steps, cmake_binary in enumerate(versions):
        print(
            "[{progress:3.0f}%] CMake {cmake_version:{longest_version_string}}".format(
                progress=100.0 * float(steps) / len(versions),
                cmake_version=cmake_binary.version,
                longest_version_string=longest_version_string,
            ),
            end="",
            flush=True,
        )

        result = try_configure(binary=cmake_binary.binary, cmake_parameters=cmake_parameters)  # type: ConfigureResult

        if result.success:
            print(colored("✔ works", "green"))
            if not last_success_idx:
                last_success_idx = steps
        else:
            last_success_idx = None
            print(colored("✘ error", "red"))
            if error_output:
                for line in result.stderr.splitlines():
                    print(colored(f"       {line}", "yellow"))
            elif result.reason:
                print(colored(f"       {result.reason}", "yellow"))

    return versions[last_success_idx] if last_success_idx is not None else None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Find the minimal required CMake version for a project.")
    parser.add_argument("params", type=str, nargs="+", help="parameters to pass to CMake")
    parser.add_argument(
        "--tools_directory",
        metavar="DIR",
        default="tools",
        help='path to the CMake binaries (default: "tools")',
    )
    parser.add_argument(
        "--full_search",
        default=False,
        action="store_true",
        help="Searches using a top down approach instead of a binary search (default: False)",
    )
    parser.add_argument(
        "--error_details",
        default=False,
        action="store_true",
        help="Print the full stderr output in case of an error (default: False)",
    )
    args = parser.parse_args()

    if args.full_search:
        working_version = full_search(
            cmake_parameters=args.params,
            tools_dir=Path(args.tools_directory),
            error_output=args.error_details,
        )
    else:
        working_version = binary_search(
            cmake_parameters=args.params,
            tools_dir=Path(args.tools_directory),
            error_output=args.error_details,
        )

    if working_version:
        print(
            "[100%] Minimal working version: {cmake} {version}".format(
                cmake=colored("CMake", "blue"),
                version=colored(working_version.version, "blue"),
            ),
        )

        print(f"\ncmake_minimum_required(VERSION {working_version.version})")

    else:
        print("[100%] {message}".format(message=colored("ERROR: Could not find working version.", "red")))
