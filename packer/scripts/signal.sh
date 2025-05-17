#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

# SIGNAL_VERSION="7.41.3"
SIGNAL_VERSION="7.36.0"

SIGNAL_VERSION_V="v${SIGNAL_VERSION}"

# Create the directory in /signal and set ownership
sudo mkdir -p /signal
sudo chown $USER:$USER /signal

# Clone the repository directly into /signal
export GIT_LFS_SKIP_SMUDGE=1
git clone --filter=blob:none https://github.com/thetechzone/reproducible-tests -b writeup /signal/reproducible-tests

# Install necessary dependencies for Python 3.12 and venv setup
sudo apt install -yqq python3.12-venv unzip  # todo: move to packer

# Set up the virtual environment in /signal/reproducible-tests
python3 -m venv /signal/reproducible-tests/.venv

# Install the dependencies inside the virtual environment
/signal/reproducible-tests/.venv/bin/pip install -r /signal/reproducible-tests/requirements-jupyter.txt

# Execute the scripts using the virtual environment Python interpreter
/signal/reproducible-tests/.venv/bin/python /signal/reproducible-tests/scripts/00_download_bundletool.py
/signal/reproducible-tests/.venv/bin/python /signal/reproducible-tests/scripts/01_check_dependencies.py || true
cd /signal/reproducible-tests/ && /signal/reproducible-tests/.venv/bin/python /signal/reproducible-tests/scripts/02_install_disorderfs.py
/signal/reproducible-tests/.venv/bin/python /signal/reproducible-tests/scripts/03_get_apkdiff.py --version "$SIGNAL_VERSION_V"
/signal/reproducible-tests/.venv/bin/python /signal/reproducible-tests/scripts/03_get_diffuse.py

# Build signal with the specified version (use absolute path for the build signal)
#cd /signal/reproducible-tests/ && .venv/bin/python ./build_signal.py --version "$SIGNAL_VERSION" --dfs sort --aab-only
cd /signal/reproducible-tests/ && .venv/bin/python ./build_signal.py --version "$SIGNAL_VERSION" --dfs ctime_sort --aab-only


echo "### DONE BUILDING. Preparing output ###"

mkdir -p /signal/reproducible-tests/results
cp /signal/reproducible-tests/reproducible-signal/apks-i-built/bundle.aab /signal/reproducible-tests/results/bundle.aab
cp -r /signal/reproducible-tests/disorderfs_root/test/ /signal/reproducible-tests/results/withness
cp -r  /signal/reproducible-tests/disorderfs_root/Signal-Android/app/build /signal/reproducible-tests/results/build 

echo "Results is read. Need to SCP it back to host."