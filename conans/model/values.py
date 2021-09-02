from collections import OrderedDict


class SettingsValues:
    def __init__(self, values=None):
        self._values = values or OrderedDict()

    def dumps(self):
        """ produces a text string with lines with a flattened version:
        compiler.arch = XX
        compiler.arch.speed = YY
        IMPORTANT: None values are discarded
        This is part of the package_id
        """
        return "\n".join(["%s=%s" % (k, v) for k, v in self._values.items() if v is not None])

    @staticmethod
    def loads(text):
        """ SettingsValues are loaded from conaninfo.txt and profile files
        It must be already ordered
        """
        values = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line[0] == "#":
                continue
            name, value = line.split("=", 1)
            values.append((name.strip(), value.strip()))
        return SettingsValues(OrderedDict(values))

    def serialize(self):
        # Used for search results
        # No need to filter None, this comes from reading conaninfo.txt
        return list(self._values.items())

    def items(self):
        return self._values.items()

    # These methods are strictly for manipulation from the package_id() method
    def set(self, attr, value):
        self._values[attr] = value

    def get(self, attr, default=None):
        return self._values.get(attr, default)

    def remove(self, attr):
        to_remove = [v for v in self._values if v.startswith(attr)]
        for r in to_remove:
            self._values.pop(r, None)

    def update(self, other):
        """
        :type other: SettingsValues
        """
        self._values.update(other._values)
