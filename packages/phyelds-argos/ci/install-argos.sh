#!/usr/bin/env bash
# Build a reproducible, user-local ARGoS for CI. Dependencies are installed by the job.
set -euo pipefail
build_root=${1:?usage: install-argos.sh BUILD_ROOT PREFIX [FORCE_NO_QT=ON]}
prefix=${2:?missing install prefix}
no_qt=${3:-ON}
git clone --quiet https://github.com/ilpincy/argos3.git "$build_root/source"
git -C "$build_root/source" checkout --quiet --detach 1d5ca3389e1066a1ae8ab0e4c54cc3bc7f85a339
cmake -S "$build_root/source/src" -B "$build_root/build" \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$prefix" \
    -DARGOS_DOCUMENTATION=OFF -DARGOS_INSTALL_LDSOCONF=OFF -DARGOS_FORCE_NO_QTOPENGL="$no_qt"
cmake --build "$build_root/build" --parallel 2
cmake --install "$build_root/build"
