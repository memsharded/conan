import os
from pathlib import Path

from conans.client.loader import load_python_file


def _find_ws_file():
    path = Path(os.getcwd())
    while path.is_dir() and len(path.parts) > 1:  # finish at '/'
        conanwsfile = path / "conanws.py"
        if conanwsfile.is_file():
            return conanwsfile
        else:
            path = path.parent


class Workspace:
    def __init__(self):
        self._wsfile = _find_ws_file()
        if self._wsfile is not None:
            ws_module, _ = load_python_file(self._wsfile)
            self._ws_module = ws_module
        else:
            self._ws_module = None

    def home_folder(self):
        if not self._ws_module:
            return
        home = getattr(self._ws_module, "home_folder", None)
        if home is None:
            return
        if os.path.isabs(home):
            return home
        cwd = os.path.dirname(self._wsfile)
        abs_path = os.path.normpath(os.path.join(cwd, home))
        return abs_path
