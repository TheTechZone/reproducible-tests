import json
import re
import subprocess
import shutil
from pathlib import Path
from typing import Optional

##
# Utilities related to the directory structure of the repository
##


def get_git_root() -> Path:
    """
    Returns the absolute path to the root of the Git repository.
    """
    try:
        root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], text=True
        ).strip()
        return Path(root).resolve()
    except subprocess.CalledProcessError:
        raise RuntimeError("Not inside a Git repository.")


# Constants
# Assumes that "." resolves to the directory of the analysis notebook
ROOT = get_git_root()

COMPARATORS_PATH = ROOT / "comparators"
DATA_ROOT = ROOT / "data"

# The root of all the data related to the local builds
BUILDS_ROOT = DATA_ROOT / "build"
# CB: Current Build
CB_APKS_PATH = BUILDS_ROOT / "apks"
CB_SPLITS_PATH = CB_APKS_PATH / "splits"
TARS_ROOT = BUILDS_ROOT / "tars"
CB_PATH = BUILDS_ROOT / "Signal-Android"
# local builds with a functional whitness (dfstest), have a differing directory structure that we normalise while extracting
REPRODUCIBLE_TESTS_ROOT = BUILDS_ROOT / "reproducible-tests"
# part of the dfstest directory structure
DFS_ROOT_PATH = REPRODUCIBLE_TESTS_ROOT / "disorderfs_root"
CB_AAB_PATH = (
    CB_PATH
    / "app"
    / "build"
    / "outputs"
    / "bundle"
    / "playProdRelease"
    / "Signal-Android-play-prod-release.aab"
)

PLAYSTORE_APKS_ROOT = DATA_ROOT / "playstore-mirror"
PLAYSTORE_UNIVERSAL_UNZIP_PATH = DATA_ROOT / "playstore-universal-unzipped"
BUNDLETOOL_EXE = ROOT / "bundletool"
VERSION_CVC_FILE = ROOT / "version_code_tag_mappings.json"
# Results after applying methods from analysis.asserts to the aggregated data
SUMMARY_ROOT = DATA_ROOT / "summary"
PLOT_ROOT = DATA_ROOT / "plots"


def _playstore_apk_path(cvc) -> str:
    return PLAYSTORE_APKS_ROOT / cvc


def universal_apk_path(cvc, relative=False) -> str:
    path = Path(_playstore_apk_path(cvc)) / f"org.thoughtcrime.securesms-{cvc}.apk"
    if relative:
        # Assuming posix
        path = create_relpath(path)
    return str(path)


_VERSION = "fixed_versions"
_PARAMS = "fixed_parameters"


def create_or_clear_summary_directory_for(testname, version=True, clear=True) -> None:
    """
    if !version we create/clear the by/param directry
    if !clear and the dir exists function does nothing
    """
    # Check main folder
    main_dir = SUMMARY_ROOT / testname
    subdir = main_dir / (_VERSION if version else _PARAMS)

    # Create main directory if it doesn't exist
    main_dir.mkdir(parents=True, exist_ok=True)

    if subdir.exists():
        if clear:
            shutil.rmtree(subdir)
        else:
            return

    subdir.mkdir(parents=True, exist_ok=True)


def summary_path(testname, key) -> str:
    # Which dimension is fixed?
    fixed = (
        _PARAMS
        if any(word in key for word in ("without", "alph", "ctime"))
        else _VERSION
    )

    # Format filename
    filename = f'{"_".join(key.split(" "))}.json' if fixed == _PARAMS else f"{key}.json"

    path = SUMMARY_ROOT / testname / fixed / filename
    return str(path)


def turn_cvc_code_mapping_to_json() -> None:
    """
    Reads a colon-separated version code mapping file and converts it to a JSON format.

    Each line in the source file is expected to be in the format:
        <version_code>: <version_name>

    Both directions (code → name, and name → code) are stored in the resulting JSON.

    Output is written to VERSION_CVC_FILE.
    """
    json_obj = {}

    mapping_file = PLAYSTORE_APKS_ROOT / "versioncode-tags-mapping.txt"

    with mapping_file.open("r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(":")
            if len(parts) != 2:
                continue  # skip malformed lines
            cvc, version = parts[0].strip(), parts[1].strip()
            json_obj[cvc] = version
            json_obj[version] = cvc

    with VERSION_CVC_FILE.open("w", encoding="utf-8") as f:
        json.dump(json_obj, f, indent=2)


def create_relpath(abspath) -> str:
    git_root = ROOT.resolve()
    abspath = Path(abspath).resolve()
    return str(abspath.relative_to(git_root))


# filename: one of the runs in data/build/tars
def version_and_run_from_tar_filename(filename) -> tuple[Optional[str], Optional[int]]:
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
    match = re.search(pattern, str(filename))
    if match:
        version = match.group(1)
        run = match.group(2) if match.group(2) else "01"  # If no run number, return 01
        return version, int(run)
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
