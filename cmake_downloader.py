import argparse
import os.path
import platform
import re
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
    url = 'https://cmake.org/files/v{base_version}/'.format(base_version=base_version)
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
    file_name_start_pos = url.rfind("/") + 1
    file_name = url[file_name_start_pos:]
    file_wo_ext, file_ext = os.path.splitext(file_name)
    if file_ext != ".zip":
        file_wo_ext, file_ext2 = os.path.splitext(file_wo_ext)
        file_ext=file_ext+file_ext2
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

        if file_ext == ".zip":
            with zipfile.ZipFile(full_file_name, 'r') as zip_ref:
                zip_ref.extractall(path)
        else:
            tar = tarfile.open(full_file_name, "r:gz")
            tar.extractall(path=path)
            tar.close()


def create_version_dict(os: str) -> Dict[str, str]:
    tarball_urls = get_tarball_urls()
    result = dict()

    for tarball_url in tarball_urls:
        version = re.findall(r'cmake-(([0-9.]+)(-rc[0-9]+)?)', tarball_url)[0][0]

        if (os == 'macos' and ('Darwin64' in tarball_url or 'Darwin-x86_64' in tarball_url)) \
                or (os == 'linux' and 'Linux-x86_64' in tarball_url) \
                or (os == 'windows' and ('win32-x86' in tarball_url or 'win64-x64' in tarball_url)):
            if version_parse(version).public not in result or \
                    (version_parse(version).public in result and 'win64-x64' in tarball_url):
                result[version_parse(version).public] = tarball_url

    return result


if __name__ == '__main__':
    # get default value for current system
    default_os = 'macos' if platform.system() == 'Darwin' else 'linux' if platform.system() == 'Linux' else 'windows' if platform.system() == 'Windows' else None

    parser = argparse.ArgumentParser(description='Download CMake binaries.')
    parser.add_argument('--os', help='OS to download CMake for (default: {default_os})'.format(default_os=default_os),
                        choices=['macos', 'linux', 'windows'], default=default_os)
    parser.add_argument('--latest_release', action='store_true',
                        help='only download the latest release (default: False)')
    parser.add_argument('--latest_patch', action='store_true',
                        help='only download the latest patch version for each release (default: False)')
    parser.add_argument('--first_minor', action='store_true',
                        help='only download the first minor version for each release (default: False)')
    parser.add_argument('--release_candidates', action='store_true',
                        help='also consider release candidates (default: False)')
    parser.add_argument('--tools_directory', metavar='DIR', default='tools',
                        help='path to the CMake binaries (default: "tools")')
    args = parser.parse_args()

    version_dict = create_version_dict(os=args.os)
    versions = sorted([version_parse(version) for version in version_dict.keys()])

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

    for version in versions:
        print('Downloading CMake {version}...'.format(version=version.public))
        download_and_extract(url=version_dict[version.public], path=args.tools_directory)
