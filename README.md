# cmake_min_version

Every CMake project requires a call to [`cmake_minimum_required`](http://cmake.org/cmake/help/v3.16/command/cmake_minimum_required.html) to set the minimally required CMake version. However, CMake gives no guidance what this version may be, and a lot of projects just take the current CMake version or whatever the IDE is proposing as default. This is a problem, because some platforms don't always provide the latest CMake version, and a lot of trial and error is needed before projects can be used.

`cmake_min_version` is a script to determine the minimal working version of CMake for a given project. It does not do any magic, but just performs a binary search using a pool of CMake binaries and basically implements the "trial and error" in an efficient way.

## Example

Assume `~/projects/example` contains a project with a `CMakeLists.txt` file. Then the following call determines the minimal working version of CMake:

```sh
❯ venv/bin/python cmake_min_version.py ~/projects/example

Found 94 CMake binaries from directory tools

[  0%] CMake 3.9.2    ✔ works
[ 12%] CMake 3.2.2    ✘ error
       CMakeLists.txt:7 (cmake_minimum_required)
[ 33%] CMake 3.8.0    ✔ works
[ 50%] CMake 3.7.1    ✘ error
       CMakeLists.txt:16 (target_compile_features)
[ 80%] CMake 3.7.2    ✘ error
       CMakeLists.txt:16 (target_compile_features)
[100%] Minimal working version: CMake 3.8.0

cmake_minimum_required(VERSION 3.8.0)
```

As a result, `~/projects/example/CMakeLists.txt` could be adjusted to require CMake 3.8.0.

## FAQ

- Q: Isn't this a rather naive and inefficent approach to achieve the goal?
- A: Yes, but I am currently not aware of a better one. I would be happy to replace this repository with a link on a tool that achieves the same goal.

## Setup

### In a nutshell

1. Install a Python virtual requirement.
2. Download CMake binaries.

### Virtual Environment

The code requires some [packages](requirements.txt) to be installed:

```sh
python3 -mvenv venv
venv/bin/pip3 install -r requirements.txt
```

### CMake binaries

The script [`cmake_downloader.py`](cmake_downloader.py) takes care of downloading CMake binaries:

```sh
usage: cmake_downloader.py [-h] [--os {macos,linux}] [--latest_release]
                           [--latest_patch] [--first_minor]
                           [--release_candidates] [--tools_directory DIR]

Download CMake binaries.

optional arguments:
  -h, --help            show this help message and exit
  --os {macos,linux}    OS to download CMake for (default: macos)
  --latest_release      only download the latest release (default: False)
  --latest_patch        only download the latest patch version for each
                        release (default: False)
  --first_minor         only download the first minor version for each release
                        (default: False)
  --release_candidates  also consider release candidates (default: False)
  --tools_directory DIR
                        path to the CMake binaries (default: "tools")
```

Example run:

```sh
❯ venv/bin/python3 cmake_downloader.py --latest_patch
Retrieving URLs...
100%|███████████████████████████████████████████| 32/32 [00:18<00:00,  1.71it/s]
Downloading CMake 2.8.12.2...
100%|██████████████████████████████████████| 40.5M/40.5M [00:12<00:00, 3.34MB/s]
Downloading CMake 3.0.2...
100%|██████████████████████████████████████| 38.7M/38.7M [00:10<00:00, 3.90MB/s]
Downloading CMake 3.1.3...
100%|██████████████████████████████████████| 28.6M/28.6M [00:07<00:00, 3.99MB/s]
Downloading CMake 3.2.3...
100%|██████████████████████████████████████| 26.4M/26.4M [00:07<00:00, 3.52MB/s]
Downloading CMake 3.3.2...
100%|██████████████████████████████████████| 21.3M/21.3M [00:06<00:00, 3.68MB/s]
Downloading CMake 3.4.3...
100%|██████████████████████████████████████| 21.6M/21.6M [00:07<00:00, 3.07MB/s]
Downloading CMake 3.5.2...
100%|██████████████████████████████████████| 21.8M/21.8M [00:06<00:00, 3.33MB/s]
Downloading CMake 3.6.3...
100%|██████████████████████████████████████| 24.9M/24.9M [00:08<00:00, 2.92MB/s]
Downloading CMake 3.7.2...
100%|██████████████████████████████████████| 25.1M/25.1M [00:09<00:00, 2.85MB/s]
Downloading CMake 3.8.2...
100%|██████████████████████████████████████| 25.2M/25.2M [00:06<00:00, 3.95MB/s]
Downloading CMake 3.9.6...
100%|██████████████████████████████████████| 25.5M/25.5M [00:07<00:00, 3.41MB/s]
Downloading CMake 3.10.3...
100%|██████████████████████████████████████| 25.9M/25.9M [00:06<00:00, 3.93MB/s]
Downloading CMake 3.11.4...
100%|██████████████████████████████████████| 26.1M/26.1M [00:06<00:00, 3.96MB/s]
Downloading CMake 3.12.4...
100%|██████████████████████████████████████| 27.7M/27.7M [00:08<00:00, 3.44MB/s]
Downloading CMake 3.13.5...
100%|██████████████████████████████████████| 30.6M/30.6M [00:08<00:00, 3.82MB/s]
Downloading CMake 3.14.7...
100%|██████████████████████████████████████| 32.0M/32.0M [00:08<00:00, 4.04MB/s]
Downloading CMake 3.15.7...
100%|██████████████████████████████████████| 33.2M/33.2M [00:10<00:00, 3.44MB/s]
Downloading CMake 3.16.5...
100%|██████████████████████████████████████| 34.2M/34.2M [00:08<00:00, 4.11MB/s]
Downloading CMake 3.17.0...
100%|██████████████████████████████████████| 35.3M/35.3M [00:10<00:00, 3.67MB/s]
```

The script downloads and unpacks different versions of CMake into the `tools` folder.

## License

<img align="right" src="http://opensource.org/trademarks/opensource/OSI-Approved-License-100x137.png">

The code is licensed under the [MIT License](http://opensource.org/licenses/MIT):

Copyright &copy; 2020 [Niels Lohmann](http://nlohmann.me)

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
