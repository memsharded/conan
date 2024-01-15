import os
from pathlib import Path

import yaml

from conans.client.loader import load_python_file
from conans.errors import ConanException
from conans.util.files import load, save


def _find_ws_folder():
    path = Path(os.getcwd())
    while path.is_dir() and len(path.parts) > 1:  # finish at '/'
        if (path / "conanws.yml").is_file() or (path / "conanws.py").is_file():
            return path
        else:
            path = path.parent


class Workspace:
    def __init__(self):
        self._folder = _find_ws_folder()
        self._yml = None
        self._py = None
        if self._folder is not None:
            self._yml_file = os.path.join(self._folder, "conanws.yml")
            if os.path.exists(self._yml_file):
                try:
                    self._yml = yaml.safe_load(load(self._yml_file))
                except Exception as e:
                    raise ConanException(f"Invalid workspace yml format at {self._folder}: {e}")

            py_file = os.path.join(self._folder, "conanws.py")
            if os.path.exists(py_file):
                self._py, _ = load_python_file(py_file)
                setattr(self._py, "conanws_data", self._yml)

    @property
    def folder(self):
        return self._folder

    def _attr(self, value):
        if self._py and getattr(self._py, value, None):
            return self._py.home_folder() if callable(self._py.home_folder) else self._py.home_folder
        if self._yml:
            return self._yml.get(value)

    def home_folder(self):
        if not self._folder:
            return
        home = self._attr("home_folder")
        if home is None or os.path.isabs(home):
            return home
        return os.path.normpath(os.path.join(self._folder, home))

    def add(self, ref, path, output_folder):
        if not self._folder:
            raise ConanException("Workspace not defined, please create a "
                                 "'conanws.py' or 'conanws.yml' file")
        self._yml = self._yml or {}
        self._yml.setdefault("editables", {})[str(ref)] = {"path": path,
                                                           "output_folder": output_folder}
        save(self._yml_file, yaml.dump(self._yml))

    def remove(self, path):
        # Maybe also means to remove the folder? Or is that a CLOSE operation?
        if not self._folder:
            raise ConanException("Workspace not defined, please create a "
                                 "'conanws.py' or 'conanws.yml' file")
        self._yml = self._yml or {}
        editables = {}
        for ref, info in self._yml.get("editables", {}).items():
            if not info["path"].startswith(path):  # Remove all that starts with the path
                editables[ref] = info
        if editables:
            self._yml["editables"] = editables
        else:
            self._yml.pop("editables")
        save(self._yml_file, yaml.dump(self._yml))

    def editables(self):
        if not self._folder:
            return
        editables = self._attr("editables")
        return editables
