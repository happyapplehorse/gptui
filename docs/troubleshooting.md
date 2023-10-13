# Potential issues and solutions when installing on Termux

## Installing numpy

First, ensure that numpy is installed. You can use `pkg install python-numpy` to install numpy, referring to [Termux Wiki](https://wiki.termux.com/wiki/Python). If using a virtual environment, you might need to use `python -m venv --system-site-packages <your-venv-path>` to make python-numpy available within the virtual environment.

## Possible issues when installing qdrant-client on Termux

### Installation of maturin is required

```
pkg rem binutils -y
apt autoremove
pkg i binutils-is-llvm rust -y
pip install maturin
```

### Installation of grpcio is required

```
GRPC_PYTHON_DISABLE_LIBC_COMPATIBILITY=1 \
GRPC_PYTHON_BUILD_SYSTEM_OPENSSL=1 \
GRPC_PYTHON_BUILD_SYSTEM_ZLIB=1 \
GRPC_PYTHON_BUILD_SYSTEM_CARES=1 \
CFLAGS+=" -U__ANDROID_API__ -D__ANDROID_API__=26 -include unistd.h" \
LDFLAGS+=" -llog" \
pip install grpcio
```

### When installing or updating semantic-kernel to version 0.3.11.dev0 or later, the ruamel.yaml.clib library is required. If you encounter the "failed build wheel" error, the solution is as follows:

```
pkg upgrade
pkg install build-essential python
CFLAGS="-Wno-incompatible-function-pointer-types" pip install ruamel.yaml.clib
```
