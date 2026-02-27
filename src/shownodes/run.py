import shlex
import subprocess
from subprocess import CompletedProcess
from typing import List, Union


def run(cmd: Union[str, List[str]], **kwargs) -> CompletedProcess:
    """
    Helper for ``subprocess.run``. Allows command to be optionally given in
    string or list of strings format. Output captured by default, and
    automatically decoded from ``bytes`` to ``str``.
    """
    kwargs.setdefault("capture_output", True)
    kwargs.setdefault("encoding", "utf8")
    args = shlex.split(cmd) if isinstance(cmd, str) else cmd
    result = subprocess.run(args, **kwargs)
    return result
