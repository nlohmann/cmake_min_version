import argparse
import os.path
import re
from typing import List

import progressbar
import requests


def get_folders() -> List[str]:
    url = 'https://cmake.org/files/'
    html = requests.get(url).text
    return list(re.findall(r'>v([0-9.]+)', html))


def get_tarball_urls_version(base_version: str) -> List[str]:
    url = 'https://cmake.org/files/v{base_version}/'.format(base_version=base_version)
    html = requests.get(url).text
    return sorted([url + filename for filename in re.findall(r'>(cmake-[0-9rc.]+-[^.]+\.tar\.gz)', html)])


def get_tarball_urls() -> List[str]:
    folders = get_folders()
    result = []  # type: List[str]
    progress = progressbar.ProgressBar()

    print('Retrieving URLs...')
    for folder in progress(folders):
        urls = get_tarball_urls_version(folder)
        result += urls

    return result


def download_file(url: str):
    response = requests.get(url, stream=True)
    response.raise_for_status()

    file_name_start_pos = url.rfind("/") + 1
    file_name = url[file_name_start_pos:]

    file_size = int(response.headers['Content-Length'])

    widgets = [progressbar.Bar(), progressbar.DataSize(), progressbar.FileTransferSpeed(), ' (', progressbar.ETA(), ')']
    progress = progressbar.ProgressBar(max_value=file_size, widgets=widgets)
    downloaded_bytes = 0

    if not os.path.exists(file_name) or os.path.getsize(file_name) != file_size:
        with open(file_name, 'wb+') as f:
            for data in response:
                downloaded_bytes += len(data)
                progress.update(downloaded_bytes)
                f.write(data)
        progress.finish()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Download CMake binaries.')
    parser.add_argument('version', type=str, nargs='*', help='version to download')
    parser.add_argument('--tools_directory', metavar='DIR', default='tools',
                        help='path to the CMake binaries (default: "tools")')
    args = parser.parse_args()

    tarball_urls = get_tarball_urls()

    print('Downloading CMake releases...')
    for tarball_url in tarball_urls:
        if 'Darwin64' in tarball_url or 'Darwin-x86_64' in tarball_url:
            print(tarball_url)
            download_file(tarball_url)
