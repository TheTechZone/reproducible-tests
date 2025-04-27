import pytest
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from analysis.analyse import (
    are_classified_runs_consistent,
    SortedRuns,
    assemble_consistent_tarfile_list,
    all_versions,
    _tarfiles_with_params,
)


# --- Dummy checks ---


def dummy_check_nothing_consistent(_):
    return False  # , [tarfile]


def dummy_check_everything_consistent(_):
    return True  # , []


def dummy_check_version_28(tarfile):
    return "v7.28" in tarfile


# --- Dummy tar files for mocking ---
dummy_tarfiles = [
    "dfstest-signal-android-ctime-reversed_v7.28.4_01.tar.gz",
    "dfstest-signal-android-ctime-reversed_v7.28.4_02.tar.gz",
    "dfstest-signal-android-ctime-sort_v7.28.4_01.tar.gz",
    "dfstest-signal-android-ctime-sort_v7.28.4_02.tar.gz",
    "signal-android-ctime-reversed_v7.28.4_01.tar.gz",
    "signal-android-ctime-reversed_v7.28.4_02.tar.gz",
    "signal-android-ctime-reversed_v7.28.4_03.tar.gz",
    "signal-android-ctime-sort_v7.28.4.tar.gz",
    "signal-android-ctime-reversed_v7.30.4_01.tar.gz",
    "signal-android-ctime-sort_v7.30.4.tar.gz",
]

# --- Expected output for parameterized tests ---

expected_all = dummy_tarfiles
expected_none = []
expected_28 = [
    "dfstest-signal-android-ctime-reversed_v7.28.4_01.tar.gz",
    "dfstest-signal-android-ctime-reversed_v7.28.4_02.tar.gz",
    "dfstest-signal-android-ctime-sort_v7.28.4_01.tar.gz",
    "dfstest-signal-android-ctime-sort_v7.28.4_02.tar.gz",
    "signal-android-ctime-reversed_v7.28.4_01.tar.gz",
    "signal-android-ctime-reversed_v7.28.4_02.tar.gz",
    "signal-android-ctime-reversed_v7.28.4_03.tar.gz",
    "signal-android-ctime-sort_v7.28.4.tar.gz",
]


# --- Patch TARS_ROOT.iterdir to simulate the files ---
@pytest.fixture
def mock_tarfiles():
    mock_path = MagicMock()
    mock_path.iterdir.return_value = [Path(name) for name in dummy_tarfiles]
    return mock_path


# --- Import the function under test ---
# from analysis.analyse import assemble_consistent_tarfile_list  # replace `your_module`


# --- Parametrized Test ---
@pytest.mark.parametrize(
    "check_fn, expected",
    [
        (dummy_check_nothing_consistent, []),
        (dummy_check_everything_consistent, dummy_tarfiles),
        (dummy_check_version_28, [f for f in dummy_tarfiles if "v7.28" in f]),
    ],
)
@patch("analysis.analyse.TARS_ROOT", new_callable=lambda: Path("/fake/tars"))
@patch("pathlib.Path.iterdir")
def test_assemble_consistent_tarfile_list(
    mock_iterdir, mock_tars_root, check_fn, expected
):
    # Return Path objects when iterdir is called
    mock_iterdir.return_value = [Path(f"/fake/tars/{f}") for f in dummy_tarfiles]

    result = assemble_consistent_tarfile_list(check_fn)

    # Only the filename (name attribute) matters in the function
    assert sorted(result) == sorted(expected)


def dummy_comparator_nothing_consistent(t1: str, t2: str):
    return True, [f"{t1}:{t2}"]


def dummy_comparator_everything_consistent(_: str, __: str):
    return False, []


def dummy_comparator_version_28(t1: str, t2: str):
    is_not_28 = False
    diff = []
    if "v7.28" not in t1:
        diff.append(t1)
        is_not_28 = True
    if "v7.28" not in t2:
        diff.append(t2)
        is_not_28 = True
    return is_not_28, diff


@pytest.mark.parametrize(
    "check_fn, initial, expected",
    [
        # Case A
        (
            dummy_comparator_nothing_consistent,
            {
                "1-run": SortedRuns(True, ["example_v7.16.256.tar.gz"]),
                "multiple-runs": SortedRuns(
                    True, ["example_v7.1.2_01.tar.gz", "example_v7.1.2_02.tar.gz"]
                ),
                "no-runs": SortedRuns(True, []),
            },
            {
                "1-run": SortedRuns(True, ["example_v7.16.256.tar.gz"]),
                "multiple-runs": SortedRuns(
                    False, ["example_v7.1.2_01.tar.gz", "example_v7.1.2_02.tar.gz"]
                ),
                "no-runs": SortedRuns(True, []),
            },
        ),
        # Case B
        (
            dummy_comparator_everything_consistent,
            {
                "1-run": SortedRuns(True, ["example_v7.16.256.tar.gz"]),
                "multiple-runs": SortedRuns(
                    True, ["example_v7.1.2_01.tar.gz", "example_v7.1.2_02.tar.gz"]
                ),
                "no-runs": SortedRuns(True, []),
            },
            {
                "1-run": SortedRuns(True, ["example_v7.16.256.tar.gz"]),
                "multiple-runs": SortedRuns(
                    True, ["example_v7.1.2_01.tar.gz", "example_v7.1.2_02.tar.gz"]
                ),
                "no-runs": SortedRuns(True, []),
            },
        ),
        # Case C
        (
            dummy_comparator_version_28,
            {
                "1-run": SortedRuns(True, ["example_v7.16.256.tar.gz"]),
                "no-runs": SortedRuns(True, []),
                "all v_28": SortedRuns(
                    True,
                    [
                        "example_v7.28.1.tar.gz",
                        "example_v7.28.1_02.tar.gz",
                        "example_v7.28.1_03.tar.gz",
                    ],
                ),
                "all but one v_28": SortedRuns(
                    True,
                    [
                        "example_v7.28.1.tar.gz",
                        "example_v7.29.1_02.tar.gz",
                        "example_v7.28.1_03.tar.gz",
                    ],
                ),
            },
            {
                "1-run": SortedRuns(True, ["example_v7.16.256.tar.gz"]),
                "no-runs": SortedRuns(True, []),
                "all v_28": SortedRuns(
                    True,
                    [
                        "example_v7.28.1.tar.gz",
                        "example_v7.28.1_02.tar.gz",
                        "example_v7.28.1_03.tar.gz",
                    ],
                ),
                "all but one v_28": SortedRuns(
                    False,
                    [
                        "example_v7.28.1.tar.gz",
                        "example_v7.29.1_02.tar.gz",
                        "example_v7.28.1_03.tar.gz",
                    ],
                ),
            },
        ),
    ],
)
def test_are_classified_runs_consistent(check_fn, initial, expected):
    are_classified_runs_consistent(initial, check_fn)
    assert initial == expected


@pytest.mark.parametrize(
    "tar_filenames, expected_versions",
    [
        (
            [
                "signal-android_v7.1.2.tar.gz",
                "dfstest-signal-android-ctime-reversed_v7.1.3_01.tar.gz",
                "dfstest-signal-android-ctime-sort.v7.1.3_02.tar.gz",
                "signal-android-alph-reversed_v7.1.22_04.tar.gz",
                "signal-android-alph-sort_v7.1.1.tar.gz",
                "signal-android-ctime-sort_v7.1.2.tar.gz",
                "signal-android_v7.1.2_02.tar.gz",
            ],
            ["7.1.1", "7.1.2", "7.1.22", "7.1.3"],
        ),
    ],
)
def test_get_all_versions(
    tmp_path: Path, monkeypatch, tar_filenames, expected_versions
):
    # Set up fake tar files in the temp directory
    for file in tar_filenames:
        (tmp_path / file).touch()

    # Patch the location where TARS_ROOT is defined in the target module
    monkeypatch.setattr("analysis.analyse.TARS_ROOT", tmp_path)

    versions = all_versions()
    assert sorted(versions) == sorted(expected_versions)


@pytest.mark.parametrize(
    "kwargs, expected_files",
    [
        # A
        ({"dfs": True}, set()),
        # B
        (
            {"dfs": False},
            {"signal-android_v7.1.2.tar.gz", "signal-android_v7.1.2_02.tar.gz"},
        ),
        # C
        ({"dfs": True, "ctime": True}, set()),
        # C - inverse
        (
            {"dfs": True, "ctime": True, "reverse": True, "sort": True},
            {
                "dfstest-signal-android-ctime-reversed_v7.1.3_01.tar.gz",
                "dfstest-signal-android-ctime-sort.v7.1.3_02.tar.gz",
                "signal-android-ctime-sort_v7.1.2.tar.gz",
            },
        ),
        # D -- -BORKED
        (
            {"dfs": True, "reverse": True},
            {
                "dfstest-signal-android-ctime-reversed_v7.1.3_01.tar.gz",
                "dfstest-signal-android-ctime-sort.v7.1.3_02.tar.gz",
                "signal-android-ctime-sort_v7.1.2.tar.gz",
            },
        ),
        # E -- BORKED
        (
            {"dfs": True, "sort": True},
            {
                "dfstest-signal-android-ctime-sort.v7.1.3_02.tar.gz",
                "signal-android-alph-sort_v7.1.1.tar.gz",
                "signal-android-ctime-sort_v7.1.2.tar.gz",
            },
        ),
        # F
        (
            {"dfs": True, "sort": True, "alph": True},
            {"signal-android-alph-sort_v7.1.1.tar.gz"},
        ),
        # G
        (
            {"dfs": True, "reverse": True, "alph": True},
            {"signal-android-alph-reversed_v7.1.22_04.tar.gz"},
        ),
        # H
        (
            {"dfs": True, "reverse": True, "ctime": True},
            {"dfstest-signal-android-ctime-reversed_v7.1.3_01.tar.gz"},
        ),
        # I / J
        (
            {"dfs": True, "sort": True, "ctime": True},
            {
                "dfstest-signal-android-ctime-sort.v7.1.3_02.tar.gz",
                "signal-android-ctime-sort_v7.1.2.tar.gz",
            },
        ),
        # K -- BORKEEEEEEED!
        (
            {"dfs": True, "sort": True, "ctime": True, "alph": True},
            {
                "dfstest-signal-android-ctime-sort.v7.1.3_02.tar.gz",
                "signal-android-ctime-sort_v7.1.2.tar.gz",
            },
        ),
        # L
        (
            {"dfs": True, "sort": True, "reverse": True, "ctime": True, "alph": True},
            {
                "dfstest-signal-android-ctime-reversed_v7.1.3_01.tar.gz",
                "dfstest-signal-android-ctime-sort.v7.1.3_02.tar.gz",
                "signal-android-alph-reversed_v7.1.22_04.tar.gz",
                "signal-android-alph-sort_v7.1.1.tar.gz",
                "signal-android-ctime-sort_v7.1.2.tar.gz",
            },
        ),
        # M
        (
            {"dfs": False, "sort": True, "reverse": True, "ctime": True, "alph": True},
            {"signal-android_v7.1.2.tar.gz", "signal-android_v7.1.2_02.tar.gz"},
        ),
    ],
)
def test_tarfiles_with_params(tmp_path, monkeypatch, kwargs, expected_files):
    # Create fake files in the temp dir
    filenames = [
        "signal-android_v7.1.2.tar.gz",
        "dfstest-signal-android-ctime-reversed_v7.1.3_01.tar.gz",
        "dfstest-signal-android-ctime-sort.v7.1.3_02.tar.gz",
        "signal-android-alph-reversed_v7.1.22_04.tar.gz",
        "signal-android-alph-sort_v7.1.1.tar.gz",
        "signal-android-ctime-sort_v7.1.2.tar.gz",
        "signal-android_v7.1.2_02.tar.gz",
    ]
    for fname in filenames:
        (tmp_path / fname).touch()

    monkeypatch.setattr("analysis.analyse.TARS_ROOT", tmp_path)

    result = _tarfiles_with_params(**kwargs)
    result_names = {f for f in result}

    assert result_names == expected_files
