from logging import LogRecord
import inspect
import logging
import shutil
import sys
import os
from collections import namedtuple
from types import FrameType
from typing import Optional

from plumbum.cmd import sudo  # type: ignore
from plumbum.commands.base import BaseCommand  # type: ignore

run_command_counter = 0

ExecResult = namedtuple("ExecResult", ["retcode", "stdout", "stderr"])


def execute(
    cmd: BaseCommand,
    retcodes: Optional[tuple[int, ...]] = None,
    as_sudo: bool = False,
    log: bool = False,
) -> str | ExecResult:
    """
    Executes and logs a plumbum command.
    See: https://plumbum.readthedocs.io/en/latest/local_commands.html
    If anything is passed for expected retcodes, returns:
         retcode, stdout, stderr
    else returns:
         None, stdout, None
    :param cmd: the plumbum command to execute, can be either a LocalCommand (via local['cmd']) or RemoteCommand (rem['cmd'])
    :param retcodes: None or a tuple of accepted return codes
    :param as_sudo: Execute as superuser (might request a prompt if the process does not have `euid=0`)
    :param log: turn logging of the command on or off
    :return: ExecResult - retcode, stdout, stderr (if retcode is not None) OR (None, stdout, None)
    """
    global run_command_counter

    def log_command(cmd_str: str, stdout_data: str, should_log: bool = True) -> None:
        if not should_log:
            return

        def formatstring_stdout(stdout_arg: str) -> str:
            return f"\n\tOutput:\n {stdout_arg}" if stdout_arg.strip() else ""

        # Safe frame handling
        frame: Optional[FrameType] = inspect.currentframe()
        if frame and frame.f_back and frame.f_back.f_back:
            caller_frame = frame.f_back.f_back
            func_name = caller_frame.f_code.co_name
            line_number = caller_frame.f_lineno
        else:
            func_name = "<unknown>"
            line_number = -1

        print(
            f"-> function:{func_name}, line {line_number} \n\t{cmd_str}{formatstring_stdout(stdout_data)}"
        )

    logging.debug(f"Command nr: {run_command_counter} \n{cmd}\nRetcodes: {retcodes}")
    run_command_counter = run_command_counter + 1
    if as_sudo:
        (rc, stdout, stderr) = sudo[cmd].run(retcode=retcodes)
    else:
        (rc, stdout, stderr) = cmd.run(retcode=retcodes)
    if retcodes is None and rc != 0:
        log_command(str(cmd), stdout, log)
        logging.critical(
            f"UNEXPECTED ERROR:\nrc: {rc}\nstdout: {stdout}\nstderr: {stderr}\n"
        )
        exit(1)
    log_command(str(cmd), stdout, log)
    if retcodes is None:
        return ExecResult(None, stdout, None)
    else:
        return ExecResult(rc, stdout, stderr)


def get_term() -> str:
    """get the preferred terminal to enhance portability

    todo: actually find a way to do this.
    There is `settings` but that only works on gnome and $TERM is a bit
    useless since everyone pretends to be `xterm-256color`
    """

    terminals = [
        "gnome-terminal",
        "konsole",
        "xfce4-terminal",
        "xterm",
        "terminator",
        "lxterminal",
    ]
    for terminal in terminals:
        if shutil.which(terminal):
            return terminal
    return "gnome-terminal"


def signal_handler(_sig, _frame) -> None:
    print("You pressed Ctrl+C!")
    sys.exit(0)


def open_terminal(command: str) -> None:
    os.system(f"gnome-terminal -- {command} &")


def check_or_request_sudo() -> None:
    euid = os.geteuid()
    if euid != 0:
        print("Script not running as root. Requesting sudo..")
        args = ["sudo", sys.executable] + sys.argv
        # the next line replaces the currently-running process with the sudo
        os.execlpe("sudo", *args, os.environ)  # noqa


class ColorHandler(logging.StreamHandler):
    # https://en.wikipedia.org/wiki/ANSI_escape_code#Colors
    GRAY8 = "38;5;8"
    GRAY7 = "38;5;7"
    ORANGE = "33"
    RED = "31"
    WHITE = "0"

    def __init__(self, stream: logging.StreamHandler):
        super().__init__()
        assert stream.formatter is not None, "stream formatter should not be none"
        self.formatter = stream.formatter

    def emit(self, record: LogRecord) -> None:
        assert self.formatter is not None, "stream formatter should not be none"

        # Don't use white for any logging, to help distinguish from user print statements
        level_color_map = {
            logging.DEBUG: self.GRAY8,
            logging.INFO: self.GRAY7,
            logging.WARNING: self.ORANGE,
            logging.ERROR: self.RED,
        }

        csi = f"{chr(27)}["  # control sequence introducer
        color = level_color_map.get(record.levelno, self.WHITE)
        message = self.formatter.format(record)

        print(f"{csi}{color}m{message}{csi}m")
