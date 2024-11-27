# Reproducability test for signalapp/Signal-Android

The script attempts to automate Signal's reproducible-builds workflow. They only require a working installation of Python 3 (as they rely solely on the standard library).

## Setup

- (optional) Install bundletool (does NOT ship with adb):

```shell
./00_download_bundletool.py
```

- check dependencies (git, adb, docker and python should be already available on your system):

```shell
./01_check_dependencies.py
```

## Actual Reproducibility Test

Run `./build_signal.py`. The script is designed to output all intermediary steps

```shell
./build_signal.py
```

If this is not your first run, you can use `clean` to get in a good state.
