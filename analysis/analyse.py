import os
import json
from typing import Mapping, Union
from collections.abc import Callable
from setup.structure import(
    DATA_ROOT,
    TARS_ROOT,
    extract_version_and_run
)


def print_with_params(version, file, sorting_criteria=None, direction=None):
    with open(os.path.join(DATA_ROOT, "res", file), "r") as f:
        data = json.loads(f.read())
    
    for key in data.keys():
        if version in key and sorting_criteria in key and direction in key:
            print(f"{key}:{json.dumps(data[key], indent=4, sort_keys=True)}")


def is_metadata_to_dirorder_consistent(tarfile):
    # True if the files are consistent amongst each other
    diff = _differences(get_mtimes_list(tarfile), get_metadata_list(tarfile))
    if len(diff) > 0:
        print(f"Metadata inconsistency in: {tarfile}")
        print(diff)
        return False
    return True


def get_metadata_list(tarfile):
    with open(os.path.join(DATA_ROOT, "res", "output_metadata_mtimes.json"), "r") as f:
        obj = json.loads(f.read())
    metadata = json.loads(obj[tarfile]["output-metadata.json"])
    metadata_list = []
    for element in metadata["elements"]:
        metadata_list.append(element["outputFile"])
    return metadata_list


def get_mtimes_list(tarfile):
    with open(os.path.join(DATA_ROOT, "res", "output_metadata_mtimes.json"), "r") as f:
        obj = json.loads(f.read())
    mtime_sort = obj[tarfile]["mtimes"]
    mtime_list = []
    for line in mtime_sort.split("\n"):
            if "+0000" in line:
                # ignore the file we are comparing to
                if "output-metadata.json" not in line:
                    mtime_list.append(line.split("+0000")[-1].strip())
    return mtime_list


def _differences(list1, list2):
    assert(len(list1)==len(list2)), f"The two lists to compare had differing lengths!"
    differences = []
    for i, value in enumerate(list1):
        if value != list2[i]:
            differences.append(f"{value} -> {list2[i]}\n")
    return differences


def assemble_consistent_tarfile_list(consistency_check: Callable[[str], bool]):
    """metadata to dirorder"""
    consistent_runs = []
    for tarfile in os.listdir(TARS_ROOT):
        if consistency_check(tarfile):
            consistent_runs.append(tarfile)
    return consistent_runs



def compare_metadata_list(tarfile1, tarfile2) -> tuple[bool, list]:
    list1 = get_metadata_list(tarfile1)
    list2 = get_metadata_list(tarfile2)
    diff = _differences(list1, list2)
    return len(diff) > 0, diff
    

def _compare_amongst_runs(classified_runs, key, compare: Callable[[str, str], tuple[bool, list]]):
    print_run_number = False
    if key is None:
        to_compare = []
        # compare the firs run of each set marked consistent with each other
        for key in classified_runs.keys():
            if classified_runs[key]["consistent"]:
                if len(classified_runs[key]["runs"]) > 0:
                    to_compare.append(classified_runs[key]["runs"][0])
    else:
        to_compare = classified_runs[key]["runs"]
        print_run_number = True
    middle = int(len(to_compare)/2)
    for tarfile in to_compare[0:middle]:
        for other in [file for file in to_compare if file not in tarfile]:
            (has_diff, diff) = compare(tarfile, other)
            if has_diff:
                _, run_01 = extract_version_and_run(tarfile) 
                _, run_02 = extract_version_and_run(other)
                if print_run_number:
                    if "dfstest" in tarfile:
                        run_01 = f"dfstest_{run_01}"
                    if "dfstest" in other:
                        run_02 = f"dfstest_{run_02}"
                    #print(f"diff:\n{"".join(diff)}")
                    classified_runs[key]["consistent"] = False
                else:
                    # we want to indicate which parameters were compared against each other in this case
                    # we can cut off the prefix for that
                    run_01 = tarfile.split("signal-android-")[-1].replace(".tar.gz", "")
                    run_02 = other.split("signal-android-")[-1].replace(".tar.gz", "")
                print(f"run {run_01} was inconsistent with run {run_02}!")

    
def check_consistency_of_classified_runs(classified_runs: Mapping[str, Mapping[str, Union[bool, list]]], compare: Callable[[str, str], tuple[bool, list]]):
    for key in classified_runs.keys():
        runs = len(classified_runs[key]["runs"])
        if runs < 2:
            print(f"Only one run was {key}")
            classified_runs[key]["consistent"] = True
        else:
            print(f"There were {runs} {key} runs")
            # check internal consistency
            _compare_amongst_runs(classified_runs, key, compare)
    # Now compare any runs that were consistent amongst each other
    _compare_amongst_runs(classified_runs, None, compare)


def check_for_same_version(version, tarfiles, compare: Callable[[str, str], tuple[bool, list]]):
    versioned_tarfiles = [file for file in tarfiles if version in file]
    #print(versioned_tarfiles)
    alphabetical = []
    ctime = []
    alphabetical = [file for file in versioned_tarfiles if "alph" in file]
    ctime = [file for file in versioned_tarfiles if "ctime" in file]
    vanilla = [file for file in versioned_tarfiles if "ctime" not in file and "alph" not in file]
    # create dictionary for internal consistency check between repeats of different runs:
    classified_runs = {
        "alphabetically sorted":{"consistent":True, "runs":[file for file in alphabetical if "sort" in file]},
        "alphabetically reverse sorted":{"consistent":True, "runs":[file for file in alphabetical if "reverse" in file]},
        "ctime sorted":{"consistent":True, "runs":[file for file in ctime if "sort" in file]},
        "ctime reverse sorted":{"consistent":True, "runs":[file for file in ctime if "reverse" in file]},
        "without disorderfs":{"consistent":True, "runs":vanilla}
    }
    print(f"checking version {version}...")
    check_consistency_of_classified_runs(classified_runs, compare)




def get_all_versions():
    versions = []
    for tarfile in os.listdir(TARS_ROOT):
        v, _ = extract_version_and_run(tarfile)
        versions.append(v)
    return list(set(versions))


def _get_all_tarfiles_with_params(dfs, alph=None, ctime=None, reverse=None):
    files = []
    for tarfile in os.listdir(TARS_ROOT):
        if dfs:
            if alph and "alph" in tarfile:
                if reverse and "reverse" in tarfile:
                    files.append(tarfile)
                elif "sort" in tarfile:
                    files.append(tarfile)
            elif ctime and "ctime" in tarfile:
                if reverse and "reverse" in tarfile:
                    files.append(tarfile)
                elif "sort" in tarfile:
                    files.append(tarfile)
        else:
            if "alph" not in tarfile and "ctime" not in tarfile \
            and "sort" not in tarfile and "reverse" not in tarfile:
                files.append(tarfile)
    return files
                

def get_all_tarfiles():
    return os.listdir(TARS_ROOT)



def check_for_same_params(tarfiles, compare: Callable[[str, str], tuple[bool, list]], dfs=False, alph=False, ctime=False, reverse=False):
    """
        if dfs == False, the other parameters are not considered
    """
    versions = get_all_versions()
    # create description string
    description = ""
    if dfs:
        # Sanity checks
        assert(not alph and ctime), "Cannot be sorted alphabetically and by ctime simultaneously!"
        if alph:
            if reverse:
                description = "alphabetically reverse sorted"
            else:
                description = "alphabetically sorted"
        elif ctime:
            if reverse:
                description = "ctime reverse sorted"
            else:
                description = "ctime sorted"
    else:
        description = "without disorderfs"
    relevant_files = _get_all_tarfiles_with_params(dfs, alph, ctime, reverse)
    classified_runs = {}
    for v in versions:
        key = f"{v} {description}"
        classified_runs[key] = {"consistent": True, "runs":[]} 
        for tarfile in relevant_files:
                if v in tarfile:
                    classified_runs[key]["runs"].append(tarfile)
    print(f"checking the parameters: '{description}'...")
    check_consistency_of_classified_runs(classified_runs, compare)
    




# Compare the hashes of the dexes for the same version
# TODO
def compare_dex_hashes(version):
    pass