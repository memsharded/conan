from conans.model.values import SettingsValues


class TestSettingsValues:

    def test_simple(self):
        v = SettingsValues()
        v["compiler"] = "gcc"
        v["compiler.version"] = "8"
        text = "compiler=gcc\ncompiler.version=8"
        assert text == v.dumps()
