import pytest
from unittest import mock
from pathlib import Path
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from analysis import aggregation


# --- Pytest Fixtures ---


@pytest.fixture
def mock_version_cvc_file(tmp_path):
    """Creates a temporary VERSION_CVC_FILE for testing."""
    data = {
        # For get_version (CVC -> SemVer)
        "50000": "v5.0.0",
        "51000": "v5.1.0",
        "60102": "v6.1.2-beta",
        "7080903": "v7.8.9-beta.3",
        # For get_cvc (SemVer (no 'v' prefix by default lookup) -> CVC)
        # The get_cvc function will strip 'v' from input "vX.Y.Z" to "X.Y.Z" before lookup
        "5.0.0": "50000",
        "5.1.0": "51000",
        "6.1.2-beta": "60102",  # Added for completeness, though not in original failing test
        "7.8.9-beta.3": "7080903",
    }
    version_file = tmp_path / "version_cvc.json"
    with open(version_file, "w") as f:
        json.dump(data, f)
    return version_file


@pytest.fixture
def mock_build_gradle_kts_dir(tmp_path):
    """Creates a mock directory structure for CB_PATH and a build.gradle.kts file."""
    mock_cb_root = tmp_path / "mock_codebase"
    app_dir = mock_cb_root / "app"
    app_dir.mkdir(parents=True, exist_ok=True)
    gradle_file = app_dir / "build.gradle.kts"
    content = """
    dependencies {
        // some dependencies
    }
    android {
        // compileSdk = 33
    }
    // A comment
    val canonicalVersionCode = 70809
    // Another comment
    val propertyNotUsed = "test"
    val currentHotfixVersion = 3
    """
    gradle_file.write_text(content)
    return mock_cb_root


# --- Helper for Mocking Plumbum Commands ---


def create_mock_plumbum_cmd(stdout="", stderr="", retcode=0, is_run_method=False):
    """
    Creates a mock structure for a plumbum command.
    Handles cmd[args...]() and cmd[args...].run() patterns.
    """
    cmd_mock = mock.MagicMock(name="PlumbumCmdMock")
    # This mock represents the object after arguments are applied, e.g., local["ls"]["-l"]
    final_executable_mock = mock.MagicMock(name="FinalExecutablePlumbumCmdMock")

    if is_run_method:
        final_executable_mock.run.return_value = (retcode, stdout, stderr)
    else:
        # Handles the cmd() case
        final_executable_mock.return_value = stdout

    # When cmd_mock["arg"] is called, it returns the final_executable_mock
    cmd_mock.__getitem__.return_value = final_executable_mock

    # If the command is called directly without __getitem__ (e.g. local["cmd"]())
    if is_run_method:
        cmd_mock.run.return_value = (retcode, stdout, stderr)
    else:
        cmd_mock.return_value = stdout

    return cmd_mock


# --- Tests for Version/CVC retrieval ---


def test_get_version_exists(mock_version_cvc_file, monkeypatch):
    monkeypatch.setattr(aggregation, "VERSION_CVC_FILE", mock_version_cvc_file)
    assert aggregation.get_version("50000") == "v5.0.0"
    assert aggregation.get_version("60102") == "v6.1.2-beta"


def test_get_version_not_exists(mock_version_cvc_file, monkeypatch):
    monkeypatch.setattr(aggregation, "VERSION_CVC_FILE", mock_version_cvc_file)
    assert aggregation.get_version("00000") is None


def test_get_cvc_exists(mock_version_cvc_file, monkeypatch):
    monkeypatch.setattr(aggregation, "VERSION_CVC_FILE", mock_version_cvc_file)
    assert aggregation.get_cvc("v5.1.0") == "51000"
    assert aggregation.get_cvc("5.0.0") == "50000"  # Handles missing 'v'


def test_get_cvc_not_exists(mock_version_cvc_file, monkeypatch):
    monkeypatch.setattr(aggregation, "VERSION_CVC_FILE", mock_version_cvc_file)
    assert aggregation.get_cvc("v0.0.0") is None


# --- Tests for Clearing Functions ---


def test_clear_untared_folder_exists(tmp_path, monkeypatch):
    mock_cb_path = tmp_path / "codebase_to_clear"
    mock_cb_path.mkdir()
    monkeypatch.setattr(aggregation, "CB_PATH", mock_cb_path)

    mock_rm_cmd = create_mock_plumbum_cmd()
    with mock.patch("analysis.aggregation.local") as mock_local:
        mock_local.__getitem__.return_value = mock_rm_cmd  # Handles local["rm"]

        aggregation._clear_untared_folder()

        mock_local.__getitem__.assert_called_once_with("rm")
        mock_rm_cmd.__getitem__.assert_called_once_with(("-r", str(mock_cb_path)))
        mock_rm_cmd.__getitem__.return_value.assert_called_once_with()
        # We don't assert mock_cb_path.exists() is False because the mock rm doesn't actually delete.
        # The test verifies that the correct `rm` command *would* be called.


def test_clear_untared_folder_not_exists(tmp_path, monkeypatch):
    mock_cb_path = tmp_path / "non_existent_codebase"
    monkeypatch.setattr(
        aggregation, "CB_PATH", mock_cb_path
    )  # This path does not exist

    with mock.patch("analysis.aggregation.local") as mock_local:
        aggregation._clear_untared_folder()
        mock_local.__getitem__.assert_not_called()  # rm should not be called


def test_clear_current_apks(tmp_path, monkeypatch):
    # CB_APKS_PATH is typically BUILDS_ROOT / "apks"
    # For the test, we create a mock path and ensure its parent exists for `mkdir` if it were real.
    mock_apks_path = tmp_path / "builds_root_dummy" / "apks"
    # mock_apks_path.parent.mkdir(parents=True, exist_ok=True) # Not strictly needed as Path.mkdir mock handles it

    monkeypatch.setattr(aggregation, "CB_APKS_PATH", mock_apks_path)

    mock_rm_cmd = create_mock_plumbum_cmd()
    mock_mkdir_cmd = create_mock_plumbum_cmd()

    def local_getitem_side_effect(cmd_name):
        if cmd_name == "rm":
            return mock_rm_cmd
        if cmd_name == "mkdir":
            return mock_mkdir_cmd
        return mock.MagicMock()

    with mock.patch("analysis.aggregation.local") as mock_local:
        mock_local.__getitem__.side_effect = local_getitem_side_effect
        aggregation._clear_current_apks()

        # Assert rm call: local["rm"]["-r", CB_APKS_PATH]()
        mock_rm_cmd.__getitem__.assert_called_once_with(("-r", mock_apks_path))
        mock_rm_cmd.__getitem__.return_value.assert_called_once_with()

        # Assert mkdir call: local["mkdir"][CB_APKS_PATH]()
        mock_mkdir_cmd.__getitem__.assert_called_once_with(mock_apks_path)
        mock_mkdir_cmd.__getitem__.return_value.assert_called_once_with()


def test_clear(monkeypatch):
    with mock.patch(
        "analysis.aggregation._clear_untared_folder"
    ) as mock_clear_untar, mock.patch(
        "analysis.aggregation._clear_current_apks"
    ) as mock_clear_apks:
        aggregation.clear()
        mock_clear_untar.assert_called_once()
        mock_clear_apks.assert_called_once()


# --- Test for current_cvc ---


def test_current_cvc_normal(mock_build_gradle_kts_dir, monkeypatch):
    monkeypatch.setattr(aggregation, "CB_PATH", mock_build_gradle_kts_dir)

    # Mock for local["cat"]
    mock_cat_cmd_obj = mock.MagicMock(name="CatCmdObj")
    # Mock for local["cat"][<path>]
    cat_cmd_with_path_obj = mock.MagicMock(name="CatCmdWithPathObj")
    mock_cat_cmd_obj.__getitem__.return_value = cat_cmd_with_path_obj

    # Mock for local["grep"]
    mock_grep_cmd_obj = mock.MagicMock(name="GrepCmdObj")

    # Specific instances that local["grep"][<pattern>] should resolve to
    # These are used for identity checks.
    grep_for_cvc_obj = mock.MagicMock(name="GrepObjectForCVC")
    grep_for_hotfix_obj = mock.MagicMock(name="GrepObjectForHotfix")

    def grep_getitem_side_effect(args_tuple):
        pattern = args_tuple
        if "canonicalVersionCode" in pattern:
            return grep_for_cvc_obj
        elif "currentHotfixVersion" in pattern:
            return grep_for_hotfix_obj
        raise AssertionError(
            f"grep_getitem_side_effect: Unexpected grep pattern '{pattern}'"
        )

    mock_grep_cmd_obj.__getitem__.side_effect = grep_getitem_side_effect

    # Mocks for the final piped command object (cat | grep)
    # These will be configured to return specific strings when THEY are called.
    final_cvc_pipe_mock = mock.MagicMock()  # Removed name to simplify
    final_hotfix_pipe_mock = mock.MagicMock()  # Removed name

    # Define what happens when these final pipe mocks are CALLED
    final_cvc_pipe_mock.side_effect = lambda: "val canonicalVersionCode = 70809\n"
    final_hotfix_pipe_mock.side_effect = lambda: "val currentHotfixVersion = 3\n"

    def or_operator_side_effect(grep_obj_passed_to_or):
        # This is the side_effect for cat_cmd_with_path_obj.__or__
        # It should return the appropriate final_pipe_mock.
        if grep_obj_passed_to_or is grep_for_cvc_obj:
            return final_cvc_pipe_mock
        elif grep_obj_passed_to_or is grep_for_hotfix_obj:
            return final_hotfix_pipe_mock
        raise AssertionError(
            f"or_operator_side_effect: Unexpected grep object {grep_obj_passed_to_or!r}. "
            f"Expected {grep_for_cvc_obj!r} or {grep_for_hotfix_obj!r}"
        )

    cat_cmd_with_path_obj.__or__ = mock.MagicMock(side_effect=or_operator_side_effect)

    with mock.patch("analysis.aggregation.local") as mock_local_mgr:

        def local_getitem_router(cmd_name):
            if cmd_name == "cat":
                return mock_cat_cmd_obj
            if cmd_name == "grep":
                return mock_grep_cmd_obj
            raise AssertionError(
                f"local_getitem_router: Unexpected command '{cmd_name}'"
            )

        mock_local_mgr.__getitem__.side_effect = local_getitem_router

        cvc_result = aggregation.current_cvc()
        assert cvc_result == "7080903"

    # Assert that the final pipe mocks were indeed called (meaning routing was correct)
    final_cvc_pipe_mock.assert_called_once()
    final_hotfix_pipe_mock.assert_called_once()


def test_current_cvc_no_hotfix_value(mock_build_gradle_kts_dir, monkeypatch):
    # Setup: Modify gradle file for this specific test case
    gradle_file_path = mock_build_gradle_kts_dir / "app" / "build.gradle.kts"
    gradle_content = "val canonicalVersionCode = 12345\n val currentHotfixVersion =\n"
    gradle_file_path.write_text(gradle_content)
    monkeypatch.setattr(aggregation, "CB_PATH", mock_build_gradle_kts_dir)

    mock_cat_cmd_obj = mock.MagicMock(name="CatCmdObj_NoHotfix")
    cat_cmd_with_path_obj = mock.MagicMock(name="CatCmdWithPathObj_NoHotfix")
    mock_cat_cmd_obj.__getitem__.return_value = cat_cmd_with_path_obj

    mock_grep_cmd_obj = mock.MagicMock(name="GrepCmdObj_NoHotfix")

    grep_for_cvc_obj = mock.MagicMock(name="GrepObjectForCVC_NoHotfix")
    grep_for_hotfix_obj = mock.MagicMock(name="GrepObjectForHotfix_NoHotfix")

    def grep_getitem_side_effect(args_tuple):
        pattern = args_tuple
        if "canonicalVersionCode" in pattern:
            return grep_for_cvc_obj
        elif "currentHotfixVersion" in pattern:
            return grep_for_hotfix_obj
        raise AssertionError(
            f"grep_getitem_side_effect: Unexpected grep pattern '{pattern}'"
        )

    mock_grep_cmd_obj.__getitem__.side_effect = grep_getitem_side_effect

    final_cvc_pipe_mock = mock.MagicMock()
    final_hotfix_pipe_mock = mock.MagicMock()

    final_cvc_pipe_mock.side_effect = lambda: "val canonicalVersionCode = 12345\n"
    final_hotfix_pipe_mock.side_effect = (
        lambda: "val currentHotfixVersion =\n"
    )  # Hotfix value is empty

    def or_operator_side_effect(grep_obj_passed_to_or):
        if grep_obj_passed_to_or is grep_for_cvc_obj:
            return final_cvc_pipe_mock
        elif grep_obj_passed_to_or is grep_for_hotfix_obj:
            return final_hotfix_pipe_mock
        raise AssertionError(
            f"or_operator_side_effect: Unexpected grep object {grep_obj_passed_to_or!r}. "
            f"Expected {grep_for_cvc_obj!r} or {grep_for_hotfix_obj!r}"
        )

    cat_cmd_with_path_obj.__or__ = mock.MagicMock(side_effect=or_operator_side_effect)

    with mock.patch("analysis.aggregation.local") as mock_local_mgr:

        def local_getitem_router(cmd_name):
            if cmd_name == "cat":
                return mock_cat_cmd_obj
            if cmd_name == "grep":
                return mock_grep_cmd_obj
            raise AssertionError(
                f"local_getitem_router: Unexpected command '{cmd_name}'"
            )

        mock_local_mgr.__getitem__.side_effect = local_getitem_router

        cvc_result = aggregation.current_cvc()
        assert cvc_result == "1234500"

    final_cvc_pipe_mock.assert_called_once()
    final_hotfix_pipe_mock.assert_called_once()


# --- Test _update_aggregation_result ---


def test_update_aggregation_result(tmp_path, monkeypatch):
    mock_data_root = tmp_path / "data_root_for_agg"
    res_dir = mock_data_root / "res"
    res_dir.mkdir(parents=True, exist_ok=True)  # Ensure parent directory exists
    monkeypatch.setattr(aggregation, "DATA_ROOT", mock_data_root)

    test_filename = "my_summary.json"
    target_filepath = res_dir / test_filename

    # Case 1: File doesn't exist initially.
    # To make the test pass without SUT changes for FileNotFoundError on read,
    # we ensure the file is present with empty JSON content if it's the first write.
    # Ideally, the SUT's _update_aggregation_result would handle FileNotFoundError gracefully.
    if not target_filepath.exists():
        with open(target_filepath, "w") as f:
            json.dump({}, f)  # Create an empty JSON object

    key1 = "test_run_1"
    value1 = {"info": "data1"}
    # Now call the function, SUT will read the empty {}
    aggregation._update_aggregation_result(test_filename, key1, value1, log=False)

    with open(target_filepath, "r") as f:
        content = json.load(f)
    assert content == {key1: value1}

    # Case 2: File exists (from previous step), should be updated
    key2 = "test_run_2"
    value2 = {"info": "data2"}
    aggregation._update_aggregation_result(test_filename, key2, value2, log=True)

    with open(target_filepath, "r") as f:
        content = json.load(f)
    # The content should now be an update to what was in key1's step
    assert content == {key1: value1, key2: value2}


# --- Test _extract_apks ---


def test_extract_apks_bundle_exists_splits_dont_exist(tmp_path, monkeypatch):
    mock_builds_root = tmp_path / "mock_builds"
    mock_builds_root.mkdir()

    # Mock Paths used by the function
    mock_cb_aab_path = mock.MagicMock(spec=Path, name="MockAABPath")
    mock_cb_aab_path.exists.return_value = True
    mock_cb_aab_path.__str__.return_value = (
        "path/to/bundle.aab"  # For f-string in bundletool command
    )

    mock_cb_splits_path = mock.MagicMock(spec=Path, name="MockSplitsPath")
    mock_cb_splits_path.exists.return_value = (
        False  # Splits path does NOT exist initially
    )

    monkeypatch.setattr(aggregation, "CB_AAB_PATH", mock_cb_aab_path)
    monkeypatch.setattr(aggregation, "CB_SPLITS_PATH", mock_cb_splits_path)
    monkeypatch.setattr(aggregation, "BUILDS_ROOT", mock_builds_root)
    monkeypatch.setattr(aggregation, "BUNDLETOOL_EXE", "path/to/bundletool.jar")

    mock_bundletool_cmd = create_mock_plumbum_cmd()

    with mock.patch("analysis.aggregation.local") as mock_local, mock.patch(
        "analysis.aggregation.os.chdir"
    ) as mock_os_chdir, mock.patch(
        "analysis.aggregation.Path.cwd"
    ) as mock_path_cwd, mock.patch(
        "analysis.aggregation._clear_current_apks"
    ) as mock_clear_current_apks:
        mock_path_cwd.return_value = Path("/original/working/dir")
        mock_local.__getitem__.return_value = (
            mock_bundletool_cmd  # For local[BUNDLETOOL_EXE]
        )

        aggregation._extract_apks()

        mock_cb_aab_path.exists.assert_called_once()
        mock_cb_splits_path.exists.assert_called_once()
        mock_cb_splits_path.mkdir.assert_called_once_with(parents=True)  # mkdir called
        mock_clear_current_apks.assert_not_called()  # Not called if splits didn't exist

        mock_os_chdir.assert_any_call(mock_builds_root)
        mock_os_chdir.assert_any_call(Path("/original/working/dir"))  # Changed back

        # Check bundletool command
        expected_bundletool_args = (
            "build-apks",
            f"--bundle={str(mock_cb_aab_path)}",
            "--output-format=DIRECTORY",
            "--output=apks",
        )
        mock_local.__getitem__.assert_called_with(str(aggregation.BUNDLETOOL_EXE))
        mock_bundletool_cmd.__getitem__.assert_called_once_with(
            expected_bundletool_args
        )
        mock_bundletool_cmd.__getitem__.return_value.assert_called_once_with()


def test_extract_apks_bundle_exists_splits_exist(tmp_path, monkeypatch):
    mock_builds_root = tmp_path / "mock_builds_alt"  # Different name to avoid conflict
    mock_builds_root.mkdir()

    mock_cb_aab_path = mock.MagicMock(spec=Path)
    mock_cb_aab_path.exists.return_value = True
    mock_cb_aab_path.__str__.return_value = "path/to/bundle.aab"

    mock_cb_splits_path = mock.MagicMock(spec=Path)
    mock_cb_splits_path.exists.return_value = True  # Splits path DOES exist

    monkeypatch.setattr(aggregation, "CB_AAB_PATH", mock_cb_aab_path)
    monkeypatch.setattr(aggregation, "CB_SPLITS_PATH", mock_cb_splits_path)
    monkeypatch.setattr(aggregation, "BUILDS_ROOT", mock_builds_root)
    monkeypatch.setattr(aggregation, "BUNDLETOOL_EXE", "path/to/bundletool.jar")

    mock_bundletool_cmd = create_mock_plumbum_cmd()

    with mock.patch("analysis.aggregation.local") as mock_local, mock.patch(
        "analysis.aggregation.os.chdir"
    ), mock.patch("analysis.aggregation.Path.cwd"), mock.patch(
        "analysis.aggregation._clear_current_apks"
    ) as mock_clear_current_apks:
        mock_local.__getitem__.return_value = mock_bundletool_cmd
        aggregation._extract_apks()

        mock_cb_splits_path.mkdir.assert_not_called()  # Not called if splits existed
        mock_clear_current_apks.assert_called_once()  # Called if splits existed


def test_extract_apks_bundle_not_exists(monkeypatch):
    mock_cb_aab_path = mock.MagicMock(spec=Path, name="NonExistentAAB")
    mock_cb_aab_path.exists.return_value = False  # AAB does NOT exist
    monkeypatch.setattr(aggregation, "CB_AAB_PATH", mock_cb_aab_path)

    with mock.patch("builtins.print") as mock_print, pytest.raises(
        SystemExit
    ) as pytest_wrapped_e:
        aggregation._extract_apks()

    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1
    mock_print.assert_any_call(f"{mock_cb_aab_path} \ndoes not exist!!")


# --- Test extract function (higher level) ---
def test_extract_dfs_test_true(tmp_path, monkeypatch):
    filepath_to_extract = "my_archive.tar.gz"
    mock_builds_root = tmp_path / "builds_for_extract"
    mock_builds_root.mkdir()

    # Mock various paths used by 'extract' and its callees
    monkeypatch.setattr(aggregation, "BUILDS_ROOT", mock_builds_root)
    # These are relative paths as used in the source, they don't need to exist in tmp_path
    # unless their .exists() or other methods are called directly.
    mock_dfs_root_path = Path("dfs_root_in_test")
    mock_signal_android_path = mock_dfs_root_path / "Signal-Android"
    mock_cb_path_target = Path("codebase_target_in_test")
    mock_repro_tests_root_to_rm = Path("reproducible-tests_in_test")

    monkeypatch.setattr(aggregation, "DFS_ROOT_PATH", mock_dfs_root_path)
    monkeypatch.setattr(aggregation, "CB_PATH", mock_cb_path_target)  # Target for mv
    monkeypatch.setattr(
        aggregation, "REPRODUCIBLE_TESTS_ROOT", mock_repro_tests_root_to_rm
    )

    # Mocks for plumbum commands
    mock_tar_cmd = create_mock_plumbum_cmd()
    mock_mv_cmd = create_mock_plumbum_cmd()
    mock_rm_cmd_dfs = (
        create_mock_plumbum_cmd()
    )  # Specific for the REPRODUCIBLE_TESTS_ROOT removal

    def local_getitem_side_effect(cmd_name):
        if cmd_name == "tar":
            return mock_tar_cmd
        if cmd_name == "mv":
            return mock_mv_cmd
        if cmd_name == "rm":
            return mock_rm_cmd_dfs  # This will be used for the REPRODUCIBLE_TESTS_ROOT
        return mock.MagicMock()

    with mock.patch("analysis.aggregation.local") as mock_local, mock.patch(
        "analysis.aggregation.os.chdir"
    ) as mock_os_chdir, mock.patch(
        "analysis.aggregation.Path.cwd"
    ) as mock_path_cwd, mock.patch(
        "analysis.aggregation._clear_untared_folder"
    ) as mock_clear_untar, mock.patch(
        "analysis.aggregation._extract_apks"
    ) as mock_extract_apks_call:

        mock_path_cwd.return_value = Path("/original/cwd_for_extract")
        mock_local.__getitem__.side_effect = local_getitem_side_effect

        aggregation.extract(filepath_to_extract, dfs_test=True)

        mock_path_cwd.assert_called_once()

        mock_os_chdir.assert_any_call(str(mock_builds_root))
        mock_os_chdir.assert_any_call(str(Path("/original/cwd_for_extract")))

        mock_clear_untar.assert_called_once()  # Called by extract

        # tar command
        mock_tar_cmd.__getitem__.assert_called_once_with(("-xzf", filepath_to_extract))
        mock_tar_cmd.__getitem__.return_value.assert_called_once_with()

        # mv command (for dfs_test=True)
        mock_mv_cmd.__getitem__.assert_called_once_with(
            (str(mock_signal_android_path), str(mock_cb_path_target))
        )
        mock_mv_cmd.__getitem__.return_value.assert_called_once_with()

        # rm command for REPRODUCIBLE_TESTS_ROOT (for dfs_test=True)
        mock_rm_cmd_dfs.__getitem__.assert_called_once_with(
            ("-r", str(mock_repro_tests_root_to_rm))
        )
        mock_rm_cmd_dfs.__getitem__.return_value.assert_called_once_with()

        mock_extract_apks_call.assert_called_once()


def test_extract_dfs_test_false(tmp_path, monkeypatch):
    filepath_to_extract = "another_archive.tar.gz"
    mock_builds_root = tmp_path / "builds_for_extract_false"
    mock_builds_root.mkdir()

    monkeypatch.setattr(aggregation, "BUILDS_ROOT", mock_builds_root)

    mock_tar_cmd = create_mock_plumbum_cmd()

    # Only tar should be called from the specific commands in `extract` when dfs_test=False
    # _clear_untared_folder might call `rm` but that's mocked separately.
    def local_getitem_side_effect(cmd_name):
        if cmd_name == "tar":
            return mock_tar_cmd
        # Any other call to local[] like "mv" or "rm" (for dfs specific part) should not happen
        # If they do, this will raise an error or return a generic MagicMock which might fail later assertions.
        raise AssertionError(f"local[{cmd_name}] should not be called in this path")

    with mock.patch("analysis.aggregation.local") as mock_local, mock.patch(
        "analysis.aggregation.os.chdir"
    ), mock.patch("analysis.aggregation.Path.cwd"), mock.patch(
        "analysis.aggregation._clear_untared_folder"
    ) as mock_clear_untar, mock.patch(
        "analysis.aggregation._extract_apks"
    ) as mock_extract_apks_call:
        # Ensure that if local is accessed with "mv" or "rm", it's via the side effect or we detect it.
        # A simple way is to ensure only 'tar' is in the expected call list.
        mock_local.__getitem__.side_effect = lambda cmd: (
            mock_tar_cmd if cmd == "tar" else mock.DEFAULT
        )

        aggregation.extract(filepath_to_extract, dfs_test=False)

        mock_clear_untar.assert_called_once()

        mock_local.__getitem__.assert_called_once_with(
            "tar"
        )  # Only tar is expected here directly from extract's logic
        mock_tar_cmd.__getitem__.assert_called_once_with(("-xzf", filepath_to_extract))
        mock_tar_cmd.__getitem__.return_value.assert_called_once_with()

        # Ensure mv and the specific rm for REPRODUCIBLE_TESTS_ROOT were not called.
        # This is implicitly checked by the strict side_effect or by checking mock_local.__getitem__.call_args_list
        # For example, ensure no calls to local["mv"] or local["rm"] happened that were not from _clear_untared_folder

        mock_extract_apks_call.assert_called_once()


# Mock function for creating dex sets
@mock.patch("analysis.aggregation._unzip_playstore_apk")
@mock.patch("analysis.aggregation.os.chdir")
@mock.patch("analysis.aggregation.Path.iterdir")
@mock.patch("analysis.aggregation.local")
def test_create_dex_sets(mock_local, mock_iterdir, mock_chdir, mock_unzip):
    cvc = "10001"

    # Create fake dex files
    fake_dex_files = [Path(f"classes{i}.dex") for i in range(2)]
    mock_iterdir.side_effect = [fake_dex_files, fake_dex_files]  # playstore, then local

    # Stub sha256sum to return a mock callable per file
    def sha256sum_side_effect(file_path):
        file_name = Path(file_path).name
        sha = f"{file_name}_SHA"
        return lambda: f"{sha}  {file_name}"

    sha256sum_mock = mock.MagicMock()
    sha256sum_mock.__getitem__.side_effect = lambda key: sha256sum_side_effect(key)

    # Only allow "sha256sum" access on local
    def local_side_effect(cmd):
        if cmd == "sha256sum":
            return sha256sum_mock
        raise KeyError(f"Unexpected local command accessed: {cmd}")

    mock_local.__getitem__.side_effect = local_side_effect

    result = aggregation.create_dex_sets(cvc)

    expected_shas = {f"classes0.dex_SHA", f"classes1.dex_SHA"}
    expected_names = {f"classes0.dex", f"classes1.dex"}

    assert set(result["playstore"].keys()) == expected_shas
    assert set(result["local"].keys()) == expected_shas
    assert set(result["playstore"].values()) == expected_names
    assert set(result["local"].values()) == expected_names

    assert result["differing_dexes"] == {}


@mock.patch("analysis.aggregation._unzip_playstore_apk")
@mock.patch("analysis.aggregation.os.chdir")
@mock.patch("analysis.aggregation.Path.iterdir")
@mock.patch("analysis.aggregation.local")
def test_create_dex_sets_with_differences(
    mock_local, mock_iterdir, mock_chdir, mock_unzip
):
    cvc = "10001"

    # Simulate dex files: one file in common, one unique to each set
    playstore_files = [Path("classes0.dex"), Path("classes1.dex")]
    local_files = [Path("classes0.dex"), Path("classes2.dex")]

    # Return different sets on first and second call to Path.iterdir()
    mock_iterdir.side_effect = [playstore_files, local_files]

    # Create a mapping from file name to SHA
    sha_map = {
        "classes0.dex": "shared_sha",
        "classes1.dex": "playstore_only_sha",
        "classes2.dex": "local_only_sha",
    }

    # Return a fake sha256sum command result per file
    def sha256sum_side_effect(file_path):
        filename = Path(file_path).name
        sha = sha_map[filename]
        return lambda: f"{sha}  {filename}"

    sha256sum_mock = mock.MagicMock()
    sha256sum_mock.__getitem__.side_effect = lambda key: sha256sum_side_effect(key)

    def local_side_effect(cmd):
        if cmd == "sha256sum":
            return sha256sum_mock
        raise KeyError(f"Unexpected local command accessed: {cmd}")

    mock_local.__getitem__.side_effect = local_side_effect

    result = aggregation.create_dex_sets(cvc)

    assert result["playstore"] == {
        "shared_sha": "classes0.dex",
        "playstore_only_sha": "classes1.dex",
    }

    assert result["local"] == {
        "shared_sha": "classes0.dex",
        "local_only_sha": "classes2.dex",
    }

    assert result["differing_dexes"] == {
        "playstore_only_sha": "playstore->classes1.dex",
        "local_only_sha": "local->classes2.dex",
    }
