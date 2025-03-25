#!/usr/bin/env python3
import os
import json
import re
from plumbum import local

# Constants
# Assumes that "." resolves to the directory of the notebook
DATA_ROOT = os.path.abspath(os.path.join(".", "data"))
BUILDS_ROOT = os.path.join(DATA_ROOT, "build")
# CB: Current Build
CB_APKS_PATH = os.path.join(BUILDS_ROOT, "apks")
CB_SPLITS_PATH = os.path.join(CB_APKS_PATH, "splits")
TARS_ROOT = os.path.join(BUILDS_ROOT, "tars")
CURRENT_BUILD_PATH = os.path.join(BUILDS_ROOT, "Signal-Android")
REPRODUCIBLE_TESTS_ROOT = os.path.join(BUILDS_ROOT, "reproducible-tests")
DFS_ROOT_PATH = os.path.join(REPRODUCIBLE_TESTS_ROOT, "disorderfs_root")
CB_AAB_PATH = os.path.join(CURRENT_BUILD_PATH, "app", "build", "outputs", "bundle", "playProdRelease", "Signal-Android-play-prod-release.aab")
PLAYSTORE_APKS_ROOT = os.path.join(DATA_ROOT, "playstore-mirror")
PLAYSTORE_UNIVERSAL_UNZIP_PATH = os.path.join(DATA_ROOT, "playstore-universal-unzipped")
BUNDLETOOL_EXE = os.path.join(".", "bundletool")
VERSION_CVC_FILE = os.path.join(".", "version_code_tag_mappings.json")
#TODO: fill out with all the apks you want to compare, mapping from local -> playstore
APK_PLAYSTORE_PREFIX = "org.thoughtcrime.securesms-"
# Note that {cvc}.apk must still be appended to the values to get the complete filepath
APK_COMPARE_MAP = {
    "base-arm64_v8a.apk":f"{APK_PLAYSTORE_PREFIX}config.arm64_v8a-", 
    "base-xxhdpi.apk":f"{APK_PLAYSTORE_PREFIX}config.xxhdpi-",
    "base-master.apk":f"{APK_PLAYSTORE_PREFIX}"
}


def current_cvc():
    build_gradle_kts_path = os.path.join(CURRENT_BUILD_PATH, "app", "build.gradle.kts")
    version_code_line = "val canonicalVersionCode ="
    get_version_code = local["cat"][build_gradle_kts_path] | local["grep"][version_code_line]
    stdout = get_version_code()
    return f"{stdout.split(version_code_line)[-1].strip()}00" 


def _playstore_apk_path(cvc):
    return os.path.join(PLAYSTORE_APKS_ROOT, cvc)


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


def _universal_apk_path(cvc, relative=False):
    path = os.path.join(_playstore_apk_path(cvc), f"org.thoughtcrime.securesms-{cvc}.apk")
    if relative:
        # Assuming posix
        path = create_relpath(path)
        path = path[1:]
    return path


def create_relpath(abspath):
    # git rev-parse --show-toplevel
        stdout = local["git"]["rev-parse", "--show-toplevel"]()
        # Assuming posix
        relpath = abspath.removeprefix(stdout.strip())
        return relpath[1:]


# Only look at universal
def _unzip_playstore_apk(cvc):
    print(f"Going to unzip {cvc}...")
    # Create the directory if necessary
    if os.path.exists(PLAYSTORE_UNIVERSAL_UNZIP_PATH):
        # Idempotence
        print(f"Clearing universal zip directory for {cvc}...")
        local["rm"]["-r", PLAYSTORE_UNIVERSAL_UNZIP_PATH]()
    local["mkdir"][PLAYSTORE_UNIVERSAL_UNZIP_PATH]()
    #TODO: Dedublicate code
    # Pull apk with git lfs
    print(f"Pulling {_universal_apk_path(cvc, True)} with git lfs...")
    lfs = local["git"]["lfs", "pull", f"--include={_universal_apk_path(cvc, True)}"]
    rt, stdout, stderr = lfs.run()
    #print(rt, stdout, stderr)
    local["unzip"]["-d", PLAYSTORE_UNIVERSAL_UNZIP_PATH, _universal_apk_path(cvc)]()
    print(f"Successfully unzipped universal-{cvc}!")


def create_dex_sets(cvc):
    print("Creating dex comparison sets...")
    # format {cvc:{differences:{}, playstore_univ:{md5:classesX.dex}, local_build:{md5:classesX.dex}},...}
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
    cvc_d["playstore_univ"] = playstore_univ
    # Current Build
    root_rel_dexpath = os.path.join(CURRENT_BUILD_PATH, "app", "build", "intermediates", "dex", "playProdRelease", "minifyPlayProdReleaseWithR8")
    os.chdir(current_dir)
    os.chdir(root_rel_dexpath)
    local_build = {}
    for file in os.listdir("."):
        if ".dex" in file:
            sha = shasum[file]().split(" ")[0].strip()
            local_build[sha] = file
    cvc_d["local"] = local_build
    # Create the symmetric difference between the shasets
    symmetric_difference = set(playstore_univ.keys()).symmetric_difference(set(local_build.keys()))
    sym_difference_map = {}
    for sha in symmetric_difference:
        if sha in playstore_univ.keys():
            sym_difference_map[sha] = f"playstore->{playstore_univ[sha]}"
        elif sha in local_build.keys():
            sym_difference_map[sha] = f"local->{local_build[sha]}"
    cvc_d["differences"] = sym_difference_map
    os.chdir(current_dir)
    return cvc_d


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
        

def _clear_current_apks():
    print("Clearing APKs from previous run...")
    local["rm"]["-r", CB_APKS_PATH]()
    local["mkdir"][CB_APKS_PATH]()
    

def clear():
    _clear_untared_folder()
    _clear_current_apks()

# Compares current base.apk with the coresponding playstore equivalent
def create_diffuse_record():
    print("Running diffuse on the master APK...")
    # TODO: clean up duplicate code
    cvc = current_cvc()
    playstore_apk_path = os.path.join(PLAYSTORE_APKS_ROOT, current_cvc(), f"{APK_COMPARE_MAP['base-master.apk']}{cvc}.apk")
    # Pull the APK you want to compare with git-lfs
    local["git"]["lfs", "pull", "--include", playstore_apk_path]()
    # Diffuse
    diffuse_res = local["tools/diffuse/bin/diffuse"]["diff", os.path.join(CB_SPLITS_PATH, "base-master.apk"), playstore_apk_path]()
    return diffuse_res

# param: apk_compare -> which apk to compare according to key-value in APK_COMPARE_MAP
# apk_compare is the key to the dict, representing the part of the apk name without the prefixing: org.thoughtcrime.securesms-
# returns {apkdiff:{'match':<Boolean>, 'mismatched_files':[<filename>,...]}, diffuse:<string>}
# where APKdiff's "first" is the local build and "second" is the playstore APK
def create_apkdiff_record(local_apk_filename):
    cvc = current_cvc()
    # construct paths TODO: factor out, also used in create_diffuse_records, but meow meow was too tired so copy pasta
    local_apk_path = os.path.join(CB_SPLITS_PATH, local_apk_filename)
    playstore_apk_path = os.path.join(PLAYSTORE_APKS_ROOT, cvc, f"{APK_COMPARE_MAP[local_apk_filename]}{cvc}.apk")
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
    (_, stdout, _) = local["python3"]["./apkdiff.py", local_apk_path, playstore_apk_path].run(retcode=None)
    if "APKs don't match" in stdout:
        match = False
    else:
        match = True
    apkdiff_res["match"] = match
    mismatched_files = []
    if not match:
        for (dirpath, _, filenames) in os.walk("mismatches"):
            for filename in filenames:
                mismatched_files.append(os.path.join(dirpath, filename))
    apkdiff_res["mismatched_files"] = mismatched_files
    return apkdiff_res


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
    bundletool["build-apks", f"--bundle={CB_AAB_PATH}", "--output-format=DIRECTORY", "--output=apks"]()
    os.chdir(cwd)


def _turn_cvc_code_mapping_to_json():
    json_obj = {}
    with open(os.path.join(PLAYSTORE_APKS_ROOT, "versioncode-tags-mapping.txt"), "r") as f:
        lines = f.readlines()
        for line in lines:
            cvc = line.split(":")[0].strip()
            version = line.split(":")[-1].strip()
            json_obj[cvc] = version
            json_obj[version] = cvc 
    with open(VERSION_CVC_FILE, "w") as f:
        f.writelines(json.dumps(json_obj))


# filename: one of the runs in data/build/tars
def _extract_version_and_run(filename):
    # Define the regex pattern
    pattern = r'v(\d+\.\d+\.\d+)(?:_(\d+))?'
    # Search for the pattern in the filename
    match = re.search(pattern, filename)
    if match:
        version = match.group(1)
        run = match.group(2) if match.group(2) else None  # If no run number, return None
        return version, run
    else:
        return None, None  # Return None if no match is found


# TODO: work on these names meow :)
# TODO: document what you're returning
def extract_structure(tar_filename):
    dfstest = True if "dfstest" in tar_filename else False
    dfs = True if dfstest or "ctime" in tar_filename or "alph" in tar_filename else False
    if not dfs:
        ctime = None
        reverse = None
    else:
        ctime = True if "ctime" in tar_filename else False
        reverse = True if "reversed" in tar_filename else False
    (version, run) = _extract_version_and_run(tar_filename)
    assert(version is not None)
    run = run if run is not None else "01"
    return (version, run , dfstest, dfs, ctime, reverse)
    

# meow work on those names :)
def create_nested_dict_structure_from_run_parameters(dfs, ctime, reverse, apk, run, rec):
    if not dfs:
        data = {"vanilla":
                    {run: rec if apk is None else {apk:rec}}
        }
    else:
        data = {"dfs": 
                    {"ctime" if ctime else "alph": 
                        {"reversed" if reverse else "sort":
                            {run: rec if apk is None else {apk:rec}}
                        }
                    }
        }
    return data


# Runs comparisons and updates diftools summary with
# apkdiff result
# and diffoscope results
# for each pairwise apks in APK_COMPARE_MAP
# PRE: local apks must already be extracted
def record_all_apkdiff_comparisons(tar_filename, version, run, dfs, ctime, reverse):
    print("Running apkdiff on all pairs in APK_COMPARE_MAP...") 
    for apk in APK_COMPARE_MAP.keys():
        rec = create_apkdiff_record(apk)
        data = create_nested_dict_structure_from_run_parameters(dfs, ctime, reverse, apk, run, rec)
        _update_result_summary("apkdiff.json", version, data, log=False)
    print("Updated apkdiff.json!")


def _update_result_summary(file, key, value, log=True):
    if log:
        print(f"Updating {file}...")
    filepath = os.path.join(DATA_ROOT, "res", file)
    with open(filepath, "r") as f:
        summary = json.loads(f.read())
    summary[key] = value
    with open(filepath, "w") as f:
        f.write(json.dumps(summary))


# Iterates through the data/tars folder and aggregates the results one run at a time
def analyse_all_runs():
    # Update lfs refs
    local["git"]["lfs", "checkout"]()
    for tarfile in os.listdir(TARS_ROOT):# meep hard 
        print(f"Analysing {tarfile}...")
        tarpath = os.path.join(TARS_ROOT, tarfile)
        print(f"Pulling {create_relpath(tarpath)} with git lfs...")
        local["git"]["lfs", "pull","--include", create_relpath(tarpath)]()
        # Extract run parameters from tarfile
        (version, run , dfstest, dfs, ctime, reverse) = extract_structure(tarfile)
        # Extract the build to local folder
        print(f"Extracting {tarfile}...")
        extract(os.path.join(TARS_ROOT, tarfile), dfstest)
        # Dex sort test
        dex_set = create_dex_sets(current_cvc())
        dex_data = create_nested_dict_structure_from_run_parameters(dfs, ctime, reverse, None, run, dex_set)
        _update_result_summary("dex_sort.json", version, dex_data)
        # diffuse
        diffuse_record = create_diffuse_record()
        diffuse_data = create_nested_dict_structure_from_run_parameters(dfs, ctime, reverse, None, run, diffuse_record)
        _update_result_summary("diffuse.json", version, diffuse_data)
        # apkdiff
        record_all_apkdiff_comparisons(tarfile, version, run, dfs, ctime, reverse)


# Test
cwd = os.getcwd()
try:
    #clear()
    #extract(os.path.join(TARS_ROOT, "signal-android_v7.30.2.tar.gz"))
    #_extract_apks()
    #unzip_playstore_apk("151400")
    
    #_turn_cvc_code_mapping_to_json()
    #print("Done!")
    #d = create_dex_sets("151400")
    #print(d)
    #print(d["local"])
    #print(json.dumps(create_difftool_records("base-master.apk"), indent=4))
    #extract(os.path.join(TARS_ROOT, "dfstest-signal-android-ctime-reversed_v7.28.4_01.tar.gz"), True)
    analyse_all_runs()
    pass
except Exception as e:
    print(e)
    os.chdir(cwd)
os.chdir(cwd)


# In[ ]:





# ## Meep

# 
