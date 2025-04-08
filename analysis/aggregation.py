import os
import json
from plumbum import local
from collections import defaultdict
from setup.structure import (
    COMPARATORS_PATH,
    BUILDS_ROOT,
    BUNDLETOOL_EXE,
    DATA_ROOT,
    DFS_ROOT_PATH,
    CURRENT_BUILD_PATH,
    CB_AAB_PATH,
    CB_APKS_PATH,
    CB_SPLITS_PATH,
    PLAYSTORE_APKS_ROOT,
    PLAYSTORE_UNIVERSAL_UNZIP_PATH,
    REPRODUCIBLE_TESTS_ROOT,
    TARS_ROOT,
    VERSION_CVC_FILE,
)
from setup.structure import universal_apk_path, create_relpath, extract_parameters


# TODO: fill out with all the apks you want to compare, mapping from local -> playstore
APK_PLAYSTORE_PREFIX = "org.thoughtcrime.securesms-"
# Note that {cvc}.apk must still be appended to the values to get the complete filepath
APK_COMPARE_MAP = {
    "base-arm64_v8a.apk": f"{APK_PLAYSTORE_PREFIX}config.arm64_v8a-",
    "base-xxhdpi.apk": f"{APK_PLAYSTORE_PREFIX}config.xxhdpi-",
    "base-master.apk": f"{APK_PLAYSTORE_PREFIX}",
}


def get_version(cvc):
    with open(VERSION_CVC_FILE, "r") as f:
        v_c = json.loads(f.read())
    return v_c[cvc]


def get_cvc(version):
    if version[0] == "v":
        version = version[1:]
    with open(VERSION_CVC_FILE, "r") as f:
        v_c = json.loads(f.read())
    return v_c[version]


# if dfs_test=True correct folder structure to root at Signal-Android and not dfs_root, ignoring test
def extract(filepath, dfs_test):
    cwd = os.getcwd()
    tar = local["tar"]
    os.chdir(BUILDS_ROOT)
    _clear_untared_folder()
    print(f"Extracting {filepath} ...")
    tar["-xzf", filepath]()
    if dfs_test:
        print("Normalising dfs-test hierarchy...")
        mv = local["mv"]
        mv[os.path.join(DFS_ROOT_PATH, "Signal-Android"), CURRENT_BUILD_PATH]()
        local["rm"]["-r", REPRODUCIBLE_TESTS_ROOT]()
    os.chdir(cwd)
    _extract_apks()


# simply recursively clears the directory
def _clear_untared_folder():
    if os.path.exists(CURRENT_BUILD_PATH):
        print("Clearing current build...")
        rm = local["rm"]
        rm["-r", CURRENT_BUILD_PATH]()


def _extract_apks():
    bundletool = local[BUNDLETOOL_EXE]
    if not os.path.exists(CB_AAB_PATH):
        print(f"{CB_AAB_PATH} \ndoes not exist!!")
        exit(1)
    cwd = os.getcwd()
    if not os.path.exists(CB_SPLITS_PATH):
        local["mkdir"]["-p", CB_SPLITS_PATH]()
    else:
        _clear_current_apks()
    os.chdir(BUILDS_ROOT)
    print("Extracting APKs from bundle...")
    bundletool[
        "build-apks",
        f"--bundle={CB_AAB_PATH}",
        "--output-format=DIRECTORY",
        "--output=apks",
    ]()
    os.chdir(cwd)


def _clear_current_apks():
    print("Clearing APKs from previous run...")
    local["rm"]["-r", CB_APKS_PATH]()
    local["mkdir"][CB_APKS_PATH]()


def clear():
    _clear_untared_folder()
    _clear_current_apks()


def current_cvc():
    build_gradle_kts_path = os.path.join(CURRENT_BUILD_PATH, "app", "build.gradle.kts")
    version_code_line = "val canonicalVersionCode ="
    get_version_code = (
        local["cat"][build_gradle_kts_path] | local["grep"][version_code_line]
    )
    stdout = get_version_code()
    return f"{stdout.split(version_code_line)[-1].strip()}00"


# Only look at universal
def _unzip_playstore_apk(cvc):
    print(f"Going to unzip {cvc}...")
    # Create the directory if necessary
    if os.path.exists(PLAYSTORE_UNIVERSAL_UNZIP_PATH):
        # Idempotence
        print(f"Clearing universal zip directory for {cvc}...")
        local["rm"]["-r", PLAYSTORE_UNIVERSAL_UNZIP_PATH]()
    local["mkdir"][PLAYSTORE_UNIVERSAL_UNZIP_PATH]()
    # TODO: Dedublicate code
    # Pull apk with git lfs
    print(f"Pulling {universal_apk_path(cvc, True)} with git lfs...")
    lfs = local["git"]["lfs", "pull", f"--include={universal_apk_path(cvc, True)}"]
    rt, stdout, stderr = lfs.run()
    # print(rt, stdout, stderr)
    local["unzip"]["-d", PLAYSTORE_UNIVERSAL_UNZIP_PATH, universal_apk_path(cvc)]()
    print(f"Successfully unzipped universal-{cvc}!")


def _update_aggregation_result(file, key, value, log=True):
    if log:
        print(f"Updating {file}...")
    filepath = os.path.join(DATA_ROOT, "res", file)
    with open(filepath, "r") as f:
        summary = json.loads(f.read())
    summary[key] = value
    with open(filepath, "w") as f:
        f.write(json.dumps(summary))


def create_dex_sets(cvc):
    print("Creating dex comparison sets...")
    # format {cvc:{differences:{}, playstore:{md5:classesX.dex}, local_build:{md5:classesX.dex}},...}
    cvc_d = {}
    # Playstore
    _unzip_playstore_apk(cvc)
    shasum = local["sha256sum"]
    current_dir = os.getcwd()
    os.chdir(PLAYSTORE_UNIVERSAL_UNZIP_PATH)
    playstore_univ = {}
    for file in os.listdir("."):
        if ".dex" in file:
            sha = shasum[file]().split(" ")[0].strip()
            playstore_univ[sha] = file
    cvc_d["playstore"] = playstore_univ
    # Current Build
    root_rel_dexpath = os.path.join(
        CURRENT_BUILD_PATH,
        "app",
        "build",
        "intermediates",
        "dex",
        "playProdRelease",
        "minifyPlayProdReleaseWithR8",
    )
    os.chdir(current_dir)
    os.chdir(root_rel_dexpath)
    local_build = {}
    for file in os.listdir("."):
        if ".dex" in file:
            sha = shasum[file]().split(" ")[0].strip()
            local_build[sha] = file
    cvc_d["local"] = local_build
    # Create the symmetric difference between the shasets
    symmetric_difference = set(playstore_univ.keys()).symmetric_difference(
        set(local_build.keys())
    )
    sym_difference_map = {}
    for sha in symmetric_difference:
        if sha in playstore_univ.keys():
            sym_difference_map[sha] = f"playstore->{playstore_univ[sha]}"
        elif sha in local_build.keys():
            sym_difference_map[sha] = f"local->{local_build[sha]}"
    cvc_d["differing_dexes"] = sym_difference_map
    os.chdir(current_dir)
    return cvc_d


# Compares current base.apk with the coresponding playstore equivalent
def create_diffuse_record():
    print("Running diffuse on the master APK...")
    # TODO: clean up duplicate code
    cvc = current_cvc()
    playstore_apk_path = os.path.join(
        PLAYSTORE_APKS_ROOT,
        current_cvc(),
        f"{APK_COMPARE_MAP['base-master.apk']}{cvc}.apk",
    )
    # Pull the APK you want to compare with git-lfs
    local["git"]["lfs", "pull", "--include", playstore_apk_path]()
    # Diffuse
    sudo = local["sudo"]
    diffuse_res = sudo[
        local["tools/diffuse/bin/diffuse"][
            "diff", os.path.join(CB_SPLITS_PATH, "base-master.apk"), playstore_apk_path
        ]
    ]()
    return diffuse_res


# param: apk_compare -> which apk to compare according to key-value in APK_COMPARE_MAP
# apk_compare is the key to the dict, representing the part of the apk name without the prefixing: org.thoughtcrime.securesms-
# returns {apkdiff:{'match':<Boolean>, 'mismatched_files':[<filename>,...]}, diffuse:<string>}
# where APKdiff's "first" is the local build and "second" is the playstore APK
def create_apkdiff_record(local_apk_filename):
    cvc = current_cvc()
    # construct paths TODO: factor out, also used in create_diffuse_records, but meow meow was too tired so copy pasta
    local_apk_path = os.path.join(CB_SPLITS_PATH, local_apk_filename)
    playstore_apk_path = os.path.join(
        PLAYSTORE_APKS_ROOT, cvc, f"{APK_COMPARE_MAP[local_apk_filename]}{cvc}.apk"
    )
    # Pull the APK you want to compare with git-lfs
    local["git"]["lfs", "pull", "--include", create_relpath(playstore_apk_path)]()
    # APKdiff
    # clear out "mismatches" folder
    if os.path.isdir("mismatches"):
        # Idempotence
        local["rm"]["-r", "mismatches"]()
    else:
        print(f"Did not find a 'mismatches' folder in {os.getcwd()}")
    local["mkdir"]["mismatches"]()
    apkdiff_res = {}
    # APKdiff will return 1 if the match fails. We don't want plumbum to crash the script and accept all retcodes.
    (_, stdout, _) = local["python3"][
        "./apkdiff.py", local_apk_path, playstore_apk_path
    ].run(retcode=None)
    if "APKs don't match" in stdout:
        match = False
    else:
        match = True
    apkdiff_res["match"] = match
    mismatched_files = []
    if not match:
        for dirpath, _, filenames in os.walk("mismatches"):
            for filename in filenames:
                item = os.path.join(dirpath, filename)
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
def record_all_apkdiff_comparisons(tarfile_name):
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


def run_comparator_on_apkdiff_mismatches():
    mismatches_path = os.path.join("mismatches")
    result = defaultdict(dict)
    axml = local[os.path.join(COMPARATORS_PATH, "axml_compare.py")]
    arsc = local[os.path.join(COMPARATORS_PATH, "arsc_compare.py")]
    # local, playstore
    local_mismatches_dir = os.path.join(mismatches_path, "first")
    # call comparatinator
    for dirpath, _, filenames in os.walk(local_mismatches_dir):
        for filename in filenames:
            local_item = os.path.join(dirpath, filename)
            playstore_item = os.path.join(dirpath.replace("first", "second"), filename)
            if ".xml" in filename:
                (_, stdout, _) = axml[local_item, playstore_item].run()
                result["axml"][filename] = stdout
            if ".arsc" in filename:
                (retcode, stdout, _) = arsc[local_item, playstore_item].run()
                if retcode != 1:
                    result["arsc"][f"{filename}|local->playstore"] = stdout
                    (retcode, stdout, _) = arsc[playstore_item, local_item].run()
                    result["arsc"][f"{filename}|playstore->local"] = stdout
                else:
                    # Record two failures
                    result["arsc"][f"{filename}|local->playstore"] = "Failure"
                    result["arsc"][f"{filename}|playstore->local"] = "Failure"
    return result


def copy_navigation_jsons(tarfile_name):
    # create recursive folder structure
    root = os.path.join(DATA_ROOT, "res", "files")
    copy_dir = os.path.join(root, tarfile_name)
    mkdir = local["mkdir"]
    cp = local["cp"]
    if not os.path.exists(root):
        mkdir[root]()
    # idempotence
    if os.path.exists(copy_dir):
        print(f"Clearing {copy_dir}...")
        local["rm"]["-r", copy_dir]()
    mkdir["-p", copy_dir]()
    file_mappings_path = os.path.join(
        CURRENT_BUILD_PATH,
        "app/build/intermediates/incremental/generateSafeArgsPlayProdRelease/file_mappings.json",
    )
    navigation_path = os.path.join(
        CURRENT_BUILD_PATH,
        "app/build/intermediates/navigation_json/playProdRelease/extractDeepLinksPlayProdRelease/navigation.json",
    )
    cp[file_mappings_path, copy_dir]()
    cp[navigation_path, copy_dir]()
    print("Successfully saved file_mappings.json and navigation.json")


# grab output-metadata.json and the corresponding mtimes of the directory
# app/build/intermediates/processed_res/playProdRelease/processPlayProdReleaseResources/out
# ls -ltr --full-time
def extract_output_metadata(tarfile):
    print(
        f"Extracting contents of output-metadata.json and corresponding mtimes for {tarfile}..."
    )
    if "v7.28" in tarfile:
        directory_path = os.path.join(
            CURRENT_BUILD_PATH,
            "app/build/intermediates/processed_res/playProdRelease/processPlayProdReleaseResources/out",
        )
    else:
        directory_path = os.path.join(
            CURRENT_BUILD_PATH,
            "app/build/intermediates/linked_resources_binary_format/playProdRelease/processPlayProdReleaseResources",
        )
    timeinfo = local["ls"]["-ltr", "--full-time", directory_path]()
    filecontents = local["cat"][os.path.join(directory_path, "output-metadata.json")]()
    data = {"mtimes": timeinfo, "output-metadata.json": filecontents}
    _update_aggregation_result("output_metadata_mtimes.json", tarfile, data)


# Iterates through the data/tars folder and aggregates the results one run at a time
def aggregate_all_runs(
    dexsort=True, diffuse=True, apkdiff=True, nav=True, output_meta=True
):
    # Update lfs refs
    local["git"]["lfs", "checkout"]()
    for tarfile in os.listdir(TARS_ROOT):  # meep hard
        print(f"\nAnalysing {tarfile}...")
        tarpath = os.path.join(TARS_ROOT, tarfile)
        print(f"Pulling {create_relpath(tarpath)} with git lfs...")
        local["git"]["lfs", "pull", "--include", create_relpath(tarpath)]()
        # Extract run parameters from tarfile
        (_, _, dfstest, _, _, _) = extract_parameters(tarfile)
        # Extract the build to local folder
        print(f"Extracting {tarfile}...")
        extract(os.path.join(TARS_ROOT, tarfile), dfstest)
        id = tarfile
        if dexsort:  # Dex sort test
            dex_set = create_dex_sets(current_cvc())
            _update_aggregation_result("dex_sort.json", id, dex_set)
        if diffuse:  # diffuse
            diffuse_record = create_diffuse_record()
            _update_aggregation_result("diffuse.json", id, diffuse_record)
        if apkdiff:  # apkdiff
            record_all_apkdiff_comparisons(tarfile)
        if nav:
            copy_navigation_jsons(tarfile)
        if output_meta:
            extract_output_metadata(tarfile)
