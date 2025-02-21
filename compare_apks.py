#!/usr/bin/env python3
# Chrissy's hacky script for initial analysis, reads from "data" folder
import os
from plumbum import local

def apk_filepath(bundle_filepath, apk_name):
    partial = bundle_filepath.split("/")
    del partial[-1]
    return os.path.join("/", *partial, "apks", "splits", apk_name)

def get_folder_run_from_apk_filepath(path):
    partial = path.split("/")
    if "dfs_no_sort" in path: # TODO: Hacky
        return f"{partial[-3]}_{partial[-2]}"
    else:
        return partial[-3]



def run_apkdiff(path1, path2):
    # for this quick and dirty test we simply used the copied apkdiff instead of fetching it every time
    python = local["python"]
    (rc, stdout, stderr) = python["./apkdiff.py", path1, path2].run(retcode=(0, 1))
    # if path1 == path2:
    #    print(f"For {path1}\n{rc}\n{stdout}\n{stderr}")
    return rc == 0


DIRECTORIES_OF_INTEREST = ["local_builds_mudkip", "Aditz", "Andrea", "device"]

INCLUDE_ALL_RUNS = ["bare", "dfs_no_sort"]
APKS_OF_INTEREST = ["base-master.apk", "base-arm64_v8a.apk", "base-xxhdpi.apk"]

unique_bundle_filepaths = []

for path, _, files in os.walk(os.getcwd()):
    if any(d in path for d in DIRECTORIES_OF_INTEREST):
        for f in files:
            if "bundle_shasum_256" in f:
                filepath = os.path.join(path, f)
                if any(dir in path for dir in INCLUDE_ALL_RUNS):
                    unique_bundle_filepaths.append(filepath)
                elif "01" in path:
                    unique_bundle_filepaths.append(filepath)

# TODO: Hacky
unique_bundle_filepaths.append("data/device")
# print(unique_bundle_filepaths)

def from_different_machines(path1, path2) -> bool:
    for s in DIRECTORIES_OF_INTEREST:
        if s in path1:
            source = s
    return source not in path2


results = []
for apk in APKS_OF_INTEREST:
    print(f"\n{apk} matched: ")
    for i in range(0, int(len(unique_bundle_filepaths))):
        for j in range(0, i):
            if i != j:
                path1 = apk_filepath(unique_bundle_filepaths[i], apk)
                path2 = apk_filepath(unique_bundle_filepaths[j], apk)
                result = run_apkdiff(
                    path1,
                    path2,
                )
                # print(i, j, f" :{result}")
                results.append(result)
                if result and from_different_machines(path1, path2):
                    ### Spit out any result that matched in a readable form
                    print(
                        f"{get_folder_run_from_apk_filepath(unique_bundle_filepaths[i])} - {get_folder_run_from_apk_filepath(unique_bundle_filepaths[j])}"
                    )
