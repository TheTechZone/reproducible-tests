# Scripts

This directory contains various utility scripts designed to streamline project setup.

## Scripts Overview

- `00_download_bundletool.py` – Downloads `bundletool` from GitHub releases.
- `01_check_dependencies.py` – Checks the system for required dependencies (e.g., Python, Git, Docker, ADB, etc.).
- `02_install_disorderfs.py` – Installs `disorderfs` dependencies (via `dnf` package manager).
- `03_get_apkdiff.py` – Downloads `apkdiff.py` from the Signal-Android repository for APK comparison.
- `03_get_diffuse.py` – Downloads the `diffuse` tool for binary diffing.

## Usage

Each script is executable and can be run directly from the command line. To view the options for a script, use the `-h` flag.

Example:

```shell
./03_get_apkdiff.py --version v7.25.2
```

## Dependencies

These scripts require the following:

- Python 3.10+
- a Linux-based operating system, using apt or dnf for package management
- `plumbum` for process management

## Notes

Some scripts (e.g., 02_install_disorderfs.py) may require sudo privileges for installation steps.

If you need a specific version of bundletool, apkdiff.py or diffuse, use the --version flag to specify it.
