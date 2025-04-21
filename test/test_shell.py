import pytest
from unittest.mock import patch, MagicMock
import logging
import os
import sys

from setup.shell import (
    execute,
    get_term,
    signal_handler,
    open_terminal,
    check_or_request_sudo,
    ColorHandler,
    ExecResult,
)


# ---- execute() ------------------------------------------------------


@patch("setup.shell.sudo")
def test_execute_with_retcode_and_sudo(mock_sudo):
    mock_cmd = MagicMock()
    mock_sudo.__getitem__.return_value.run.return_value = (0, "ok", "")

    result = execute(mock_cmd, retcodes=(0,), as_sudo=True)
    assert isinstance(result, ExecResult)
    assert result.retcode == 0
    assert result.stdout == "ok"
    assert result.stderr == ""


def test_execute_without_retcode():
    mock_cmd = MagicMock()
    mock_cmd.run.return_value = (0, "ok", "")

    result = execute(mock_cmd, retcodes=None, as_sudo=False)
    assert result == ExecResult(None, "ok", None)


@patch("setup.shell.logging.critical")
@patch("setup.shell.exit")
def test_execute_unexpected_error(mock_exit, mock_critical):
    mock_cmd = MagicMock()
    mock_cmd.run.return_value = (1, "failed", "something bad")

    execute(mock_cmd, retcodes=None, as_sudo=False)

    mock_critical.assert_called_once()
    mock_exit.assert_called_once_with(1)


# ---- get_term() ------------------------------------------------------


@patch("setup.shell.shutil.which")
def test_get_term_fallback(mock_which):
    mock_which.return_value = None
    assert get_term() == "gnome-terminal"


@patch("setup.shell.shutil.which")
def test_get_term_first_match(mock_which):
    def which_side_effect(cmd):
        return True if cmd == "konsole" else None

    mock_which.side_effect = which_side_effect
    assert get_term() == "konsole"


# ---- signal_handler() ------------------------------------------------


@patch("setup.shell.sys.exit")
def test_signal_handler_calls_exit(mock_exit):
    signal_handler(None, None)
    mock_exit.assert_called_once_with(0)


# ---- open_terminal() -------------------------------------------------


@patch("setup.shell.os.system")
def test_open_terminal(mock_system):
    open_terminal("echo hello")
    mock_system.assert_called_once_with("gnome-terminal -- echo hello &")


# ---- check_or_request_sudo() -----------------------------------------


@patch("os.execlpe")
@patch("os.geteuid")
def test_sudo_elevation_when_not_root(mock_geteuid, mock_execlpe):
    # Setup: User is not root
    mock_geteuid.return_value = 1000

    # Setup environment and system variables
    with patch.object(sys, "executable", "/usr/bin/python"), patch.object(
        sys, "argv", ["script.py", "--arg"]
    ), patch.dict(os.environ, {"PATH": "/usr/bin", "USER": "testuser"}, clear=True):

        # Call the function
        check_or_request_sudo()

        # Verify sudo elevation was requested
        mock_execlpe.assert_called_once()

        # Check the correct arguments were passed to execlpe
        args = mock_execlpe.call_args[0]

        assert args[0] == "sudo"

        # The function appears to be adding os.environ as a single element in the args list
        # instead of passing it as the environment parameter to execlpe
        # Check that the expected command sequence appears in the args
        assert "sudo" in args
        assert "/usr/bin/python" in args
        assert "script.py" in args
        assert "--arg" in args

        # Check that the environment dictionary is the last argument
        assert args[-1] is os.environ
        assert args[-1]["PATH"] == "/usr/bin"
        assert args[-1]["USER"] == "testuser"


@patch("os.execlpe")
@patch("os.geteuid")
def test_no_sudo_elevation_when_root(mock_geteuid, mock_execlpe):
    # Setup: User is already root
    mock_geteuid.return_value = 0

    # Call the function
    check_or_request_sudo()

    # Verify sudo was not called
    mock_execlpe.assert_not_called()


@patch("setup.shell.os.geteuid", return_value=0)
def test_check_or_request_sudo_as_root(mock_geteuid):
    check_or_request_sudo()  # Should not do anything or raise


# ---- ColorHandler.emit() ---------------------------------------------


@patch("builtins.print")
def test_color_handler_emit(mock_print):
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Test message",
        args=(),
        exc_info=None,
    )

    fake_formatter = MagicMock()
    fake_formatter.format.return_value = "Formatted message"

    handler = ColorHandler(stream=MagicMock())
    handler.formatter = fake_formatter
    handler.emit(record)

    mock_print.assert_called_once()
    output = mock_print.call_args[0][0]
    assert "Formatted message" in output
    assert "[38;5;" in output  # color prefix
