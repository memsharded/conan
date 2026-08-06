import os
import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient


PRINT_FOLDER_RECIPE = textwrap.dedent("""
    from conan import ConanFile

    class Pkg(ConanFile):
        name = "{name}"
        version = "{version}"

        def build(self):
            self.output.info(f"BUILD_FOLDER={{self.build_folder}}")

        def package(self):
            self.output.info(f"PACKAGE_FOLDER={{self.package_folder}}")
    """)


def _extract_build_folder(client_out):
    for line in client_out.splitlines():
        idx = line.find("BUILD_FOLDER=")
        if idx != -1:
            return line[idx + len("BUILD_FOLDER="):].strip()
    return None


def _extract_package_folder(client_out):
    for line in client_out.splitlines():
        idx = line.find("PACKAGE_FOLDER=")
        if idx != -1:
            return line[idx + len("PACKAGE_FOLDER="):].strip()
    return None


class TestDeterministicBuildFolder:

    def test_conf_unset_uses_uuid_cache_folder(self):
        # Regression guard: when the conf is unset, builds land in the UUID cache path
        c = TestClient()
        c.save({"conanfile.py": PRINT_FOLDER_RECIPE.format(name="pkg", version="1.0")})
        c.run("create .")
        build_folder = _extract_build_folder(c.out)
        assert build_folder is not None
        # cache builds live under <CONAN_HOME>/p/b/<hash>/b
        assert os.path.join("p", "b") in build_folder or os.sep + "b" + os.sep in build_folder
        assert c.cache_folder in build_folder

    def test_conf_set_uses_deterministic_folder(self):
        # Build folder is <base>/<name>/b/ and identical across two runs
        c = TestClient()
        base = temp_folder()
        c.save_home({"global.conf": f"tools.build:base_folder={base}"})
        c.save({"conanfile.py": PRINT_FOLDER_RECIPE.format(name="mypkg", version="1.0")})

        c.run("create .")
        build_folder1 = _extract_build_folder(c.out)
        package_folder1 = _extract_package_folder(c.out)

        c.run("create .")
        build_folder2 = _extract_build_folder(c.out)
        package_folder2 = _extract_package_folder(c.out)

        assert build_folder1 == build_folder2
        assert os.path.normpath(build_folder1) == os.path.normpath(os.path.join(base, "mypkg", "b"))
        # Package folder still lives in cache
        assert c.cache_folder in package_folder1

    def test_dep_from_source_uses_deterministic_folder(self):
        # Deps built via --build also honor the conf
        c = TestClient()
        base = temp_folder()
        c.save_home({"global.conf": f"tools.build:base_folder={base}"})

        c.save({"dep/conanfile.py": PRINT_FOLDER_RECIPE.format(name="dep", version="1.0"),
                "app/conanfile.py": GenConanfile("app", "1.0").with_requires("dep/1.0")})
        c.run("export dep")
        c.run("create app --build=missing")

        build_folder = _extract_build_folder(c.out)
        assert build_folder is not None
        assert os.path.normpath(build_folder) == os.path.normpath(os.path.join(base, "dep", "b"))

    def test_wipes_existing_folder(self):
        # A stray file left in <base>/<name>/ is gone after a build
        c = TestClient()
        base = temp_folder()
        c.save_home({"global.conf": f"tools.build:base_folder={base}"})
        c.save({"conanfile.py": PRINT_FOLDER_RECIPE.format(name="wipepkg", version="1.0")})

        # Seed a stray file that should be wiped
        stray_dir = os.path.join(base, "wipepkg")
        os.makedirs(stray_dir, exist_ok=True)
        stray_file = os.path.join(stray_dir, "leftover.txt")
        with open(stray_file, "w") as f:
            f.write("stale")

        c.run("create .")
        assert not os.path.exists(stray_file)

    def test_build_id_reuse_bypassed(self):
        # build_id() DB reuse is skipped in deterministic mode: build() runs each time
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                name = "pkg"
                version = "1.0"
                settings = "build_type"
                build_policy = "missing"
                def build_id(self):
                    self.info_build.settings.build_type = "Any"
                def build(self):
                    self.output.info("Building for real")
                def package(self):
                    self.output.info(f"Packaging {self.settings.build_type}")
            """)
        c = TestClient()
        base = temp_folder()
        c.save_home({"global.conf": f"tools.build:base_folder={base}"})
        c.save({"conanfile.py": conanfile})

        c.run("export .")
        c.run("install --requires=pkg/1.0 -s build_type=Debug")
        assert "Building for real" in c.out

        # In default (non-deterministic) mode, Release would reuse Debug's build via build_id().
        # In deterministic mode, we bypass DB reuse — build() runs again.
        c.run("install --requires=pkg/1.0 -s build_type=Release")
        assert "Building for real" in c.out

    def test_per_package_override(self):
        # tools.build:base_folder can be scoped per-package
        c = TestClient()
        global_base = temp_folder()
        dep_base = temp_folder()
        c.save_home({"global.conf": textwrap.dedent(f"""\
            tools.build:base_folder={global_base}
            dep/*:tools.build:base_folder={dep_base}
            """)})

        c.save({"dep/conanfile.py": PRINT_FOLDER_RECIPE.format(name="dep", version="1.0"),
                "app/conanfile.py": PRINT_FOLDER_RECIPE.format(name="app", version="1.0")
                    .replace("class Pkg", "class App") + "    def requirements(self):\n"
                                                        "        self.requires(\"dep/1.0\")\n"})
        c.run("export dep")
        c.run("create app --build=missing")

        dep_build = None
        app_build = None
        for line in c.out.splitlines():
            if "dep/1.0:" in line and "BUILD_FOLDER=" in line:
                dep_build = line.split("BUILD_FOLDER=", 1)[1].strip()
            elif "app/1.0:" in line and "BUILD_FOLDER=" in line:
                app_build = line.split("BUILD_FOLDER=", 1)[1].strip()

        assert dep_build is not None and app_build is not None
        assert os.path.normpath(dep_build) == os.path.normpath(os.path.join(dep_base, "dep", "b"))
        assert os.path.normpath(app_build) == os.path.normpath(os.path.join(global_base, "app", "b"))
