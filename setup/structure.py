import os
import json
import re
from typing import Optional
from plumbum import local

##
# Utilities related to the directory structure of the repository
##


# Constants
# Assumes that "." resolves to the directory of the analysis notebook
COMPARATORS_PATH = os.path.abspath(os.path.join(".", "comparators"))
DATA_ROOT = os.path.abspath(os.path.join(".", "data"))
# The root of all the data related to the local builds
BUILDS_ROOT = os.path.join(DATA_ROOT, "build")
# CB: Current Build
CB_APKS_PATH = os.path.join(BUILDS_ROOT, "apks")
CB_SPLITS_PATH = os.path.join(CB_APKS_PATH, "splits")
TARS_ROOT = os.path.join(BUILDS_ROOT, "tars")
CB_PATH = os.path.join(BUILDS_ROOT, "Signal-Android")
# local builds with a functional whitness (dfstest), have a differing directory structure that we normalise while extracting
REPRODUCIBLE_TESTS_ROOT = os.path.join(BUILDS_ROOT, "reproducible-tests")
# part of the dfstest directory structure
DFS_ROOT_PATH = os.path.join(REPRODUCIBLE_TESTS_ROOT, "disorderfs_root")
CB_AAB_PATH = os.path.join(
    CB_PATH,
    "app",
    "build",
    "outputs",
    "bundle",
    "playProdRelease",
    "Signal-Android-play-prod-release.aab",
)
PLAYSTORE_APKS_ROOT = os.path.join(DATA_ROOT, "playstore-mirror")
PLAYSTORE_UNIVERSAL_UNZIP_PATH = os.path.join(DATA_ROOT, "playstore-universal-unzipped")
BUNDLETOOL_EXE = os.path.join(".", "bundletool")
VERSION_CVC_FILE = os.path.join(".", "version_code_tag_mappings.json")
# Results after applying methods from analysis.asserts to the aggregated data
SUMMARY_ROOT = os.path.join(DATA_ROOT, "summary")
PLOT_ROOT = os.path.join(DATA_ROOT, "plots")


def _playstore_apk_path(cvc) -> str:
    return os.path.join(PLAYSTORE_APKS_ROOT, cvc)


def universal_apk_path(cvc, relative=False) -> str:
    path = os.path.join(
        _playstore_apk_path(cvc), f"org.thoughtcrime.securesms-{cvc}.apk"
    )
    if relative:
        # Assuming posix
        path = create_relpath(path)
    return path


_VERSION = "fixed_versions"
_PARAMS = "fixed_parameters"


def create_or_clear_summary_directory_for(testname, version=True, clear=True) -> None:
    """
    if !version we create/clear the by/param directry
    if !clear and the dir exists function does nothing
    """
    # Check main folder
    main_dir = os.path.join(SUMMARY_ROOT, testname)
    mkdir = local["mkdir"]
    if not os.path.exists(main_dir):
        mkdir[main_dir]()
    subdir = os.path.join(main_dir, _VERSION if version else _PARAMS)
    if os.path.exists(subdir):
        # Idempotence
        local["rm"]["-r", subdir]()
    mkdir["-p", subdir]()


def summary_path(testname, key) -> str:
    # Which dimension is fixed?
    fixed = _PARAMS if "without" in key or "alph" in key or "ctime" in key else _VERSION
    if fixed == _PARAMS:
        filename = f'{"_".join(key.split(" "))}.json'
    else:
        filename = f"{key}.json"
    p = os.path.join(SUMMARY_ROOT, testname, fixed, filename)
    # print(f"returning {p} for:\n{testname}, {key}, {tarfile}")
    return p


def turn_cvc_code_mapping_to_json() -> None:
    json_obj = {}
    with open(
        os.path.join(PLAYSTORE_APKS_ROOT, "versioncode-tags-mapping.txt"), "r"
    ) as f:
        lines = f.readlines()
        for line in lines:
            cvc = line.split(":")[0].strip()
            version = line.split(":")[-1].strip()
            json_obj[cvc] = version
            json_obj[version] = cvc
    with open(VERSION_CVC_FILE, "w") as f:
        f.writelines(json.dumps(json_obj))


def create_relpath(abspath) -> str:
    # git rev-parse --show-toplevel
    stdout = local["git"]["rev-parse", "--show-toplevel"]()
    # Assuming posix
    relpath = abspath.removeprefix(stdout.strip())
    return relpath[1:]


# filename: one of the runs in data/build/tars
def version_and_run_from_tar_filename(filename) -> tuple[Optional[str], Optional[str]]:
    """
    Parses the version and run of the run packed into the tarfile:
    (version, run)

    # PRE:
    Expects the version and run to be last in the filename in this order, separated by '_'
    if there is no run, it assumes 1
    Example: dfstest-Signal-android-ctime-sort_v1.2.3_05.tar.gz

    # POST:
    (None, None) if the tarfile is not in the expected format
    """
    # Define the regex pattern
    pattern = r"v(\d+\.\d+\.\d+)(?:_)?(\d+)?"
    # Search for the pattern in the filename
    match = re.search(pattern, filename)
    if match:
        version = match.group(1)
        run = match.group(2) if match.group(2) else "01"  # If no run number, return 01
        return version, run
    else:
        return (
            None,
            None,
        )  # Return None if no match is found (TODO: Should this throw an error instead?)


def parameters_from_tar_filename(
    tar_filename,
) -> tuple[str, int, bool, bool, Optional[bool], Optional[bool]]:
    """
    Returns the parameters that were fixed during the run packed into the tarfile:
    (version, run_nr, functional whitness present?, with disorderfs?, sorted by ctime? (or alphabetically), sort reversed?)

    # PRE:
    Expects the version and run to be last in the filename in this order, separated by '_'
    if there is no run, it assumes 1
    searches for the substrings: 'dfstest', 'ctime', and 'reversed'
    to determine the other parameters
    Example: dfstest-Signal-android-ctime-sort_v1.2.3_05.tar.gz

    # POST:
    (ctime or reverse) => dfs
    not dfs => ctime == None and reverse == None
    """
    dfstest = True if "dfstest" in tar_filename else False
    dfs = (
        True if dfstest or "ctime" in tar_filename or "alph" in tar_filename else False
    )
    if not dfs:
        ctime = None
        reverse = None
    else:
        ctime = True if "ctime" in tar_filename else False
        reverse = True if "reversed" in tar_filename else False
    (version, run) = version_and_run_from_tar_filename(tar_filename)
    assert version is not None
    run = run if run is not None else "01"
    return (version, int(run), dfstest, dfs, ctime, reverse)
