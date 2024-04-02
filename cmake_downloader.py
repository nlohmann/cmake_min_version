#!/usr/bin/env python3

import argparse
import os.path
import platform
import re
import sys
import tarfile
import tempfile
import zipfile
from typing import List, Dict

import requests
from packaging.version import parse as version_parse
from tqdm import tqdm


def get_folders() -> List[str]:
    url = 'https://cmake.org/files/'
    html = requests.get(url).text
    return list(re.findall(r'>v([0-9.]+)', html))


def get_tarball_urls_version(base_version: str) -> List[str]:
    url = f'https://cmake.org/files/v{base_version}/'
    html = requests.get(url).text
    return sorted([url + filename for filename in re.findall(r'>(cmake-[0-9rc.]+-[^.]+(?:\.tar\.gz|\.zip))', html)])


def get_tarball_urls() -> List[str]:
    folders = get_folders()
    result = []  # type: List[str]

    print('Retrieving URLs...')
    for folder in tqdm(folders):
        urls = get_tarball_urls_version(folder)
        result += urls

    return result


def download_and_extract(url: str, path: str):
    # derive file directory name from URL
    file_name_start_pos = url.rfind('/') + 1
    file_name = url[file_name_start_pos:]
    file_wo_ext = file_name.replace('.tar.gz', '').replace('.zip', '')

    if not os.path.exists(os.path.join(path, file_wo_ext)):
        response = requests.get(url, stream=True)
        response.raise_for_status()
        file_size = int(response.headers['Content-Length'])

        tmpdir = tempfile.TemporaryDirectory()
        full_file_name = os.path.join(tmpdir.name, file_name)

        progress = tqdm(total=file_size, unit='B', unit_scale=True, unit_divisor=1024)
        with open(full_file_name, 'wb+') as f:
            for data in response:
                progress.update(len(data))
                f.write(data)
        progress.close()

        if url.endswith('.zip'):
            with zipfile.ZipFile(full_file_name, mode='r') as zip_ref:
                zip_ref.extractall(path)
        else:
            with tarfile.open(full_file_name, mode='r:gz') as tar:
                tar.extractall(path=path)


def create_version_dict(os: str, bitness: int) -> Dict[str, str]:
    # create a whitelist for the current OS
    search_terms = []
    if os == 'macos' and bitness == 64:
        search_terms = ['Darwin64', 'Darwin-x86_64', 'macos-universal']
    elif os == 'linux' and bitness == 64:
        search_terms = ['Linux-x86_64', 'linux-x86_64']
    elif os == 'windows' and bitness == 32:
        search_terms = ['win32-x86']
    elif os == 'windows' and bitness == 64:
        search_terms = ['win64-x64', 'windows-x86_64']
    
    if len(search_terms) == 0:
        raise Exception(f'Unsupported OS or bitness: {os}, {bitness}')

    tarball_urls = get_tarball_urls()
    result = dict()
    for tarball_url in tarball_urls:
        # skip if the tarball URL does not contain any of the search terms
        if not any([search_term in tarball_url for search_term in search_terms]):
            continue

        version = re.findall(r'cmake-(([0-9.]+)(-rc[0-9]+)?)', tarball_url)[0][0]
        version_public = version_parse(version).public

        if version_public in result:
            continue
            # print(f'Warning: Found multiple URLs for version {version_public}.')
        result[version_public] = tarball_url

    return result


if __name__ == '__main__':
    # get default value for current system
    default_os = 'macos' if platform.system() == 'Darwin' else 'linux' if platform.system() == 'Linux' else 'windows' if platform.system() == 'Windows' else None
    # get the default bitness
    default_bitness = 32 if sys.maxsize == 2**31-1 else 64 if sys.maxsize == 2**63-1 else None

    parser = argparse.ArgumentParser(description='Download CMake binaries.')
    parser.add_argument('--os', help=f'OS to download CMake for (default: {default_os})',
                        choices=['macos', 'linux', 'windows'], default=default_os)
    parser.add_argument('--bitness', help=f'bitness to download CMake for (default: {default_bitness})',
                        choices=[32, 64], default=default_bitness)
    parser.add_argument('--latest_release', action='store_true',
                        help='only download the latest release (default: False)')
    parser.add_argument('--latest_patch', action='store_true',
                        help='only download the latest patch version for each release (default: False)')
    parser.add_argument('--first_minor', action='store_true',
                        help='only download the first minor version for each release (default: False)')
    parser.add_argument('--release_candidates', action='store_true',
                        help='also consider release candidates (default: False)')
    parser.add_argument('--min_version', help='only download versions greater or equal than MIN_VERSION')
    parser.add_argument('--max_version', help='only download versions less or equal than MAX_VERSION')
    parser.add_argument('--tools_directory', metavar='DIR', default='tools',
                        help='path to the CMake binaries (default: "tools")')
    args = parser.parse_args()

    version_dict = create_version_dict(os=args.os, bitness=args.bitness)
    versions = sorted([version_parse(version) for version in version_dict.keys()])
    print(f'Found {len(versions)} versions from {versions[0]} to {versions[-1]}.')

    if args.min_version:
        versions = sorted([version for version in versions if version >= version_parse(args.min_version)])

    if args.max_version:
        versions = sorted([version for version in versions if version <= version_parse(args.max_version)])

    if not args.release_candidates:
        versions = [version for version in versions if not version.is_prerelease]

    if args.latest_patch:
        result = []
        for major, minor in set([(version.major, version.minor) for version in versions]):
            result.append([version for version in versions if version.major == major and version.minor == minor][-1])
        versions = sorted(result)

    if args.first_minor:
        result = []
        for major, minor in set([(version.major, version.minor) for version in versions]):
            result.append([version for version in versions if version.major == major and version.minor == minor][0])
        versions = sorted(result)

    if args.latest_release:
        versions = versions[-1:]

    for idx, version in enumerate(versions):
        print(f'Downloading CMake {version.public} ({idx+1}/{len(versions)})...')
        download_and_extract(url=version_dict[version.public], path=args.tools_directory)
