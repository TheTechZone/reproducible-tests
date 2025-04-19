import pytest
import json
from pathlib import Path
from setup.structure import (
    turn_cvc_code_mapping_to_json,
    parameters_from_tar_filename,
    version_and_run_from_tar_filename,
)


@pytest.mark.parametrize(
    "input_lines, expected_output",
    [
        # Test A
        (
            "blub: meow\n10: 5\ngrump: 8.36.2",
            {
                "blub": "meow",
                "meow": "blub",
                "10": "5",
                "5": "10",
                "grump": "8.36.2",
                "8.36.2": "grump",
            },
        ),
        # Test B (empty input)
        ("", {}),
        # Test C (one mapping)
        (
            "1297ayg18k: meep",
            {"1297ayg18k": "meep", "meep": "1297ayg18k"},
        ),
    ],
)
def test_turn_cvc_code_mapping_to_json_parametrized(
    input_lines, expected_output, tmp_path: Path, monkeypatch
):
    # Arrange: prepare mock paths and files
    mock_root = tmp_path
    input_file = mock_root / "versioncode-tags-mapping.txt"
    output_file = mock_root / "versioncode-tags-mapping.json"
    input_file.write_text(input_lines)

    # Monkeypatch the module-level constants used in the function
    monkeypatch.setattr("setup.structure.PLAYSTORE_APKS_ROOT", mock_root)
    monkeypatch.setattr("setup.structure.VERSION_CVC_FILE", output_file)

    # Act
    turn_cvc_code_mapping_to_json()

    # Assert
    with output_file.open("r", encoding="utf-8") as f:
        result = json.load(f)
    assert result == expected_output


@pytest.mark.parametrize(
    "filename, expected",
    [
        # A:
        (
            "dfstest-signal-android-ctime-reversed_v7.28.4.tar.gz",
            ("7.28.4", 1, True, True, True, True),
        ),
        # B:
        (
            "signal-android_v8.36.2.tar.gz",
            ("8.36.2", 1, False, False, None, None),
        ),
        # C:
        (
            "blubblub-ctime-sort_v1.2.3.tar.gz",
            ("1.2.3", 1, False, True, True, False),
        ),
        # D:
        (
            "dfstest-alph-reversed_v9.8.7",
            (
                "9.8.7",
                1,
                True,
                True,
                False,
                True,
            ),  # This expected output might need fixing?
        ),
        # E:
        (
            "signal-android_v9.0.2_00309.tar.gz",
            ("9.0.2", 309, False, False, None, None),
        ),
    ],
)
def test_parameters_from_tar_filename(filename, expected):
    assert parameters_from_tar_filename(filename) == expected


@pytest.mark.parametrize(
    "filename, expected",
    [
        # A:
        (
            "dfstest-signal-android-ctime-reversed_v7.28.4.tar.gz",
            ("7.28.4", 1),
        ),
        # B:
        (
            "signal-android_v8.36.2.tar.gz",
            ("8.36.2", 1),
        ),
        # C:
        (
            "blubblub-ctime-sort_v1.2.3.tar.gz",
            ("1.2.3", 1),
        ),
        # D:
        (
            "dfstest-alph-reversed_v9.8.7",
            ("9.8.7", 1),
        ),
        # E:
        (
            "signal-android_v9.0.2_00309.tar.gz",
            ("9.0.2", 309),
        ),
        # F:
        (
            "Blubblub-meowmeow-grump.tar.gz",
            (None, None),  # In case the format doesn't match
        ),
    ],
)
def test_version_and_run_from_tar_filename(filename, expected):
    assert version_and_run_from_tar_filename(filename) == expected
