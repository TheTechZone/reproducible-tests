import pytest
from unittest.mock import patch, MagicMock, mock_open

from src.setup import (
    PackageManager,
    AptPackageManager,
    DnfPackageManager,
    UnsupportedPlatformError,
    get_package_manager,
    get_os_release,
    ExecResult,
)


# --- PLATFORM CHECKS ------------------------------------------------------


def test_check_platform_support_non_linux():
    with patch("platform.system", return_value="Darwin"):
        with pytest.raises(UnsupportedPlatformError):
            PackageManager.check_platform_support()


def test_check_platform_support_linux():
    with patch("platform.system", return_value="Linux"):
        assert PackageManager.check_platform_support() is None


# --- OS RELEASE PARSING ---------------------------------------------------


def test_get_os_release_parsing():
    fake_os_release = """NAME="Ubuntu"
VERSION="22.04.2 LTS (Jammy Jellyfish)"
ID=ubuntu
"""
    with patch("platform.system", return_value="Linux"), patch(
        "builtins.open", mock_open(read_data=fake_os_release)
    ):
        result = get_os_release()
        assert result["ID"] == "ubuntu"
        assert result["NAME"] == "Ubuntu"


def test_get_os_release_non_linux():
    with patch("platform.system", return_value="Windows"):
        with pytest.raises(UnsupportedPlatformError):
            get_os_release()


# --- PACKAGE MANAGER SELECTION --------------------------------------------


@patch("src.setup.pm.local")
@patch("src.setup.pm.get_os_release", return_value={"ID": "ubuntu"})
def test_get_package_manager_apt(_, mock_local):
    mock_local.__getitem__.return_value = MagicMock()
    pm = get_package_manager()
    assert isinstance(pm, AptPackageManager)


@patch("src.setup.pm.local")
@patch("src.setup.pm.get_os_release", return_value={"ID": "fedora"})
def test_get_package_manager_dnf(_, mock_local):
    mock_local.__getitem__.return_value = MagicMock()
    pm = get_package_manager()
    assert isinstance(pm, DnfPackageManager)


@patch("src.setup.pm.get_os_release", return_value={"ID": "arch"})
def test_get_package_manager_arch_raises(_):
    with pytest.raises(UnsupportedPlatformError, match="Arch"):
        get_package_manager()


@patch("src.setup.pm.get_os_release", return_value={"ID": "unknown"})
def test_get_package_manager_unknown_distro(_):
    with pytest.raises(UnsupportedPlatformError, match="unknown"):
        get_package_manager()


# --- APT PACKAGE MANAGER --------------------------------------------------


@patch("src.setup.pm.execute")
@patch("src.setup.pm.local", autospec=True)
def test_apt_install_single(mock_local, mock_execute):
    mock_apt_get = MagicMock()
    mock_local.__getitem__.side_effect = lambda cmd: {
        "apt-get": mock_apt_get,
        "dpkg-query": MagicMock(),
        "apt-cache": MagicMock(),
    }[cmd]

    # Capture calls to __getitem__ on the apt-get command
    def apt_get_getitem(args):
        # Expect args like ("install", "-y", "--show-progress", ["vim"])
        assert "vim" in args[-1]
        return MagicMock()

    mock_apt_get.__getitem__.side_effect = apt_get_getitem

    mock_env = MagicMock()
    mock_local.env.return_value.__enter__.return_value = mock_env

    # Run test
    pm = AptPackageManager()
    pm.install("vim")

    # Ensure execute was called
    mock_execute.assert_called_once()


@patch("src.setup.pm.execute")
@patch("src.setup.pm.local", autospec=True)
def test_apt_install_multiple(mock_local, mock_execute):
    mock_apt_get = MagicMock()
    mock_local.__getitem__.side_effect = lambda cmd: {
        "apt-get": mock_apt_get,
        "dpkg-query": MagicMock(),
        "apt-cache": MagicMock(),
    }[cmd]

    # Capture calls to __getitem__ on the apt-get command
    def apt_get_getitem(args):
        # Expect args like ("install", "-y", "--show-progress", ["vim"])
        assert "vim" in args[-1]
        assert "curl" in args[-1]
        return MagicMock()

    mock_apt_get.__getitem__.side_effect = apt_get_getitem

    mock_env = MagicMock()
    mock_local.env.return_value.__enter__.return_value = mock_env

    # Run test
    pm = AptPackageManager()
    pm.install(["vim", "curl"])

    # Ensure execute was called
    mock_execute.assert_called_once()


@patch("src.setup.pm.execute")
@patch("src.setup.pm.local", autospec=True)
def test_apt_update(mock_local, mock_execute):
    mock_apt_get = MagicMock()

    mock_local.__getitem__.side_effect = lambda cmd: {
        "apt-get": mock_apt_get,
        "dpkg-query": MagicMock(),
        "apt-cache": MagicMock(),
    }[cmd]

    mock_apt_get.__getitem__.side_effect = lambda args: (
        MagicMock(name="apt-get update cmd") if "update" in args else MagicMock()
    )

    pm = AptPackageManager()
    pm.update()

    mock_execute.assert_called_once()


@patch("src.setup.pm.execute")
@patch("src.setup.pm.local", autospec=True)
def test_apt_is_installed(mock_local, mock_execute):
    mock_cmd = MagicMock()
    mock_local.__getitem__.return_value = mock_cmd

    # Create a mock result that looks like an ExecResult
    mock_result = MagicMock(spec=ExecResult)
    mock_result.retcode = 0
    mock_result.stdout = "curl is already the newest version"
    mock_result.stderr = None
    mock_execute.return_value = mock_result

    pm = AptPackageManager()
    result = pm.is_installed("curl")
    assert result is True


# --- DNF PACKAGE MANAGER --------------------------------------------------


@patch("src.setup.pm.execute")
@patch("src.setup.pm.local", autospec=True)
def test_dnf_install_single(mock_local, mock_execute):
    mock_dnf = MagicMock()
    mock_local.__getitem__.side_effect = lambda cmd: {"dnf": mock_dnf}[cmd]

    def dnf_getitem(args):
        # Check that both packages are in args
        assert "vim" in args[-1]
        return MagicMock()

    mock_dnf.__getitem__.side_effect = dnf_getitem

    pm = DnfPackageManager()
    pm.install(["vim"])

    mock_execute.assert_called_once()


@patch("src.setup.pm.execute")
@patch("src.setup.pm.local", autospec=True)
def test_dnf_install_multiple(mock_local, mock_execute):
    mock_dnf = MagicMock()
    mock_local.__getitem__.side_effect = lambda cmd: {"dnf": mock_dnf}[cmd]

    def dnf_getitem(args):
        # Check that both packages are in args
        assert "nano" in args[-1]
        assert "wget" in args[-1]
        return MagicMock()

    mock_dnf.__getitem__.side_effect = dnf_getitem

    pm = DnfPackageManager()
    pm.install(["nano", "wget"])

    mock_execute.assert_called_once()


@patch("src.setup.pm.execute")
@patch("src.setup.pm.local", autospec=True)
def test_dnf_update(mock_local, mock_execute):
    mock_dnf = MagicMock()
    mock_local.__getitem__.side_effect = lambda cmd: {"dnf": mock_dnf}[cmd]

    mock_dnf.__getitem__.side_effect = lambda args: (
        MagicMock(name="dnf makecache cmd") if "makecache" in args else MagicMock()
    )

    pm = DnfPackageManager()
    pm.update()

    mock_execute.assert_called_once()


@patch("src.setup.pm.execute")
@patch("src.setup.pm.local", autospec=True)
def test_dnf_is_installed(mock_local, mock_execute):
    mock_cmd = MagicMock()
    mock_local.__getitem__.return_value = mock_cmd

    mock_result = MagicMock(spec=ExecResult)
    mock_result.retcode = 0
    mock_result.stderr = None
    mock_result.stdout = "nano 1.2.3"
    mock_execute.return_value = mock_result

    pm = DnfPackageManager()
    assert pm.is_installed("nano") is True


# --- LIBFUSE INSTALL ------------------------------------------------------


@patch("src.setup.pm.AptPackageManager.install")
@patch("src.setup.pm.local", autospec=True)
def test_apt_install_libfuse(mock_local, mock_install):
    mock_local.__getitem__.return_value = MagicMock()
    pm = AptPackageManager()
    pm.install_libfuse()
    mock_install.assert_called_once_with(["libfuse2", "libfuse-dev"])


@patch("src.setup.pm.DnfPackageManager.install")
@patch("src.setup.pm.local", autospec=True)
def test_dnf_install_libfuse(mock_local, mock_install):
    mock_local.__getitem__.return_value = MagicMock()
    pm = DnfPackageManager()
    pm.install_libfuse()
    mock_install.assert_called_once_with(["fuse-devel"])


# --- REPR -----------------------------------------------------------------


@patch("src.setup.pm.local", autospec=True)
def test_repr_apt(mock_local):
    mock_local.__getitem__.return_value = MagicMock()
    assert repr(AptPackageManager()) == "APT Package manager"


@patch("src.setup.pm.local", autospec=True)
def test_repr_dnf(mock_local):
    mock_local.__getitem__.return_value = MagicMock()
    assert repr(DnfPackageManager()) == "DNF Package manager"
