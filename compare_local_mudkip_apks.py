import os
from plumbum import local


def apk_filepath(bundle_filepath, apk_name):
    partial = bundle_filepath.split("/")
    del(partial[-1])
    return os.path.join("/", *partial, "apks", "splits", apk_name)


def get_folder_run_from_apk_filepath(path):
    partial = path.split("/")
    return f"{partial[-3]}_{partial[-2]}"


def run_apkdiff(path1, path2):
    # for this quick and dirty test we simply used the copied apkdiff instead of fetching it every time
    python = local["python"]
    (rc, stdout, stderr) = python["./apkdiff.py", path1, path2].run(retcode=(0,1))
    #if path1 == path2:
    #    print(f"For {path1}\n{rc}\n{stdout}\n{stderr}")
    return rc == 0


DIRECTORY_OF_INTEREST = "local_builds_mudkip"

INCLUDE_ALL_RUNS = ["bare", "dfs_no_sort"]
APKS_OF_INTEREST = ["base-master.apk", "base-arm64_v8a.apk", "base-xxhdpi.apk"]

unique_bundle_filepaths = []

for path, _, files in os.walk(os.getcwd()):
    if DIRECTORY_OF_INTEREST in path:
        for f in files:
            if "bundle_shasum_256" in f:
                filepath = os.path.join(path, f)
                if any(dir in path for dir in INCLUDE_ALL_RUNS):
                    unique_bundle_filepaths.append(filepath)
                elif "01" in path:
                    unique_bundle_filepaths.append(filepath)

#print(unique_bundle_filepaths)

results = []
for apk in APKS_OF_INTEREST:
    for i in range(0, int(len(unique_bundle_filepaths))):
        for j in range(0, i):
            if i != j:
                result = run_apkdiff(apk_filepath(unique_bundle_filepaths[i], apk), apk_filepath(unique_bundle_filepaths[j], apk))
                # print(i, j, f" :{result}")
                results.append(result)
                if result:
                    ### Spit out any result that matched in a readable form
                    print(f"{apk} matched: {get_folder_run_from_apk_filepath(unique_bundle_filepaths[i])} - {get_folder_run_from_apk_filepath(unique_bundle_filepaths[j])}")
