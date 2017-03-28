import importlib


def apply_linters(conanfile, output, linters):
    for linter in linters:
        try:
            lint_mod = importlib.import_module("conans.client.linters." + linter)
        except:
            output.error("Couldn't load %s linter" % linter)
        try:
            lint_mod.linter(conanfile, output)
        except Exception as e:
            output.error("Couldn't run %s linter: %s" % (linter, str(e)))
