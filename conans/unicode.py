import six


get_cwd = six.moves.getcwd


def make_unicode(v):
    if six.PY2:
        if isinstance(v, str):
            return v.decode("utf8")
    elif isinstance(v, bytes):
        return v.decode("utf8")
    return v


def assert_unicode(v):
    if six.PY2:
        assert isinstance(v, unicode)
    else:
        assert isinstance(v, str)
