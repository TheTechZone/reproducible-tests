from pathlib import Path
import json
from typing import Callable, Optional, overload, Literal
from setup.structure import (
    DATA_ROOT,
    TARS_ROOT,
    SUMMARY_ROOT,
    version_and_run_from_tar_filename,
    summary_path,
    create_or_clear_summary_directory_for,
)
from analysis.checks import (
    COMPARE_TO_CHECK_NAME,
    compare_metadata_list,
    is_metadata_to_dirorder_consistent,
)

CompareFn = Callable[[str, str], tuple[bool, list]]


def run_checks(tarfiles: list[str], compare: CompareFn) -> None:
    """
    Clears any previous data in the summary directory of that specific check (created from check name, See analyse::COMPARE_TO_CHECK_NAME),
    then runs the check for all versions and for all combinations of parameters.

    (Might be superfluous, doing this at another level rn.):
    Note: Currently this takes the same set of files for between and within version comparisons. May want to separate that
    for some of the checks (e.g., metadata consistency)
    """
    create_or_clear_summary_directory_for(COMPARE_TO_CHECK_NAME[compare], version=True)
    versions = all_versions()
    for v in versions:
        check_for_same_version(v, tarfiles, compare)
        print()
    create_or_clear_summary_directory_for(COMPARE_TO_CHECK_NAME[compare], version=False)
    check_for_same_params(None, compare, dfs=False)
    print()

    # Enumerate the 4 parameter combinations
    param_combinations = [
        {"dfs": True, "alph": True, "ctime": False, "reverse": False},
        {"dfs": True, "alph": True, "ctime": False, "reverse": True},
        {"dfs": True, "alph": False, "ctime": True, "reverse": False},
        {"dfs": True, "alph": False, "ctime": True, "reverse": True},
    ]

    for params in param_combinations:
        check_for_same_params(None, compare, **params)  # type: ignore
        print()


###
# Run all the checks on the data
###


def run_all_checks(checks: list[CompareFn], with_metadata_list: bool = True) -> None:
    """
    Executes all the checks on all the available tared builds.
    checks: contains all the handles to checks that should be applied
    PRE: compare_metadata_list not in checks
    """

    for check in checks:
        run_checks(all_tarfiles(), check)
    if with_metadata_list:
        tarfiles = assemble_consistent_tarfile_list(is_metadata_to_dirorder_consistent)
        run_checks(tarfiles, compare_metadata_list)


###
# The analysis makes use of the 'classified_runs' structure
# a dict of SortedRuns where the key is the description of the classification
#
# Examples:
# classified_runs = {"v7.30.4":SortedRuns(...), "v7.28.4":SortedRuns(...), ...}
# classified_runs = {"ctime reverse sorted":SortedRuns(...), "alphabetically sorted":SortedRuns(...), ...}
###


class SortedRuns:
    """
    Helper class to devide runs into distinct 'classes'
    (currently by version or parameter combination)
    Attributes:
        consistent: Denotes if the runs are consistent amongst each other for the current check
        runs: All the tarfiles that belong to this 'class' of run.
    """

    def __init__(self, consistent: bool, runs: list[str]):
        self.consistent = consistent
        self.runs = runs


def print_with_params(
    version: str,
    file: str,
    sorting_criteria: Optional[str] = None,
    direction: Optional[str] = None,
) -> None:
    """
    Convenience method to pretty print the contents of a result json file
    for a specified version and optionally filtered by parameters.

    PRE:
    sorting_criteria is None or ('ctime' or 'alph')
    direction is None or ('reverse' or 'sort')
    """
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
def assemble_consistent_tarfile_list(
    consistency_check: Callable[[str], bool],
) -> list[str]:
    """
    assembles a list of tarfiles that are consistent amongst themselves relative to the provided check
    (if multiple runs for the same version and parameters are present)
    or that only had a single run
    """
    consistent_runs = []
    tarfiles_dir = Path(TARS_ROOT)

    for tarfile in tarfiles_dir.iterdir():
        if consistency_check(
            tarfile.name
        ):  # tarfile is now a Path object, use .name to get the filename
            consistent_runs.append(tarfile.name)

    return consistent_runs


def _compare_amongst_runs(
    classified_runs: dict[str, SortedRuns],
    key: Optional[str],
    compare: CompareFn,
    summary_file: Optional[str] = None,
) -> None:
    """
    if key is given, method checks for internal consistency between multiple runs
    contained in the individual SortedRun Objects stored in classified_runs
    Note: this assumes that the consistency bit is initialized to True initially, and will be set
    to false if any of the internal pairwise checks fail,
    Otherwise we check pairwise for each run that was classified as internally consistent (takes the first element
    if there are multiple) and record the result

    Parameters:
        classified_runs: All the runs of interest, keyed by their description
        key: key in classified_runs.keys()
        compare: the check to be applied
        summary_file: where to record the results
    """
    record_result = True if summary_file is not None else False
    mark_consistency = False
    if key is None:
        to_compare = []
        # compare the first run of each set marked consistent with each other
        for k in classified_runs.keys():
            if classified_runs[k].consistent:
                if len(classified_runs[k].runs) > 0:
                    # Only comparing consistent runs against one another
                    to_compare.append(classified_runs[k].runs[0])
        # print(f"classified_runs:\n{classified_runs}")
        # print(f"compared to:\n{to_compare}")
    else:
        to_compare = classified_runs[key].runs
        mark_consistency = True
        # before we mark consistency, the consistency bit is assumed to be set as True
        assert classified_runs[key].consistent, f"{key} consistency bit was not set to consistent, before we doing pairwise tests!"
    mid = int(len(to_compare) / 2)
    for tarfile in to_compare[0:mid]:
        for other in [file for file in to_compare if file != tarfile]:
            # Second parameter, diff, could be printed for runs of interest here
            (has_diff, _) = compare(tarfile, other)
            if has_diff:
                v_01, tar_run_01 = version_and_run_from_tar_filename(tarfile)
                v_02, tar_run_02 = version_and_run_from_tar_filename(other)
                if mark_consistency:
                    assert key
                    classified_runs[key].consistent = False
                    if "dfstest" in tarfile:
                        run_01 = f"{v_01}_{tar_run_01}_dfstest"
                    else:
                        run_01 = f"{v_01}_{tar_run_01}"
                    if "dfstest" in other:
                        run_02 = f"{v_02}_{tar_run_02}_dfstest"
                    else:
                        run_02 = f"{v_02}_{tar_run_02}"
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


def are_classified_runs_consistent(
    classified_runs: dict[str, SortedRuns],
    compare: CompareFn,
    summary_file=None,
) -> None:
    """
    Marks any class of runs that only had a single run as internally consistent.
    Calls _compare_amongst_runs for any that have more than one run.
    Finally, compares all the internally consistent runs amongst each other.

    Parameters:
        classified_runs: All the runs of interest, keyed by their description
        compare: the check to be applied
        summary_file: where to record the results
    """
    for key in classified_runs.keys():
        no_runs = len(classified_runs[key].runs)
        if no_runs < 2:
            print(f"There was at most one {key} run.")
            classified_runs[key].consistent = True
        else:
            print(f"There were {no_runs} {key} runs")
            # check internal consistency
            # Writing down the result each time no matter if internal test or not
            _compare_amongst_runs(classified_runs, key, compare, summary_file)
    # Now compare any runs that were consistent amongst each other
    print("Checking consistency amongst internally consistent runs...")
    _compare_amongst_runs(classified_runs, None, compare, summary_file)


def check_for_same_version(
    version: str, tarfiles: list[str], compare: CompareFn
) -> None:
    """
    Sorts any runs with the provided version into their existing distinct parameter combinations.
    Then calls are_classified_runs_consistent with the provided check.
    The results are written to a summary file determined by the check
        method and version.
    Parameters:
        version: which version to consider
        tarfiles: which tarfiles to include (will be get_all_tarfiles() in the usual case)
        compare: which check to apply
    """
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
        "alphabetically sorted": SortedRuns(
            True, [file for file in alphabetical if "sort" in file]
        ),
        "alphabetically reverse sorted": SortedRuns(
            True, [file for file in alphabetical if "reverse" in file]
        ),
        "ctime sorted": SortedRuns(True, [file for file in ctime if "sort" in file]),
        "ctime reverse sorted": SortedRuns(
            True, [file for file in ctime if "reverse" in file]
        ),
        "without disorderfs": SortedRuns(True, vanilla),
    }
    print(f"checking version {version}...")
    # print(classified_runs)
    # Create/truncate summary file for idempotence
    summary_file = Path(summary_path(COMPARE_TO_CHECK_NAME[compare], version))
    if not summary_file.exists():
        print(f"Creating {summary_file.relative_to(SUMMARY_ROOT)}...")
        summary_file.write_text("{}")

    are_classified_runs_consistent(classified_runs, compare, summary_file)


def all_versions() -> list[str]:
    """
    Extracts all the distinct versions from the TARS_ROOT folder.
    """
    versions: list[str] = []
    for tarfile in TARS_ROOT.iterdir():
        v, _ = version_and_run_from_tar_filename(tarfile)
        assert v
        versions.append(v)
    return list(set(versions))


def _tarfiles_with_params(
    dfs: bool, alph: Optional[bool], ctime: Optional[bool], sort: Optional[bool], reverse: Optional[bool]
) -> list[str]:
    """
    Returns a filtered list of tarfile names from the TARS_ROOT directory
    based on specified parameter flags.

    Parameters:
        dfs: return runs done with disorderfs based on the optional ('alph', 'ctime', and 'reverse') flags.
            Note that any optional flag that is not passed will default to False.
        alph: include tarfiles with contents sorted alphabetically.
        ctime: include tarfiles with contents sorted by ctime.
        reverse: include the files sorted by alph/ctime in reverse order

    Returns:
        List[str]: A list of tarfile names matching the given parameters.
    """
    files: list[str] = []
    ignored: list[str] = []
    if dfs: # Set any unset variables if needed
        alph = False if alph is None else alph
        ctime = False if ctime is None else ctime
        sort = False if sort is None else sort
        reverse = False if reverse is None else reverse
    for tarfile in all_tarfiles():
        if dfs:
            if alph and "alph" in tarfile or ctime and "ctime" in tarfile:
                if (reverse and "reverse" in tarfile) or (
                    sort and "sort" in tarfile
                ):
                    files.append(tarfile)
                else:
                    ignored.append(tarfile)
            else:
                ignored.append(tarfile)
        else:
            if all(key not in tarfile for key in ("alph", "ctime", "sort", "reverse")):
                files.append(tarfile)
            else:
                ignored.append(tarfile)
    assert set(files + ignored) == set(
        all_tarfiles()
    ), f"Some filenames were malformed!\ndfs{dfs},alph:{alph}, ctime:{ctime}, reverse: {reverse}\n {set(all_tarfiles()) - set(files) - set(ignored)}"
    return files


def all_tarfiles() -> list[str]:
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


# Define the allowed combinations of parameters


@overload
def check_for_same_params(
    tarfiles: Optional[list[str]], compare: CompareFn, dfs: Literal[False]
) -> None: ...


@overload
def check_for_same_params(
    tarfiles: Optional[list[str]],
    compare: CompareFn,
    dfs: Literal[False],
    alph: Optional[bool],
    ctime: Optional[bool],
    reverse: Optional[bool]
) -> None: ...


@overload
def check_for_same_params(
    tarfiles: Optional[list[str]],
    compare: CompareFn,
    dfs: Literal[True],
    alph: Literal[True],
    ctime: Literal[False],
    reverse: bool
) -> None: ...


@overload
def check_for_same_params(
    tarfiles: Optional[list[str]],
    compare: CompareFn,
    dfs: Literal[True],
    alph: Literal[False],
    ctime: Literal[True],
    reverse: bool
) -> None: ...


def check_for_same_params(
    tarfiles: Optional[list[str]],
    compare: CompareFn,
    dfs: bool,
    alph: Optional[bool] = None,
    ctime: Optional[bool] = None,
    reverse: Optional[bool] = None
) -> None:
    """
    Sorts any runs with the provided parameters into their existing distinct versions.
    Then calls are_classified_runs_consistent with the provided check.
    The results are written to a summary file determined by the check
        method and parameter description

    Parameters:
        tarfiles: A list of tarfile names to check. If `None`, all
            matching tarfiles based on the given parameters are included.
        compare: A comparison function that
            takes two file paths and returns a tuple (is_equal, details).
        dfs: Whether to consider disorderfs-based runs. If `dfs` is False, the other sorting flags (`alph`, `ctime`, `reverse`) are ignored.
        alph: Whether to include runs with alphabetical sorting (requires `dfs`=True). Mutually exclusive with `ctime`.
        ctime: Whether to include runs with ctime sorting (requires `dfs`=True). Mutually exclusive with `alph`.
        reverse: Whether to include reverse-sorted runs (requires `dfs`=True).
    """
    versions = all_versions()
    # create description string
    description = description_from_params(dfs, alph, ctime, reverse)
    appropriate_tars = _tarfiles_with_params(dfs, alph, ctime, reverse)
    if tarfiles is None:
        relevant_files = appropriate_tars
    else:
        relevant_files = [file for file in tarfiles if file in appropriate_tars]
    classified_runs = {}
    for v in versions:
        classified_runs[v] = SortedRuns(True, [])
        for tarfile in relevant_files:
            if v in tarfile:
                classified_runs[v].runs.append(tarfile)
    print(f"checking the parameters: '{description}'...")
    summary_file = Path(summary_path(COMPARE_TO_CHECK_NAME[compare], description))

    if not summary_file.exists():
        print(f"Creating {summary_file.relative_to(SUMMARY_ROOT)}...")
        summary_file.write_text("{}")

    are_classified_runs_consistent(classified_runs, compare, summary_file)
