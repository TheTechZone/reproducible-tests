"""
N.B. these rely heavily on mocking/patching to avoid having to make assumptions about which tars are present on the filesystem.
Manual checking and integration testing are still very recommended ;)
"""

import pytest
from unittest.mock import patch, MagicMock

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import analysis.analyse  # Import the module to patch things within it

# Import the functions to be tested and the dataclass
from analysis.analyse import (
    check_for_same_version,
    check_for_same_params,
    SortedRuns,
)


# --- Mocking Global Variables and Dependencies ---
# Mock the COMPARE_TO_CHECK_NAME dictionary and the dummy function
# This needs to be defined here for the tests.
def dummy_check_version_28(tarfile1: str, tarfile2: str) -> tuple[bool, list]:
    """
    Dummy check function that returns False (no diff) if both files
    contain "v7.28", and True (diff) otherwise.
    """
    is_not_28 = False
    diff_files = []
    if "v7.28" not in tarfile1:
        diff_files.append(tarfile1)
        is_not_28 = True
    if "v7.28" not in tarfile2:
        diff_files.append(tarfile2)
        is_not_28 = True
    # The actual diff content isn't used by the functions under test here,
    # so returning an empty list is fine for the mock scenario.
    return is_not_28, diff_files


# We need this mapping available *in the test file* to configure the mock lookup
# and determine expected paths.
MOCK_COMPARE_TO_CHECK_NAME_MAP = {dummy_check_version_28: "dummy_check_version_28"}


# --- Test Data ---
TEST_TARFILES = [
    "dfstest-signal-android-ctime-reversed_v7.28.4_01.tar.gz",
    "dfstest-signal-android-ctime-reversed_v7.28.4_02.tar.gz",
    "dfstest-signal-android-ctime-sort_v7.28.4_01.tar.gz",
    "dfstest-signal-android-alph-sort_v7.28.4_01.tar.gz",
    "signal-android-alph-reversed_v7.28.4_01.tar.gz",
    "signal-android-alph-sort_v7.28.4.tar.gz",
    "signal-android_v7.28.4.tar.gz",
    "signal-android_v7.28.4_02.tar.gz",
    "signal-android-ctime-reversed_v7.37.2_02.tar.gz",  # Note: No 'dfstest' prefix
    "signal-android-ctime-sort_v7.37.2.tar.gz",  # Note: No 'dfstest' prefix
    "dfstest-signal-android-alph-reversed_v7.37.2_01.tar.gz",
    "dfstest-signal-android-alph-reversed_v7.37.2_02.tar.gz",
    "dfstest-signal-android-alph-sort_v7.37.2_01.tar.gz",
    "signal-android_v7.37.2.tar.gz",
]


# --- Mock Path Object ---
# We need a mock Path object that behaves somewhat like a real one,
# especially for write_text and relative_to.
class MockPath:
    def __init__(self, path_str):
        self._path_str = path_str
        # Mock the write_text method on each instance
        self.write_text = MagicMock()

    def __truediv__(self, other):
        # Ensure joining paths results in another MockPath
        return MockPath(f"{self._path_str}/{other}")

    def relative_to(self, other):
        # Simple implementation for the test case
        other_str = str(other)  # Allow comparison with MockPath or str
        if self._path_str.startswith(other_str):
            # Use MockPath constructor to ensure return type consistency
            return MockPath(self._path_str[len(other_str) + 1 :])
        raise ValueError("path is not descendant of other")

    def __str__(self):
        return self._path_str

    def __repr__(self):
        return f"MockPath('{self._path_str}')"

    # Need comparison for assertions
    def __eq__(self, other):
        if isinstance(other, MockPath):
            return self._path_str == other._path_str
        elif isinstance(other, str):
            return self._path_str == other
        return False

    # Need hashing for dictionary keys if MockPath instances are used as keys
    # (They aren't in the current tests, but good practice)
    def __hash__(self):
        return hash(self._path_str)


# --- Fixture for patching common dependencies ---
@pytest.fixture(autouse=True)
def common_patches(monkeypatch):
    """
    Patch common dependencies used by both functions.
    `autouse=True` means this fixture is applied to all test functions in this file.
    """
    # Patch global Path and SUMMARY_ROOT
    mock_summary_root = MockPath("/mock/summary/root")
    monkeypatch.setattr("analysis.analyse.SUMMARY_ROOT", mock_summary_root)

    # Patch Path class itself. Side effect ensures each Path() call returns a new MockPath instance.
    mock_path_class = MagicMock(side_effect=lambda p: MockPath(str(p)))
    monkeypatch.setattr("analysis.analyse.Path", mock_path_class)

    # Mock the version_and_run_from_tar_filename
    mock_version_run_map = {
        "dfstest-signal-android-ctime-reversed_v7.28.4_01.tar.gz": ("v7.28.4", "01"),
        "dfstest-signal-android-ctime-reversed_v7.28.4_02.tar.gz": ("v7.28.4", "02"),
        "dfstest-signal-android-ctime-sort_v7.28.4_01.tar.gz": ("v7.28.4", "01"),
        "dfstest-signal-android-alph-sort_v7.28.4_01.tar.gz": ("v7.28.4", "01"),
        "signal-android-alph-reversed_v7.28.4_01.tar.gz": ("v7.28.4", "01"),
        "signal-android-alph-sort_v7.28.4.tar.gz": ("v7.28.4", None),
        "signal-android_v7.28.4.tar.gz": ("v7.28.4", None),
        "signal-android_v7.28.4_02.tar.gz": ("v7.28.4", "02"),
        "signal-android-ctime-reversed_v7.37.2_02.tar.gz": ("v7.37.2", "02"),
        "signal-android-ctime-sort_v7.37.2.tar.gz": ("v7.37.2", None),
        "dfstest-signal-android-alph-reversed_v7.37.2_01.tar.gz": ("v7.37.2", "01"),
        "dfstest-signal-android-alph-reversed_v7.37.2_02.tar.gz": ("v7.37.2", "02"),
        "dfstest-signal-android-alph-sort_v7.37.2_01.tar.gz": ("v7.37.2", "01"),
        "signal-android_v7.37.2.tar.gz": ("v7.37.2", None),
    }
    mock_version_and_run = MagicMock(
        side_effect=lambda filename: mock_version_run_map.get(filename, (None, None))
    )
    monkeypatch.setattr(
        "analysis.analyse.version_and_run_from_tar_filename", mock_version_and_run
    )

    # Mock summary_path. This mock needs to return a Path-like object.
    def mock_summary_path_func(check_name, classifier):
        # Use the patched Path (which returns MockPath) to build the path
        # Matching the structure in the test spec: /check_name/fixed_version/classifier.json
        return (
            mock_summary_root / check_name / "fixed_version" / f"{classifier}.json"
        )  # Matching spec structure

    monkeypatch.setattr(
        "analysis.analyse.summary_path", MagicMock(side_effect=mock_summary_path_func)
    )

    # Mock are_classified_runs_consistent - we only check if it was called correctly
    mock_are_consistent = MagicMock()
    monkeypatch.setattr(
        "analysis.analyse.are_classified_runs_consistent", mock_are_consistent
    )

    # Mock all_tarfiles as it's used by _tarfiles_with_params and all_versions (via iteration)
    mock_all_tarfiles = MagicMock(return_value=TEST_TARFILES)
    monkeypatch.setattr("analysis.analyse.all_tarfiles", mock_all_tarfiles)

    # Patch COMPARE_TO_CHECK_NAME with our local map
    monkeypatch.setattr(
        "analysis.analyse.COMPARE_TO_CHECK_NAME", MOCK_COMPARE_TO_CHECK_NAME_MAP
    )

    return {
        "summary_path": analysis.analyse.summary_path,
        "are_classified_runs_consistent": mock_are_consistent,
        "SUMMARY_ROOT": mock_summary_root,
        "Path": analysis.analyse.Path,
    }


# --- Helper function to get the summary file MockPath instance from Path calls ---
def get_summary_mock_path(mock_path_class, expected_filename):
    """Helper to find the MockPath instance created for the summary file."""
    # Look through calls made to the patched Path() constructor
    for call_args in mock_path_class.call_args_list:
        # Check if the first argument to Path() ends with the expected filename
        # Convert the argument to string for reliable comparison
        if str(call_args.args[0]).endswith(expected_filename):
            return (
                call_args.return_value
            )  # Return the MockPath instance created by this call
    return None


# --- Test A: check_for_same_version (v7.37.2) ---
@patch(
    "analysis.analyse.create_or_clear_summary_directory_for"
)  # Keep patched even if not asserted
def test_check_for_same_version_v37(_mock_create_or_clear, common_patches):
    """
    Tests check_for_same_version with version v7.37.2.
    Verifies it filters tarfiles correctly and calls are_classified_runs_consistent
    with the expected classified runs and summary file path.
    """
    version_to_check = "v7.37.2"
    compare_func = dummy_check_version_28
    mock_are_consistent = common_patches["are_classified_runs_consistent"]
    mock_path_class = common_patches["Path"]

    # Expected classified_runs for v7.37.2 from TEST_TARFILES
    # Manually filter and classify based on the function's logic (matching any 'alph' or 'ctime')
    v37_tarfiles = [f for f in TEST_TARFILES if version_to_check in f]

    expected_classified_runs = {
        "alphabetically sorted": SortedRuns(
            True, [f for f in v37_tarfiles if "alph" in f and "sort" in f]
        ),
        "alphabetically reverse sorted": SortedRuns(
            True, [f for f in v37_tarfiles if "alph" in f and "reverse" in f]
        ),
        "ctime sorted": SortedRuns(
            True, [f for f in v37_tarfiles if "ctime" in f and "sort" in f]
        ),
        "ctime reverse sorted": SortedRuns(
            True, [f for f in v37_tarfiles if "ctime" in f and "reverse" in f]
        ),
        "without disorderfs": SortedRuns(
            True,
            [
                f
                for f in v37_tarfiles
                if all(key not in f for key in ("alph", "ctime", "sort", "reverse"))
            ],
        ),
    }
    expected_classified_runs = {
        k: v for k, v in expected_classified_runs.items() if v.runs
    }

    expected_check_name = MOCK_COMPARE_TO_CHECK_NAME_MAP[compare_func]
    expected_summary_filename = f"{version_to_check}.json"

    # Call the function under test
    check_for_same_version(version_to_check, TEST_TARFILES, compare_func)

    # Assertions

    # Check the summary file was created/truncated
    summary_mock_path_instance = get_summary_mock_path(
        mock_path_class, expected_summary_filename
    )
    assert (
        summary_mock_path_instance is not None
    ), f"Summary file {expected_summary_filename} was not created"
    summary_mock_path_instance.write_text.assert_called_once_with("{}")

    # Check are_classified_runs_consistent was called with the correct arguments
    mock_are_consistent.assert_called_once()
    actual_classified_runs, actual_compare_func, actual_summary_file = (
        mock_are_consistent.call_args[0]
    )

    # Assert the classified runs dictionary
    assert actual_classified_runs.keys() == expected_classified_runs.keys()
    for key in expected_classified_runs:
        assert actual_classified_runs[key] == expected_classified_runs[key]

    # Assert the compare function passed
    assert actual_compare_func == compare_func

    # Assert the summary file path object returned by the patched summary_path
    expected_summary_path_obj = analysis.analyse.summary_path(
        expected_check_name, version_to_check
    )
    assert actual_summary_file == expected_summary_path_obj


# --- Remaining Test: check_for_same_version (v7.28.4) ---
@patch(
    "analysis.analyse.create_or_clear_summary_directory_for"
)  # Keep patched even if not asserted
def test_check_for_same_version_v28(mock_create_or_clear, common_patches):
    """
    Tests check_for_same_version with version v7.28.4.
    Verifies correct classification and call to are_classified_runs_consistent.
    """
    version_to_check = "v7.28.4"
    compare_func = dummy_check_version_28
    mock_are_consistent = common_patches["are_classified_runs_consistent"]
    mock_path_class = common_patches["Path"]

    # Expected classified_runs for v7.28.4 from TEST_TARFILES
    # Manually filter and classify based on the function's logic (matching any 'alph' or 'ctime')
    v28_tarfiles = [f for f in TEST_TARFILES if version_to_check in f]

    expected_classified_runs = {
        "alphabetically sorted": SortedRuns(
            True, [f for f in v28_tarfiles if "alph" in f and "sort" in f]
        ),
        "alphabetically reverse sorted": SortedRuns(
            True, [f for f in v28_tarfiles if "alph" in f and "reverse" in f]
        ),
        "ctime sorted": SortedRuns(
            True, [f for f in v28_tarfiles if "ctime" in f and "sort" in f]
        ),
        "ctime reverse sorted": SortedRuns(
            True, [f for f in v28_tarfiles if "ctime" in f and "reverse" in f]
        ),
        "without disorderfs": SortedRuns(
            True,
            [
                f
                for f in v28_tarfiles
                if all(key not in f for key in ("alph", "ctime", "sort", "reverse"))
            ],
        ),
    }
    expected_classified_runs = {
        k: v for k, v in expected_classified_runs.items() if v.runs
    }

    expected_check_name = MOCK_COMPARE_TO_CHECK_NAME_MAP[compare_func]
    expected_summary_filename = f"{version_to_check}.json"

    # Call the function under test
    check_for_same_version(version_to_check, TEST_TARFILES, compare_func)

    # Assertions
    summary_mock_path_instance = get_summary_mock_path(
        mock_path_class, expected_summary_filename
    )
    assert (
        summary_mock_path_instance is not None
    ), f"Summary file {expected_summary_filename} was not created"
    summary_mock_path_instance.write_text.assert_called_once_with("{}")

    mock_are_consistent.assert_called_once()
    actual_classified_runs, actual_compare_func, actual_summary_file = (
        mock_are_consistent.call_args[0]
    )

    assert actual_classified_runs.keys() == expected_classified_runs.keys()
    for key in expected_classified_runs:
        assert actual_classified_runs[key] == expected_classified_runs[key]

    assert actual_compare_func == compare_func
    expected_summary_path_obj = analysis.analyse.summary_path(
        expected_check_name, version_to_check
    )
    assert actual_summary_file == expected_summary_path_obj


# --- Remaining Test: check_for_same_params (dfs=False - vanilla) ---
@patch(
    "analysis.analyse.create_or_clear_summary_directory_for"
)  # Keep patched even if not asserted
@patch("analysis.analyse.all_versions")
@patch("analysis.analyse._tarfiles_with_params")
def test_check_for_same_params_vanilla_dfs_false(
    mock__tarfiles_with_params, mock_all_versions, mock_create_or_clear, common_patches
):
    """
    Tests check_for_same_params with dfs=False (vanilla).
    Verifies correct filtering, classification by version, and call are_classified_runs_consistent.
    """
    compare_func = dummy_check_version_28
    mock_are_consistent = common_patches["are_classified_runs_consistent"]
    mock_path_class = common_patches["Path"]

    # Define the parameters for the check
    params = {"dfs": False}  # Vanilla case

    # Mock all_versions
    all_distinct_versions = sorted(
        list(
            set(
                [
                    v
                    for v, _ in [
                        analysis.analyse.version_and_run_from_tar_filename(f)
                        for f in TEST_TARFILES
                    ]
                    if v is not None
                ]
            )
        )
    )
    mock_all_versions.return_value = all_distinct_versions

    # Manual filtering for dfs=False based on _tarfiles_with_params logic
    # Logic: files where none of ("alph", "ctime", "sort", "reverse") are in the name.
    relevant_tarfiles_for_params = [
        f
        for f in TEST_TARFILES
        if all(key not in f for key in ("alph", "ctime", "sort", "reverse"))
    ]
    mock__tarfiles_with_params.configure_mock(return_value=relevant_tarfiles_for_params)

    # Expected classified_runs structure based on versions and relevant_tarfiles_for_params
    expected_classified_runs = {}
    for version in mock_all_versions.return_value:
        files_for_this_version = [
            f for f in relevant_tarfiles_for_params if version in f
        ]
        if files_for_this_version:
            expected_classified_runs[version] = SortedRuns(True, files_for_this_version)

    # Expected description string
    expected_description = analysis.analyse.description_from_params(
        **params
    )  # "without disorderfs"

    expected_check_name = MOCK_COMPARE_TO_CHECK_NAME_MAP[compare_func]
    expected_summary_filename = f"{expected_description}.json"

    # Call the function under test
    check_for_same_params(TEST_TARFILES, compare_func, **params)

    # Assertions
    mock_all_versions.assert_called_once()
    # Check _tarfiles_with_params was called with the correct parameters
    # For dfs=False, _tarfiles_with_params is called only with dfs=False.
    mock__tarfiles_with_params.assert_called_once_with(
        False, alph=None, ctime=None, reverse=None, sort=True
    )

    summary_mock_path_instance = get_summary_mock_path(
        mock_path_class, expected_summary_filename
    )
    assert (
        summary_mock_path_instance is not None
    ), f"Summary file {expected_summary_filename} was not created"
    summary_mock_path_instance.write_text.assert_called_once_with("{}")

    mock_are_consistent.assert_called_once()
    actual_classified_runs, actual_compare_func, actual_summary_file = (
        mock_are_consistent.call_args[0]
    )

    assert actual_classified_runs.keys() == expected_classified_runs.keys()
    for key in expected_classified_runs:
        assert actual_classified_runs[key] == expected_classified_runs[key]

    assert actual_compare_func == compare_func
    expected_summary_path_obj = analysis.analyse.summary_path(
        expected_check_name, expected_description
    )
    assert actual_summary_file == expected_summary_path_obj


# --- Remaining Tests: check_for_same_params (dfs=True, other combinations) ---


@pytest.mark.parametrize(
    "params, expected_description",
    [
        (
            {"dfs": True, "alph": True, "ctime": False, "reverse": False},
            "alphabetically sorted",
        ),
        (
            {"dfs": True, "alph": True, "ctime": False, "reverse": True},
            "alphabetically reverse sorted",
        ),
        ({"dfs": True, "alph": False, "ctime": True, "reverse": False}, "ctime sorted"),
        (
            {"dfs": True, "alph": False, "ctime": True, "reverse": True},
            "ctime reverse sorted",
        ),
    ],
    ids=[
        "alph_sort",
        "alph_reverse",
        "ctime_sort",
        "ctime_reverse",
    ],  # Easier test names
)
@patch(
    "analysis.analyse.create_or_clear_summary_directory_for"
)  # Keep patched even if not asserted
@patch("analysis.analyse.all_versions")
@patch("analysis.analyse._tarfiles_with_params")
def test_check_for_same_params_dfs_combinations(
    mock__tarfiles_with_params,
    mock_all_versions,
    mock_create_or_clear,
    common_patches,
    params,
    expected_description,
):
    """
    Tests check_for_same_params for the different dfs=True parameter combinations.
    Uses parametrizing to run the same test logic with different inputs.
    """
    compare_func = dummy_check_version_28
    mock_are_consistent = common_patches["are_classified_runs_consistent"]
    mock_path_class = common_patches["Path"]

    all_distinct_versions = sorted(
        list(
            set(
                [
                    v
                    for v, _ in [
                        analysis.analyse.version_and_run_from_tar_filename(f)
                        for f in TEST_TARFILES
                    ]
                    if v is not None
                ]
            )
        )
    )
    mock_all_versions.return_value = all_distinct_versions

    # --- CORRECTED Manual Filtering for dfs=True based on _tarfiles_with_params logic ---
    # This logic MUST match the actual filtering in _tarfiles_with_params exactly for the test to pass.
    # The original _tarfiles_with_params logic for dfs=True does NOT check for the "dfstest" prefix.
    # It checks if the file contains the string associated with the active sorting flag ('alph' or 'ctime')
    # AND if it contains the string associated with the active direction ('sort' or 'reverse').

    dfs = params.get("dfs", False)  # Always True in this test
    alph = params.get("alph", False)
    ctime = params.get("ctime", False)
    reverse = params.get("reverse", False)
    sort = not reverse  # Derived as in _tarfiles_with_params

    relevant_tarfiles_for_params = []
    for tarfile in TEST_TARFILES:
        if dfs:  # This branch is always taken in this test
            # Check the first condition: (alph is True AND "alph" in name) OR (ctime is True AND "ctime" in name)
            condition1_matches = (alph and "alph" in tarfile) or (
                ctime and "ctime" in tarfile
            )

            # Check the second condition: (reverse is True AND "reverse" in name) OR (sort is True AND "sort" in name)
            condition2_matches = (reverse and "reverse" in tarfile) or (
                sort and "sort" in tarfile
            )

            # In _tarfiles_with_params, if condition1 and condition2 are both true, the file is included.
            # The mutual exclusion (alph vs. ctime) is implicitly handled by the flags and string checks.
            if condition1_matches and condition2_matches:
                relevant_tarfiles_for_params.append(tarfile)

    mock__tarfiles_with_params.configure_mock(return_value=relevant_tarfiles_for_params)

    # Expected classified_runs structure based on versions and relevant_tarfiles_for_params
    expected_classified_runs = {}
    for version in mock_all_versions.return_value:
        files_for_this_version = [
            f for f in relevant_tarfiles_for_params if version in f
        ]
        if files_for_this_version:
            expected_classified_runs[version] = SortedRuns(True, files_for_this_version)

    expected_check_name = MOCK_COMPARE_TO_CHECK_NAME_MAP[compare_func]
    expected_summary_filename = f"{expected_description}.json"

    # Call the function under test
    check_for_same_params(TEST_TARFILES, compare_func, **params)

    # Assertions
    mock_all_versions.assert_called_once()

    # Check _tarfiles_with_params was called with the correct parameters
    expected_params_for__tarfiles = params.copy()
    del expected_params_for__tarfiles["dfs"]  # dfs is passed positionally
    # _tarfiles_with_params adds/defaults these if dfs=True
    expected_params_for__tarfiles["sort"] = not expected_params_for__tarfiles.get(
        "reverse", False
    )
    expected_params_for__tarfiles["alph"] = expected_params_for__tarfiles.get(
        "alph", False
    )
    expected_params_for__tarfiles["ctime"] = expected_params_for__tarfiles.get(
        "ctime", False
    )
    expected_params_for__tarfiles["reverse"] = expected_params_for__tarfiles.get(
        "reverse", False
    )

    mock__tarfiles_with_params.assert_called_once_with(
        True, **expected_params_for__tarfiles
    )  # Call matches signature

    summary_mock_path_instance = get_summary_mock_path(
        mock_path_class, expected_summary_filename
    )
    assert (
        summary_mock_path_instance is not None
    ), f"Summary file {expected_summary_filename} was not created"
    summary_mock_path_instance.write_text.assert_called_once_with("{}")

    mock_are_consistent.assert_called_once()
    actual_classified_runs, actual_compare_func, actual_summary_file = (
        mock_are_consistent.call_args[0]
    )

    assert actual_classified_runs.keys() == expected_classified_runs.keys()
    for key in expected_classified_runs:
        assert actual_classified_runs[key] == expected_classified_runs[key]

    assert actual_compare_func == compare_func
    expected_summary_path_obj = analysis.analyse.summary_path(
        expected_check_name, expected_description
    )
    assert actual_summary_file == expected_summary_path_obj
