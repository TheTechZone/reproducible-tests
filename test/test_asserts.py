import pytest
import json

from src.analysis import _differences, _get_metadata_list


@pytest.mark.parametrize(
    "list1, list2, expected_result",
    [
        # A: both lists are empty
        ([], [], []),
        # B: both lists contain the same element
        ([3], [3], []),
        # C: lists with differences in the second element
        ([1, 4, 2, 5], [1, 3, 2, 5], ["4 -> 3\n"]),
        # D: lists with nested structures
        (
            [[1, 2, 3], 5, "blub", ["meow", "meep", "grump", 5]],
            [[1, 2, 5], 5, "blub", ["meow", "meep", "grump", 5]],
            ["[1, 2, 3] -> [1, 2, 5]\n"],
        ),
    ],
)
def test_differences(list1, list2, expected_result):
    result = _differences(list1, list2)
    assert result == expected_result


@pytest.mark.parametrize(
    "tarfile_name, file_contents, expected",
    [
        # A: Empty elements
        (
            "runA",
            {"runA": {"output-metadata.json": json.dumps({"elements": []})}},
            [],
        ),
        # B: Single element
        (
            "runB",
            {
                "runB": {
                    "output-metadata.json": json.dumps(
                        {"elements": [{"type": "file", "outputFile": "myFile.meep"}]}
                    )
                }
            },
            ["myFile.meep"],
        ),
        # C: Two elements
        (
            "runC",
            {
                "runC": {
                    "output-metadata.json": json.dumps(
                        {
                            "elements": [
                                {"type": "file", "outputFile": "myFile.meep"},
                                {"attributes": [], "outputFile": "myFile.grump"},
                            ]
                        }
                    )
                }
            },
            ["myFile.meep", "myFile.grump"],
        ),
        # D: Full realistic metadata blob
        (
            "signal-android_v7.30.2.tar.gz",
            {
                "signal-android_v7.30.2.tar.gz": {
                    "mtimes": "irrelevant here",
                    "output-metadata.json": json.dumps(
                        {
                            "version": 3,
                            "artifactType": {
                                "type": "LINKED_RESOURCES_BINARY_FORMAT",
                                "kind": "Directory",
                            },
                            "applicationId": "org.thoughtcrime.securesms",
                            "variantName": "playProdRelease",
                            "elements": [
                                {
                                    "outputFile": "linked-resources-binary-format-playProdUniversalRelease.ap_"
                                },
                                {
                                    "outputFile": "linked-resources-binary-format-playProdX86_64Release.ap_"
                                },
                                {
                                    "outputFile": "linked-resources-binary-format-playProdArm64-v8aRelease.ap_"
                                },
                                {
                                    "outputFile": "linked-resources-binary-format-playProdX86Release.ap_"
                                },
                                {
                                    "outputFile": "linked-resources-binary-format-playProdArmeabi-v7aRelease.ap_"
                                },
                            ],
                            "elementType": "File",
                        }
                    ),
                }
            },
            [
                "linked-resources-binary-format-playProdUniversalRelease.ap_",
                "linked-resources-binary-format-playProdX86_64Release.ap_",
                "linked-resources-binary-format-playProdArm64-v8aRelease.ap_",
                "linked-resources-binary-format-playProdX86Release.ap_",
                "linked-resources-binary-format-playProdArmeabi-v7aRelease.ap_",
            ],
        ),
    ],
)
def test_get_metadata_list(
    tmp_path, tarfile_name, file_contents, expected, monkeypatch
):
    fake_data_root = tmp_path
    fake_file_path = fake_data_root / "res" / "output_metadata_mtimes.json"
    fake_file_path.parent.mkdir(parents=True, exist_ok=True)

    # Write the mock data
    with fake_file_path.open("w") as f:
        json.dump(file_contents, f)

    # Patch DATA_ROOT inside your module
    import src.analysis.checks

    monkeypatch.setattr(src.analysis.checks, "DATA_ROOT", tmp_path)

    # Run the actual test
    result = _get_metadata_list(tarfile_name)
    assert result == expected
