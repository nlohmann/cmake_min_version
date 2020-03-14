## Setup

### CMake binaries

- Download CMake binaries from <https://cmake.org/files/>.
- Extract to a folder, for instance `tools`.

### Virtual Environment

```sh
python3 -mvenv venv
venv/bin/pip3 install -r requirements.txt
```

## Run

Execute

```sh
venv/bin/python3 cmake_min_version.py [--tools_directory DIR] params [params ...]
```

## Example

```sh
❯ cmake_min_version.py ~/projects/example

[  0%] CMake 3.10.2  ✔ works
[ 12%] CMake 3.5.1   ✘ error
       CMakeLists.txt:7 (cmake_minimum_required)
[ 29%] CMake 3.9.1   ✔ works
[ 43%] CMake 3.8.0   ✔ works
[ 57%] CMake 3.7.1   ✘ error
       CMakeLists.txt:16 (target_compile_features)
[ 83%] CMake 3.7.2   ✘ error
       CMakeLists.txt:16 (target_compile_features)
[100%] Minimal working version: CMake 3.8.0
```