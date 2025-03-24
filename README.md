# Reproducability test for signalapp/Signal-Android

The script attempts to automate Signal's reproducible-builds workflow. They only require a working installation of Python 3 (as they rely solely on the standard library).

## Setup

- (optional) Install bundletool (does NOT ship with adb):

```shell
./00_download_bundletool.py # --version
```

- check dependencies (git, adb, docker, gcc, make and python should be already available on your system):

```shell
./01_check_dependencies.py
```

- install disorderfs and associated libs to fix the overlay filesystem on which the build will be executed 
```shell
./02_install_disorderfs.py
```

- for manual testing, it is useful to have a copy of apkdiff that matches the version you're trying to reproduce

```shell
./03_get_apkdiff.py # --version
```

## Actual Reproducibility Test

Run `./build_signal.py`. The script is designed to output all intermediary steps

```shell
./build_signal.py --version
```

The scripts execution can be modified by named arguments. For example, if you want to run the build on a disorderfs overlay and fix a specific version without connecting a phone:

```shell
./build_signal.py --version v7.28.4 --dfs ctime_sort
```

Run help (-h) for a list of all options.

If this is not your first run, you can use `clean` to get in a good state.
