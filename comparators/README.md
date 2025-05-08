# Comparators

This directory contains standalone scripts for comparing Android-related files to help understand differences between variants of the same file.

## Scripts

- `apkscope.py` – High-level APK comparison wrapper using `diffoscope`, with support for file exclusion via `apkdiff.py`.
- `arsc_compare.py` – Compares `.arsc` resource files, including checks for `res1` differences.
- `axml_compare.py` – Compares Android binary XML (AXML) files, such as `AndroidManifest.xml` and resource XMLs.
- `dex_compare.py` – Compares two `.dex` files.
- `dexset_compare.py` – Compares directories containing sets of `.dex` files (e.g., for multi-dex APKs).

## Usage

Each script is executable and can be run directly from the command line:

```bash
./dex_compare.py file1.dex file2.dex
```

Check each script’s -h flag for usage details and supported options.

## Dependencies

These scripts are mostly standalone but require:

androguard>=4

For `apkscope.py`, a compatible apkdiff.py must be present in the project root

To fetch a matching version of apkdiff.py for the codebase under test:

```bash
./scripts/03_get_apkdiff --version [tag]
```

## Notes

Output stability is not guaranteed at this time. Some scripts support JSON-formatted output, but this varies. Refer to each script’s help message for available formats and options.
