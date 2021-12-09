tools_locations = {
    'svn': {"disabled": True},
    'cmake': {
        "3.15": {},
        "3.16": {"disabled": True},
        "3.17": {"disabled": True},
        "3.19": {"path": {"Windows": "C:/ws/cmake/cmake-3.19.7-win64-x64/bin"}},
    },
    'ninja': {
        "1.10.2": {}
    },
    'bazel':  {
        "system": {"path": {'Windows': 'C:/ws/bazel/4.2.0'}},
    },
    'mingw64': {
        "default": "4.9",
        "4.9": {"path": {'Windows': 'C:/ws/mingw/mingw-w64/4.9/mingw64/bin'}},
    },
    'mingw32': {"disabled": True},
    "clang": {
        "disabled": False,
        "default": "12",
        "12": {"path": {'Windows': 'C:/ws/LLVM/LLVM12/bin'}}
    },
    'visual_studio': {"16": {"disabled": False}},
}
