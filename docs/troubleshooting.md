# Potential issues and solutions when installing on Termux

## Installing Termux-API

Some functionalities require the support of Termux-API, such as copying code snippets and voice features.
To install Termux-API, you need to:
1. Install the Termux-API plugin. The Termux:API application can be obtained from [F-Droid](https://f-droid.org/en/packages/com.termux.api/).
2. After installing Termux-API, you also need to execute `pkg install termux-api` in Termux to install the corresponding package.
3. Grant the necessary permissions to Termux-API.

## Installing numpy

First, ensure that numpy is installed. You can use `pkg install python-numpy` to install numpy, referring to [Termux Wiki](https://wiki.termux.com/wiki/Python). If using a virtual environment, you might need to use `python -m venv --system-site-packages <your-venv-path>` to make python-numpy available within the virtual environment.

## Installing lxml

```
pkg update && pkg upgrade
pkg install python libxml2 libxslt pkg-config
pip install cython wheel
CFLAGS="-Wno-error=incompatible-function-pointer-types -O0" pip install lxml
```

## Possible issues when installing qdrant-client on Termux

### Installation of maturin is required

```
pkg rem binutils -y
apt autoremove
pkg i binutils-is-llvm rust -y
pip install maturin
```

### Installation of grpcio is required

Make sure you have the header `ares.h` in `/data/data/com.termux/files/usr/include`.
You can install it using: `pkg install c-ares`.
Then:

```
GRPC_PYTHON_DISABLE_LIBC_COMPATIBILITY=1 \
GRPC_PYTHON_BUILD_SYSTEM_OPENSSL=1 \
GRPC_PYTHON_BUILD_SYSTEM_ZLIB=1 \
GRPC_PYTHON_BUILD_SYSTEM_CARES=1 \
CFLAGS+=" -U__ANDROID_API__ -D__ANDROID_API__=26 -include unistd.h" \
LDFLAGS+=" -llog" \
pip install grpcio
```
If it still doesn't work, refer to [here](https://github.com/termux/termux-packages/issues/17583).

## Failed to build wheel when installing ruamel.yaml.clib

When installing or updating semantic-kernel to version 0.3.11.dev0 or later, the ruamel.yaml.clib library is required.
If you encounter a "failed to build wheel" error, the solution is as follows:
```
pkg upgrade
pkg install build-essential python
CFLAGS="-Wno-incompatible-function-pointer-types" pip install ruamel.yaml.clib
```

## Failed to build wheel for `playsound`

If you encounter a 'Failed to build wheel' error during the installation of playsound,
please ensure that `wheel` and `setuptools` are installed on your system.
You can install these build tools by running the command
```
pip install wheel setuptools
```
in your terminal or command prompt.


# Potential issues and solutions on MacOS

## The audio playback function is not working properly

```
pip3 install PyObjC
```
