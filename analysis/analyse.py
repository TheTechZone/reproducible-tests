from pathlib import Path
import json
from typing import Mapping, Union, Optional
from collections.abc import Callable
from setup.structure import (
    DATA_ROOT,
    TARS_ROOT,
    SUMMARY_ROOT,
    version_and_run_from_tar_filename,
    parameters_from_tar_filename,
    summary_path,
    create_or_clear_summary_directory_for,
)
from analysis.asserts import (
    COMPARE_TO_TESTNAME,
    compare_dex_hashes,
    compare_first_dex_file_hash,
    compare_metadata_list,
    is_metadata_to_dirorder_consistent,
)


def run_tests(tarfiles, compare: Callable[[str, str], tuple[bool, list]]):
    """
    Currently this takes the same set of files for between and within version comparisons. May want to separate that
    for some of the tests (e.g., metadata consistency)
    """
    create_or_clear_summary_directory_for(COMPARE_TO_TESTNAME[compare], version=True)
    versions = get_all_versions()
    for v in versions:
        check_for_same_version(v, tarfiles, compare)
        print()
    create_or_clear_summary_directory_for(COMPARE_TO_TESTNAME[compare], version=False)
    check_for_same_params(None, compare, dfs=False)
    print()
    # Enumerate the 4 parameter combinations
    check_for_same_params(
        None, compare, dfs=True, alph=True, ctime=False, reverse=False
    )
    print()
    check_for_same_params(None, compare, dfs=True, alph=True, ctime=False, reverse=True)
    print()
    check_for_same_params(
        None, compare, dfs=True, alph=False, ctime=True, reverse=False
    )
    print()
    check_for_same_params(None, compare, dfs=True, alph=False, ctime=True, reverse=True)


###
# Run all the tests
###


def run_all_tests(tests, with_metadata_list=True):
    for test in tests:
        run_tests(get_all_tarfiles(), test)
    if with_metadata_list:
        tarfiles = assemble_consistent_tarfile_list(is_metadata_to_dirorder_consistent)
        run_tests(tarfiles, compare_metadata_list)


###
# The analysis makes use of the 'classified_runs' structure
# a dict of dicts where the first key is the description of the set of runs that
# follows in the next dict (e.g., version, or which parameters were active)
# the next dict is keyed by the opposite key
# the innermost strucure is as follows (basically a named tuple implemented as a dict):
# TODO: may want to make this a tuple instead
# DATA := {"consistent":boolean, "runs":list[str]}
# where the consistent flag indicates internal consistency between runs (if applicable)
# and "runs" contain all tarfiles which are grouped by the same fixed parameters & version
#
# Examples:
# classified_runs = {"v7.30.4":{"consistent":True, "runs":["signal-android-ctime-reversed_v7.30.4_01.tar.gz",...]}...}
# classified_runs = {"ctime reverse sorted":{"consistent":True, "runs":["signal-android-ctime-reversed_v7.30.4_01.tar.gz",...]}...}
###


def print_with_params(
    version: str,
    file: str,
    sorting_criteria: Optional[str] = None,
    direction: Optional[str] = None,
):
    file_path = DATA_ROOT / "res" / file

    with file_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    for key, value in data.items():
        if (
            version in key
            and (sorting_criteria is None or sorting_criteria in key)
            and (direction is None or direction in key)
        ):
            print(f"{key}: {json.dumps(value, indent=4, sort_keys=True)}")


# E.g., used to filter out runs that were not internally consistent for the metadata list
# Or could be used to filter out runs that did not match something we want to match in their playstore equivalent
def assemble_consistent_tarfile_list(consistency_check: Callable[[str], bool]):
    """makes sure that multiple runs with the same parameters are consistent amongst each other"""
    consistent_runs = []
    tarfiles_dir = Path(TARS_ROOT)

    for tarfile in tarfiles_dir.iterdir():
        if consistency_check(
            tarfile.name
        ):  # tarfile is now a Path object, use .name to get the filename
            consistent_runs.append(tarfile.name)


def _compare_amongst_runs(
    classified_runs,
    key,
    compare: Callable[[str, str], tuple[bool, list]],
    summary_file=None,
):
    """
    if key is given, method checks for internal consistency between multiple runs
    contained in this object,
    Otherwise we check pairwise for each run that was classified as internally consistent,
    and record the result
    """
    # TODO: Do I these to be optional args?
    record_result = True if summary_file is not None else False
    mark_consistency = False
    if key is None:
        to_compare = []
        # compare the first run of each set marked consistent with each other
        for k in classified_runs.keys():
            if classified_runs[k]["consistent"]:
                if len(classified_runs[k]["runs"]) > 0:
                    # Only comparing consistent runs against one another
                    to_compare.append(classified_runs[k]["runs"][0])
        # print(f"classified_runs:\n{classified_runs}")
        # print(f"compared to:\n{to_compare}")
    else:
        to_compare = classified_runs[key]["runs"]
        mark_consistency = True
    mid = int(len(to_compare) / 2)
    for tarfile in to_compare[0:mid]:
        for other in [file for file in to_compare if file not in tarfile]:
            (has_diff, diff) = compare(tarfile, other)
            if has_diff:
                v_01, run_01 = version_and_run_from_tar_filename(tarfile)
                v_02, run_02 = version_and_run_from_tar_filename(other)
                if (
                    mark_consistency
                ):  # TODO: this is a confusing overload, unconfuse at some point
                    classified_runs[key]["consistent"] = False
                    if "dfstest" in tarfile:
                        run_01 = f"{v_01}_{run_01}_dfstest"
                    else:
                        run_01 = f"{v_01}_{run_01}"
                    if "dfstest" in other:
                        run_02 = f"{v_02}_{run_02}_dfstest"
                    else:
                        run_02 = f"{v_02}_{run_02}"
                    # print(f"diff:\n{"".join(diff)}")
                else:
                    # we want to indicate which parameters were compared against each other in this case
                    # we can cut off the prefix for that
                    run_01 = tarfile.split("signal-android-")[-1].replace(".tar.gz", "")
                    run_02 = other.split("signal-android-")[-1].replace(".tar.gz", "")
                print(f"MISSMATCH: {run_01} <=> {run_02}!")
            if record_result:
                # print(f"Recording result of {COMPARE_TO_TESTNAME[compare]} between {tarfile} and {other}")
                assert summary_file is not None  # to please the typecheckr
                with open(summary_file, "r") as f:
                    obj = json.loads(f.read())
                # create internal dicts if they do not yet exist
                if tarfile not in obj.keys():
                    obj[tarfile] = {}
                if other not in obj.keys():
                    obj[other] = {}
                # Both sides to turn the triangle into a symmetric matrix
                # True if the runs match, false otherwise
                obj[tarfile][other] = not has_diff
                obj[other][tarfile] = not has_diff
                with open(summary_file, "w") as f:
                    f.write(json.dumps(obj))


def check_consistency_of_classified_runs(
    classified_runs: dict[str, dict[str, Union[bool, list]]],
    compare: Callable[[str, str], tuple[bool, list]],
    summary_file=None,
) -> None:
    for key in classified_runs.keys():
        runs = len(classified_runs[key]["runs"])
        if runs < 2:
            print(f"Only one run was {key}")
            classified_runs[key]["consistent"] = True
        else:
            print(f"There were {runs} {key} runs")
            # check internal consistency
            # Writing down the result each time no matter if internal test or not
            _compare_amongst_runs(classified_runs, key, compare, summary_file)
    # Now compare any runs that were consistent amongst each other
    print("Checking consistency of equal and internally consistent runs...")
    _compare_amongst_runs(classified_runs, None, compare, summary_file)


def check_for_same_version(
    version, tarfiles, compare: Callable[[str, str], tuple[bool, list]]
) -> None:
    versioned_tarfiles = [file for file in tarfiles if version in file]
    # print(versioned_tarfiles)
    alphabetical = []
    ctime = []
    alphabetical = [file for file in versioned_tarfiles if "alph" in file]
    ctime = [file for file in versioned_tarfiles if "ctime" in file]
    vanilla = [
        file
        for file in versioned_tarfiles
        if "ctime" not in file and "alph" not in file
    ]
    # create dictionary for internal consistency check between repeats of different runs:
    classified_runs = {
        "alphabetically sorted": {
            "consistent": True,
            "runs": [file for file in alphabetical if "sort" in file],
        },
        "alphabetically reverse sorted": {
            "consistent": True,
            "runs": [file for file in alphabetical if "reverse" in file],
        },
        "ctime sorted": {
            "consistent": True,
            "runs": [file for file in ctime if "sort" in file],
        },
        "ctime reverse sorted": {
            "consistent": True,
            "runs": [file for file in ctime if "reverse" in file],
        },
        "without disorderfs": {"consistent": True, "runs": vanilla},
    }
    print(f"checking version {version}...")
    # print(classified_runs)
    # Create/truncate summary file for idempotence
    summary_file = Path(summary_path(COMPARE_TO_TESTNAME[compare], version))
    if not summary_file.exists():
        print(f"Creating {summary_file.relative_to(SUMMARY_ROOT)}...")
        summary_file.write_text("{}")

    check_consistency_of_classified_runs(classified_runs, compare, summary_file)


def get_all_versions() -> list[str]:
    versions = []
    for tarfile in TARS_ROOT.iterdir():
        v, _ = version_and_run_from_tar_filename(tarfile)
        versions.append(v)
    return list(set(versions))


def _get_all_tarfiles_with_params(
    dfs: bool, alph: Optional[bool], ctime: Optional[bool], reverse: Optional[bool]
) -> list[str]:
    """
    Returns a filtered list of tarfile names from the TARS_ROOT directory
    based on specified parameter flags.

    Parameters:
        dfs: filter runs done with disorderfs based on the optional ('alph', 'ctime', and 'reverse') flags.
        alph: include tarfiles with contents sorted alphabetically.
        ctime: include tarfiles with contents sorted by ctime.
        reverse: include the files sorted by alph/ctime in reverse order

    Returns:
        List[str]: A list of tarfile names matching the given parameters.
    """
    files = []
    for tarfile in get_all_tarfiles():
        if dfs:
            if alph and "alph" in tarfile:
                if reverse and "reverse" in tarfile:
                    files.append(tarfile)
                elif not reverse and "sort" in tarfile:
                    files.append(tarfile)
            elif ctime and "ctime" in tarfile:
                if reverse and "reverse" in tarfile:
                    files.append(tarfile)
                elif not reverse and "sort" in tarfile:
                    files.append(tarfile)
        else:
            if (
                "alph" not in tarfile
                and "ctime" not in tarfile
                and "sort" not in tarfile
                and "reverse" not in tarfile
            ):
                files.append(tarfile)
    return files
    # todo: replace with this :)
    # for tarfile in os.listdir(TARS_ROOT):
    #     if dfs:
    #         if alph and "alph" in tarfile or ctime and "ctime" in tarfile:
    #             if (reverse and "reverse" in tarfile) or (not reverse and "sort" in tarfile):
    #                 files.append(tarfile)
    #     else:
    #         if all(key not in tarfile for key in ("alph", "ctime", "sort", "reverse")):
    #             files.append(tarfile)
    # return files


def get_all_tarfiles() -> list[str]:
    tarfiles_dir = Path(TARS_ROOT)
    return [tarfile.name for tarfile in tarfiles_dir.iterdir()]


def description_from_params(
    dfs: bool,
    alph: Optional[bool] = False,
    ctime: Optional[bool] = False,
    reverse: Optional[bool] = False,
) -> str:
    """
    Parameters:
        dfs: file was created with disorderfs
        alph: disorderfs was sorting alphabetically
        ctime: disorderfs was sorting by ctime.
        reverse: disorderfs was sorting in reverse order
    """
    description = ""
    if dfs:
        # Sanity checks
        assert not (
            alph and ctime
        ), f"Cannot be sorted alphabetically {alph} and by ctime {ctime} simultaneously!"
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
    return description


def check_for_same_params(
    tarfiles: Optional[list[str]],
    compare: Callable[[str, str], tuple[bool, list]],
    dfs: bool = False,
    alph: bool = False,
    ctime: bool = False,
    reverse: bool = False,
) -> None:
    """
    Checks whether a group of test runs (tarfiles) with the same parameters
        produce consistent comparison results across different versions.
    The comparison results are written to a summary file determined by the comparison
        method and parameter description

    Parameters:
        tarfiles (Optional[list[str]]): A list of tarfile names to check. If `None`, all
            matching tarfiles based on the given parameters are included.
        compare (Callable[[str, str], tuple[bool, list]]): A comparison function that
            takes two file paths and returns a tuple (is_equal, details).
        dfs: Whether to consider disorderfs-based runs. If `dfs` is False, the other sorting flags (`alph`, `ctime`, `reverse`) are ignored.
        alph: Whether to include runs with alphabetical sorting (requires `dfs`=True). Mutually exclusive with `ctime`.
        ctime: Whether to include runs with ctime sorting (requires `dfs`=True). Mutually exclusive with `alph`.
        reverse: Whether to include reverse-sorted runs (requires `dfs`=True).
    """
    versions = get_all_versions()
    # create description string
    description = description_from_params(dfs, alph, ctime, reverse)
    appropriate_tars = _get_all_tarfiles_with_params(dfs, alph, ctime, reverse)
    if tarfiles is None:
        relevant_files = appropriate_tars
    else:
        relevant_files = [file for file in tarfiles if file in appropriate_tars]
    classified_runs = {}
    for v in versions:
        classified_runs[v] = {"consistent": True, "runs": []}
        for tarfile in relevant_files:
            if v in tarfile:
                classified_runs[v]["runs"].append(tarfile)
    print(f"checking the parameters: '{description}'...")
    summary_file = Path(summary_path(COMPARE_TO_TESTNAME[compare], description))

    if not summary_file.exists():
        print(f"Creating {summary_file.relative_to(SUMMARY_ROOT)}...")
        summary_file.write_text("{}")

    check_consistency_of_classified_runs(classified_runs, compare, summary_file)
