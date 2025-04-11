import json
from setup.structure import DATA_ROOT
from typing import Optional

###
# General utility
###


def _differences(list1: list[str], list2: list[str]) -> list[str]:
    """
    Compare two given list and return the differences in a human readable form
    ["differing_value_list1 -> differing_value_list2", ...]

    PRE: len(list1) == len(list2)
    """
    assert len(list1) == len(list2), "The two lists to compare had differing lengths!"
    differences = []
    for i, value in enumerate(list1):
        if value != list2[i]:
            differences.append(f"{value} -> {list2[i]}\n")
    return differences


###
# Metadata comparison
###


def _get_metadata_list(tarfile):
    """
    reads output_metadata_mtimes.json from the data/res folder and returns all recorded output files
    expects the format: {tarfile:{..., "output-metadata.json":{..., "elements":[{"outputFile":"value"}, {"outputFile":value}, ...], ...}, ...}, ...}
    """
    metadata_file_path = DATA_ROOT / "res" / "output_metadata_mtimes.json"

    with metadata_file_path.open("r") as f:
        obj = json.load(f)

    metadata = json.loads(obj[tarfile]["output-metadata.json"])
    metadata_list = []
    for element in metadata["elements"]:
        metadata_list.append(element["outputFile"])
    return metadata_list


def _get_mtimes_list(tarfile: str) -> list[str]:
    """
        parses the file order stored in "mtimes" of the output_metadata_mtimes.json dict
        and returns them as a list.
    """
    metadata_file_path = DATA_ROOT / "res" / "output_metadata_mtimes.json"

    with metadata_file_path.open("r") as f:
        obj = json.load(f)

    mtime_sort = obj[tarfile]["mtimes"]
    mtime_list = []
    for line in mtime_sort.split("\n"):
        if "+0000" in line:
            # ignore the file we are comparing to
            if "output-metadata.json" not in line:
                mtime_list.append(line.split("+0000")[-1].strip())
    return mtime_list


def is_metadata_to_dirorder_consistent(tarfile: str) -> bool:
    """
    Test for internal consistency between files parsed from the mtimes output and the metadata list
        
    Returns:
        `True` if the files are consistent amongst each other (dirorder is equivalent to outputfile)
    """
    diff = _differences(_get_mtimes_list(tarfile), _get_metadata_list(tarfile))
    if has_diffs := len(diff) > 0:
        print(f"Metadata inconsistency in: {tarfile}")
        print(diff)
    return has_diffs


# Test between runs
def compare_metadata_list(tarfile1, tarfile2) -> tuple[bool, list]:
    """
        for two runs denoted by tarfile1 & tarfile2
        check if the metadata lists are equal
        returns: equal, differences
    """
    list1 = _get_metadata_list(tarfile1)
    list2 = _get_metadata_list(tarfile2)
    diff = _differences(list1, list2)
    return len(diff) > 0, diff


###
# Dex sort and first dex tests
###

# We don't have an internal consistency test here since no dexes ever matched the playstore
# TODO: may be useful to add one in the future


def get_dex_list_for_local_build(tarfile) -> dict:
    dex_sort_file_path = DATA_ROOT / "res" / "dex_sort.json"
    with dex_sort_file_path.open("r") as f:
        obj = json.load(f)
    return obj[tarfile]["local"]


def dict_pairs_to_string(dictionary: dict) -> list[str]:
    res = []
    for k in dictionary.keys():
        res.append(f"{k}:{dictionary[k]}")
    return res


# Compare all dex hashes
def compare_dex_hashes(tarfile1: str, tarfile2: str) -> tuple[bool, set[str]]:
    dex_list_1 = get_dex_list_for_local_build(tarfile1)
    dex_list_2 = get_dex_list_for_local_build(tarfile2)
    # Create symmetric difference between the sets
    diff = set(dict_pairs_to_string(dex_list_1)).symmetric_difference(
        set(dict_pairs_to_string(dex_list_2))
    )
    return len(diff) > 0, diff


def get_first_dex_hash(dex_list: dict[str, dict]) -> Optional[str]:
    for k in dex_list.keys():
        if dex_list[k] == "classes.dex":
            return k


# Because according to Aditz the first dex file matters more!
# Only checks classes.dex
def compare_first_dex_file_hash(tarfile1: str, tarfile2: str) -> tuple[bool, list[str]]:
    dex_hash_1 = get_first_dex_hash(get_dex_list_for_local_build(tarfile1))
    dex_hash_2 = get_first_dex_hash(get_dex_list_for_local_build(tarfile2))
    equal = dex_hash_1 == dex_hash_2
    return equal, [] if equal else [f"{dex_hash_1}->{dex_hash_2}"]


####
# Define a name for each toplevel test, this will be used when updating the 'summary' results of this test
####
## TODO: Refine these names
COMPARE_TO_TESTNAME = {
    compare_metadata_list: "metadata_list",
    compare_dex_hashes: "dex_sort",
    compare_first_dex_file_hash: "does_first_dexfile_match",
}
