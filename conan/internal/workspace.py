import os
from pathlib import Path

import yaml

from conans.client.loader import load_python_file
from conans.errors import ConanException
from conans.util.files import load, save


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
        self.workspace_folder = os.path.dirname(self._wsfile) if self._wsfile else None
        self._yml = os.path.join(self.workspace_folder, "conanws.yml") if self._wsfile else None
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
        abs_path = os.path.normpath(os.path.join(self.workspace_folder, home))
        return abs_path

    def add(self, ref, path, output_folder):
        if not self._ws_module:
            raise ConanException("Workspace not defined")
        if os.path.exists(self._yml):
            try:
                data = yaml.safe_load(load(self._yml))
            except Exception as e:
                raise ConanException("Invalid yml format at {}: {}".format(self._yml, e))
        else:
            data = {}
        data.setdefault("editables", {})[ref] = {"path": path, "output_folder": output_folder}
        save(self._yml, yaml.dump(data))
