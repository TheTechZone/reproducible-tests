import os
from pathlib import Path
import json
from typing import Optional
from plumbum import local  # type: ignore
from collections import defaultdict
from setup.structure import (
    COMPARATORS_PATH,
    BUILDS_ROOT,
    BUNDLETOOL_EXE,
    DATA_ROOT,
    DFS_ROOT_PATH,
    CB_PATH,
    CB_AAB_PATH,
    CB_APKS_PATH,
    CB_SPLITS_PATH,
    PLAYSTORE_APKS_ROOT,
    PLAYSTORE_UNIVERSAL_UNZIP_PATH,
    REPRODUCIBLE_TESTS_ROOT,
    TARS_ROOT,
    VERSION_CVC_FILE,
)
from setup.structure import (
    universal_apk_path,
    create_relpath,
    parameters_from_tar_filename,
)


# TODO: fill out with all the apks you want to compare, mapping from local -> playstore
APK_PLAYSTORE_PREFIX = "org.thoughtcrime.securesms-"
# Note that {cvc}.apk must still be appended to the values to get the complete filepath
APK_COMPARE_MAP = {
    "base-arm64_v8a.apk": f"{APK_PLAYSTORE_PREFIX}config.arm64_v8a-",
    "base-xxhdpi.apk": f"{APK_PLAYSTORE_PREFIX}config.xxhdpi-",
    "base-master.apk": f"{APK_PLAYSTORE_PREFIX}",
}


def get_version(cvc: str) -> Optional[str]:
    """
    Get the human readable, sematic version for a version code
    """
    with open(VERSION_CVC_FILE, "r") as f:
        v_c = json.loads(f.read())
    return v_c.get(cvc, None)


def get_cvc(version: str) -> Optional[str]:
    """
    Get the cannocial version code for a known semantic version (git tag)
    """
    if version[0] == "v":
        version = version[1:]
    with open(VERSION_CVC_FILE, "r") as f:
        v_c = json.loads(f.read())
    return v_c.get(version, None)


def extract(filepath: str, dfs_test: bool) -> None:
    """
    if `dfs_test=True` correct folder structure to root at Signal-Android and not dfs_root, ignoring test
    """
    cwd = Path.cwd()  # Get the current working directory using pathlib
    tar = local["tar"]
    os.chdir(str(BUILDS_ROOT))  # Convert Path to string for os.chdir
    _clear_untared_folder()

    print(f"Extracting {filepath} ...")
    tar["-xzf", filepath]()
    if dfs_test:
        print("Normalising dfs-test hierarchy...")
        mv = local["mv"]
        mv[str(DFS_ROOT_PATH / "Signal-Android"), str(CB_PATH)]()
        local["rm"]["-r", str(REPRODUCIBLE_TESTS_ROOT)]()

    os.chdir(str(cwd))
    _extract_apks()


def _clear_untared_folder() -> None:
    """
    recursively clears the codabase directory
    """
    if CB_PATH.exists():
        print("Clearing current build...")
        rm = local["rm"]
        rm["-r", str(CB_PATH)]()
    else:
        print(f"Path {CB_PATH} does not exist. Skipping...")


def _extract_apks() -> None:
    bundletool = local[str(BUNDLETOOL_EXE)]
    if not CB_AAB_PATH.exists():
        print(f"{CB_AAB_PATH} \ndoes not exist!!")
        exit(1)

    cwd = Path.cwd()
    if not CB_SPLITS_PATH.exists():
        # local["mkdir"]["-p", CB_SPLITS_PATH]()
        CB_SPLITS_PATH.mkdir(
            parents=True
        )  # Create the splits directory if it doesn't exist
    else:
        _clear_current_apks()
    os.chdir(BUILDS_ROOT)
    print("Extracting APKs from bundle...")
    bundletool[
        "build-apks",
        f"--bundle={str(CB_AAB_PATH)}",
        "--output-format=DIRECTORY",
        "--output=apks",
    ]()
    os.chdir(cwd)


def _clear_current_apks() -> None:
    print("Clearing APKs from previous run...")
    local["rm"]["-r", CB_APKS_PATH]()
    local["mkdir"][CB_APKS_PATH]()


def clear() -> None:
    _clear_untared_folder()
    _clear_current_apks()


def current_cvc() -> str:
    """
    Get the canonical version code from the build.gradle.kts file.
    """
    build_gradle_kts_path = Path(CB_PATH) / "app" / "build.gradle.kts"
    version_code_line = "val canonicalVersionCode ="

    get_version_code = (
        local["cat"][str(build_gradle_kts_path)] | local["grep"][version_code_line]
    )

    stdout = get_version_code()
    canonical_version_code = f"{stdout.split(version_code_line)[-1].strip()}00"  # Assuming hotfix version is 0

    # Extract the current hotfix version and format it as a 2-digit string
    hotfix_version_line = "val currentHotfixVersion ="
    get_hotfix_version = (
        local["cat"][str(build_gradle_kts_path)] | local["grep"][hotfix_version_line]
    )
    stdout = get_hotfix_version()
    hotfix_version = stdout.split(hotfix_version_line)[-1].strip()
    current_hotfix_version = f"{int(hotfix_version):02d}" if hotfix_version else "00"

    # Assumes hotfix version is 0
    return f"{canonical_version_code}{current_hotfix_version}"


# Only look at universal
def _unzip_playstore_apk(cvc: str) -> None:
    print(f"Going to unzip {cvc}...")

    # Use pathlib to define the paths
    unzip_path = PLAYSTORE_UNIVERSAL_UNZIP_PATH
    universal_apk = universal_apk_path(cvc)

    # Create the directory if necessary
    if unzip_path.exists():
        # Idempotence: Clearing the unzip directory for the given cvc
        print(f"Clearing universal zip directory for {cvc}...")
        local["rm"]["-r", str(unzip_path)]()

    unzip_path.mkdir(parents=True, exist_ok=True)

    # TODO: Deduplicate code
    # Pull apk with git lfs
    print(f"Pulling {universal_apk} with git lfs...")
    lfs = local["git"]["lfs", "pull", f"--include={universal_apk}"]
    rt, stdout, stderr = lfs.run()

    # Unzip the file to the specified directory
    local["unzip"]["-d", str(unzip_path), str(universal_apk)]()

    print(f"Successfully unzipped universal-{cvc}!")


def _update_aggregation_result(file: str, key: str, value, log: bool = True) -> None:
    if log:
        print(f"Updating {file}...")

    # Use pathlib to construct the filepath
    filepath = Path(DATA_ROOT) / "res" / file
    # Read the current summary from the file
    with open(filepath, "r") as f:
        summary = json.load(f)
    # Update the summary with the new key-value pair
    summary[key] = value

    # Write the updated summary back to the file
    with open(filepath, "w") as f:
        json.dump(summary, f)


def create_dex_sets(cvc: str) -> dict:
    print("Creating dex comparison sets...")
    # format {cvc:{differences:{}, playstore:{md5:classesX.dex}, local_build:{md5:classesX.dex}},...}
    cvc_d = {}

    # Playstore
    _unzip_playstore_apk(cvc)
    shasum = local["sha256sum"]
    current_dir = Path.cwd()  # Get the current directory using pathlib
    playstore_univ = {}

    playstore_path = Path(
        PLAYSTORE_UNIVERSAL_UNZIP_PATH
    )  # Define the playstore path using pathlib
    os.chdir(playstore_path)

    for file in playstore_path.iterdir():
        if file.suffix == ".dex":  # Check if the file is a dex file
            sha = shasum[str(file)]().split(" ")[0].strip()
            playstore_univ[sha] = file.name  # Use file.name to get the file's name
    cvc_d["playstore"] = playstore_univ

    # Current Build
    root_rel_dexpath = (
        Path(CB_PATH)
        / "app"
        / "build"
        / "intermediates"
        / "dex"
        / "playProdRelease"
        / "minifyPlayProdReleaseWithR8"
    )
    os.chdir(current_dir)
    os.chdir(root_rel_dexpath)

    local_build = {}
    for file in root_rel_dexpath.iterdir():
        if file.suffix == ".dex":  # Check if the file is a dex file
            sha = shasum[str(file)]().split(" ")[0].strip()
            local_build[sha] = file.name  # Use file.name to get the file's name
    cvc_d["local"] = local_build

    # Create the symmetric difference between the sha sets
    symmetric_difference = set(playstore_univ.keys()).symmetric_difference(
        set(local_build.keys())
    )
    sym_difference_map = {}
    for sha in symmetric_difference:
        if sha in playstore_univ:
            sym_difference_map[sha] = f"playstore->{playstore_univ[sha]}"
        elif sha in local_build:
            sym_difference_map[sha] = f"local->{local_build[sha]}"
    cvc_d["differing_dexes"] = sym_difference_map

    os.chdir(current_dir)
    return cvc_d


def create_diffuse_record() -> Optional[str]:
    """
    Compares current base.apk with the corresponding playstore equivalent using `diffuse`_.

    .. _diffuse: https://github.com/JakeWharton/diffuse
    """
    print("Running diffuse on the base-master APK...")

    # Get the current version code (cvc)
    cvc = current_cvc()

    # Build the path to the playstore APK using pathlib
    playstore_apk_path = (
        Path(PLAYSTORE_APKS_ROOT)
        / cvc
        / f"{APK_COMPARE_MAP['base-master.apk']}{cvc}.apk"
    )

    # Pull the APK you want to compare with git-lfs
    local["git"]["lfs", "pull", "--include", str(playstore_apk_path)]()

    # Run the diffuse command using sudo
    sudo = local["sudo"]
    diffuse_res = sudo[
        local["tools/diffuse/bin/diffuse"][
            "diff",
            str(Path(CB_SPLITS_PATH) / "base-master.apk"),
            str(playstore_apk_path),
        ]
    ]()

    return diffuse_res


# param: apk_compare -> which apk to compare according to key-value in APK_COMPARE_MAP
# apk_compare is the key to the dict, representing the part of the apk name without the prefixing: org.thoughtcrime.securesms-
# returns {apkdiff:{'match':<Boolean>, 'mismatched_files':[<filename>,...]}, diffuse:<string>}
# where APKdiff's "first" is the local build and "second" is the playstore APK
def create_apkdiff_record(local_apk_filename: str) -> dict:
    cvc = current_cvc()

    # Construct paths using pathlib
    local_apk_path = Path(CB_SPLITS_PATH) / local_apk_filename
    playstore_apk_path = (
        Path(PLAYSTORE_APKS_ROOT)
        / cvc
        / f"{APK_COMPARE_MAP[local_apk_filename]}{cvc}.apk"
    )

    # Pull the APK you want to compare with git-lfs
    local["git"]["lfs", "pull", "--include", create_relpath(str(playstore_apk_path))]()

    # Clear out "mismatches" folder (Idempotent)
    mismatches_dir = Path("mismatches")
    if mismatches_dir.exists() and mismatches_dir.is_dir():
        local["rm"]["-r", str(mismatches_dir)]()
    else:
        print(f"Did not find a 'mismatches' folder in {os.getcwd()}")
    mismatches_dir.mkdir(parents=True, exist_ok=True)

    apkdiff_res: dict[str, str | list[str] | bool] = {}

    # APKdiff will return 1 if the match fails. We don't want plumbum to crash the script and accept all retcodes.
    (_, stdout, _) = local["python3"][
        "./apkdiff.py", str(local_apk_path), str(playstore_apk_path)
    ].run(retcode=None)

    # Determine if the APKs match
    match = "APKs don't match" not in stdout
    apkdiff_res["match"] = match

    mismatched_files = []

    if not match:
        for dirpath, _, filenames in os.walk(mismatches_dir):
            for filename in filenames:
                item = str(Path(dirpath) / filename)
                item = (
                    item.replace("first", "local")
                    if "first" in item
                    else item.replace("second", "playstore")
                )
                mismatched_files.append(item)

    apkdiff_res["mismatched_files"] = mismatched_files
    return apkdiff_res


# Runs comparisons and updates diftools summary with
# apkdiff result
# and diffoscope results
# for each pairwise apks in APK_COMPARE_MAP
# PRE: local apks must already be extracted
def record_all_apkdiff_comparisons(tarfile_name: str) -> None:
    print("Running apkdiff on all pairs in APK_COMPARE_MAP...")
    result = {}
    comparator_result = {}
    for apk in APK_COMPARE_MAP.keys():
        rec = create_apkdiff_record(apk)
        result[apk] = rec
        # Now apkdiff was run and we can call the comparators on interesting files
        comparator_rec = run_comparator_on_apkdiff_mismatches()
        comparator_result[apk] = comparator_rec
    _update_aggregation_result("apkdiff.json", tarfile_name, result, log=False)
    _update_aggregation_result(
        "apkdiff_comparators.json", tarfile_name, comparator_result, log=False
    )
    print("Updated apkdiff aggregations!")


def run_comparator_on_apkdiff_mismatches() -> dict:
    mismatches_path = Path("mismatches")
    result: dict = defaultdict(dict)

    # Use Path for comparators as well
    axml = local[str(COMPARATORS_PATH / "axml_compare.py")]
    arsc = local[str(COMPARATORS_PATH / "arsc_compare.py")]

    # local, playstore
    local_mismatches_dir = mismatches_path / "first"

    # Call comparators
    for local_item_path in local_mismatches_dir.rglob("*"):
        # Ensure only files are processed
        if local_item_path.is_file():
            playstore_item_path = (
                mismatches_path
                / "second"
                / local_item_path.relative_to(local_mismatches_dir)
            )

            if local_item_path.suffix == ".xml":
                (_, stdout, _) = axml[
                    str(local_item_path), str(playstore_item_path)
                ].run()
                result["axml"][local_item_path.name] = stdout

            elif local_item_path.suffix == ".arsc":
                # ARSC comparison for local->playstore
                retcode, stdout, _ = arsc[
                    str(local_item_path), str(playstore_item_path)
                ].run()
                if retcode != 1:
                    result["arsc"][f"{local_item_path.name}|local->playstore"] = stdout

                    # ARSC comparison for playstore->local
                    retcode, stdout, _ = arsc[
                        str(playstore_item_path), str(local_item_path)
                    ].run()
                    result["arsc"][f"{local_item_path.name}|playstore->local"] = stdout
                else:
                    # Record failure
                    result["arsc"][
                        f"{local_item_path.name}|local->playstore"
                    ] = "Failure"
                    result["arsc"][
                        f"{local_item_path.name}|playstore->local"
                    ] = "Failure"

    return result


def copy_navigation_jsons(tarfile_name: Path | str) -> None:
    # create recursive folder structure
    root = Path(DATA_ROOT) / "res" / "files"
    copy_dir = root / tarfile_name
    mkdir = local["mkdir"]
    cp = local["cp"]

    # Ensure the root directory exists
    if not root.exists():
        mkdir[str(root)]()

    # Idempotence: Remove and recreate the copy_dir if it already exists
    if copy_dir.exists():
        print(f"Clearing {copy_dir}...")
        local["rm"]["-r", str(copy_dir)]()

    mkdir["-p", str(copy_dir)]()

    file_mappings_path = (
        CB_PATH
        / "app"
        / "build"
        / "intermediates"
        / "incremental"
        / "generateSafeArgsPlayProdRelease"
        / "file_mappings.json"
    )
    navigation_path = (
        CB_PATH
        / "app"
        / "build"
        / "intermediates"
        / "navigation_json"
        / "playProdRelease"
        / "extractDeepLinksPlayProdRelease"
        / "navigation.json"
    )

    # Copy the files to the target directory
    cp[str(file_mappings_path), str(copy_dir)]()
    cp[str(navigation_path), str(copy_dir)]()

    print("Successfully saved file_mappings.json and navigation.json")


# grab output-metadata.json and the corresponding mtimes of the directory
# app/build/intermediates/processed_res/playProdRelease/processPlayProdReleaseResources/out
# ls -ltr --full-time
def extract_output_metadata(tarfile):
    print(
        f"Extracting contents of output-metadata.json and corresponding mtimes for {tarfile}..."
    )

    # Define the directory path based on the version
    if "v7.28" in tarfile:
        directory_path = (
            Path(CB_PATH)
            / "app"
            / "build"
            / "intermediates"
            / "processed_res"
            / "playProdRelease"
            / "processPlayProdReleaseResources"
            / "out"
        )
    else:
        directory_path = (
            Path(CB_PATH)
            / "app"
            / "build"
            / "intermediates"
            / "linked_resources_binary_format"
            / "playProdRelease"
            / "processPlayProdReleaseResources"
        )

    # Get the file modification times and contents
    timeinfo = local["ls"]["-ltr", "--full-time", str(directory_path)]()
    filecontents = local["cat"][str(directory_path / "output-metadata.json")]()

    # Prepare the data to update
    data = {"mtimes": timeinfo, "output-metadata.json": filecontents}

    # Update the aggregation result
    _update_aggregation_result("output_metadata_mtimes.json", tarfile, data)


def aggregate_all_runs(
    dexsort: bool = True,
    diffuse: bool = True,
    apkdiff: bool = True,
    nav: bool = True,
    output_meta: bool = True,
) -> None:
    """
    Iterates through the data/tars folder and aggregates the comparison results one run at a time

    Parameters:
        dexsort (bool): runs the dex file sort comparison and updates `dex_sort.json`.
        diffuse (bool): runs the diffuse analysis and updates `diffuse.json`.
        apkdiff (bool): performs APK diff comparisons.
        nav (bool): copies navigation-related JSON metadata for each run.
        output_meta (bool): extracts and stores general output metadata for each run.

    Side Effects:
        - Reads from and writes to disk (JSON files, extracted folders).
        - Interacts with Git LFS to fetch archived test data.
        - Prints status information to standard output.
    """
    # Update lfs refs
    local["git"]["lfs", "checkout"]()
    for tarfile in TARS_ROOT.iterdir():  # meep hard
        if tarfile.is_file():  # Ensure we only process files
            print(f"\nAnalysing {tarfile.name}...")
            relpath = create_relpath(tarfile)
            print(f"Pulling {relpath} with git lfs...")
            local["git"]["lfs", "pull", "--include", relpath]()
            # Extract run parameters from tarfile
            (_, _, dfstest, _, _, _) = parameters_from_tar_filename(tarfile)

            # Extract the build to the local folder
            print(f"Extracting {tarfile.name}...")
            extract(str(tarfile), dfstest)

            # Use the tarfile name as the ID
            tar_id = tarfile.name
            if dexsort:  # Dex sort test
                dex_set = create_dex_sets(current_cvc())
                _update_aggregation_result("dex_sort.json", tar_id, dex_set)
            if diffuse:  # diffuse
                diffuse_record = create_diffuse_record()
                _update_aggregation_result("diffuse.json", tar_id, diffuse_record)
            if apkdiff:  # apkdiff
                record_all_apkdiff_comparisons(tarfile.name)
            if nav:
                copy_navigation_jsons(tarfile)
            if output_meta:
                extract_output_metadata(tarfile)
