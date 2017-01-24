import unittest
from conans.test.utils.test_files import temp_folder
import os
from conans.util.files import rmdir


class BusyRemovalTest(unittest.TestCase):

    def basic_test(self):
        folder = temp_folder()
        subfolder = os.path.join(folder, "subfolder")
        os.makedirs(subfolder)
        filename = os.path.join(subfolder, "file1.txt")
        filehandle = open(filename, "wb")
        filehandle.write("Hello World")
        rmdir(subfolder)