# coding=utf-8

import unittest

from conans.cli.output import ConanOutput
from conans.client.file_copier import report_copied_files
from conans.test.utils.mocks import RedirectedTestOutput
from conans.test.utils.tools import redirect_output


class ReportCopiedFilesTestCase(unittest.TestCase):

    def test_output_string(self):

        output = RedirectedTestOutput()
        with redirect_output(output):
            files = ['/abs/path/to/file.pdf',
                     '../rel/path/to/file2.pdf',
                     '../rel/path/to/file3.pdf',
                     '../rel/path/to/file4.pdf',
                     '../rel/path/to/file5.pdf',
                     '../rel/path/to/file6.pdf',
                     '../rel/path/to/file7.pdf',
                     '/without/ext/no_ext1',
                     'no_ext2',
                     'a/other.txt']

            report_copied_files(files, ConanOutput())
            lines = sorted(str(output).splitlines())
            self.assertEqual("Copied 7 '.pdf' files", lines[2])
            self.assertEqual("Copied 2 files: no_ext1, no_ext2", lines[1])
            self.assertEqual("Copied 1 '.txt' file: other.txt", lines[0])
