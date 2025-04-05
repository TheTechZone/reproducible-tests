import os
import json
from setup.structure import(
    DATA_ROOT
) 


###
# General utility
###

def differences(list1, list2):
    """
    Compare two given list and return the differences in a human readable form for ad hoc printing
    """
    assert(len(list1)==len(list2)), f"The two lists to compare had differing lengths!"
    differences = []
    for i, value in enumerate(list1):
        if value != list2[i]:
            differences.append(f"{value} -> {list2[i]}\n")
    return differences

###
# Metadata comparison
###

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


# Test for internal consistency
def is_metadata_to_dirorder_consistent(tarfile):
    # True if the files are consistent amongst each other (dirorder is equivalent to outputfile)
    diff = differences(get_mtimes_list(tarfile), get_metadata_list(tarfile))
    if len(diff) > 0:
        print(f"Metadata inconsistency in: {tarfile}")
        print(diff)
        return False
    return True


# Test between runs
def compare_metadata_list(tarfile1, tarfile2) -> tuple[bool, list]:
    list1 = get_metadata_list(tarfile1)
    list2 = get_metadata_list(tarfile2)
    diff = differences(list1, list2)
    return len(diff) > 0, diff


###
# Dex sort and first dex tests
###

# We don't have an internal consistency test here since no dexes ever matched the playstore
# TODO: may be useful to add one in the future

def get_dex_list(tarfile):
    with open(os.path.join(DATA_ROOT, "res", "dex_sort.json"), 'r') as f:
        obj = json.loads(f.read())
    return obj[tarfile]["local"]


def dict_pairs_to_string(dictionary):
    res = []
    for k in dictionary.keys():
        res.append(f"{k}:{dictionary[k]}")
    return res


# Compare all dex hashes
def compare_dex_hashes(tarfile1, tarfile2):
    dex_list_1 = get_dex_list(tarfile1)
    dex_list_2 = get_dex_list(tarfile2)
    # Create symmetric difference between the sets
    diff = set(dict_pairs_to_string(dex_list_1)).symmetric_difference(set(dict_pairs_to_string(dex_list_2)))
    return len(diff) > 0, diff


def get_first_dex_hash(dex_list):
    for k in dex_list.keys():
        if dex_list[k] == "classes.dex":
            return k


# Because according to Aditz the first dex file matters more!
# Only checks classes.dex
def compare_first_dex_file_hash(tarfile1, tarfile2):
    dex_hash_1 = get_first_dex_hash(get_dex_list(tarfile1))
    dex_hash_2 = get_first_dex_hash(get_dex_list(tarfile2))
    equal = dex_hash_1 == dex_hash_2
    return equal, [] if equal else [f"{dex_hash_1}->{dex_hash_2}"]


####
# Define a name for each toplevel test, this will be used when updating the 'summary' results of this test
####
## TODO: Refine these names
COMPARE_TO_TESTNAME = {
    compare_metadata_list:"metadata_list", 
    compare_dex_hashes:"dex_sort",
    compare_first_dex_file_hash:"does_first_dexfile_match"
}
