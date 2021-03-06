""" Bencode tests.

    List of test cases taken from original BitTorrent code by Bram Cohen.

    Copyright (c) 2009, 2011 The PyroScope Project <pyroscope.project@gmail.com>
"""
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
from __future__ import absolute_import, print_function  #, unicode_literals

import logging
import unittest

try:
    from io import BytesIO
except ImportError:
    from StringIO import StringIO as BytesIO

from pyrobase.testing import mockedopen
from pyrobase.bencode import * #@UnusedWildImport

log = logging.getLogger(__name__)
log.trace("module loaded")


class DecoderTest(unittest.TestCase):

    def test_errors(self):
        testcases = (
            "",
            "0:0:",
            "ie",
            "i341foo382e",
            #"i-0e",
            "i123",
            "i6easd",
            "35208734823ljdahflajhdf",
            "2:abfdjslhfld",
            #"02:xy",
            "l",
            "l0:",
            "leanfdldjfh",
            "relwjhrlewjh",
            "d",
            "defoobar",
            "d3:fooe",
            #"di1e0:e",
            #"d1:b0:1:a0:e",
            #"d1:a0:1:a0:e",
            #"i03e",
            #"l01:ae",
            "9999:x",
            "l0:",
            "d0:0:",
            "d0:",
        )
        for testcase in testcases:
            #print testcase
            self.failUnlessRaises(BencodeError, bdecode, testcase)


    def test_values(self):
        testcases = (
            ("i4e", 4),
            ("i0e", 0),
            ("i123456789e", 123456789),
            ("i-10e", -10),
            ("0:", ''),
            ("3:abc", "abc"),
            ("10:1234567890", "1234567890"),
            ("le", []),
            ("l0:0:0:e", ['', '', '']),
            ("li1ei2ei3ee", [1, 2, 3]),
            ("l3:asd2:xye", ["asd", "xy"]),
            ("ll5:Alice3:Bobeli2ei3eee", [["Alice", "Bob"], [2, 3]]),
            ("de", {}),
            ("d3:agei25e4:eyes4:bluee", {"age": 25, "eyes": "blue"}),
            ("d8:spam.mp3d6:author5:Alice6:lengthi100000eee",
                {"spam.mp3": {"author": "Alice", "length": 100000}}),
        )
        for bytes, result in testcases:
            self.failUnlessEqual(bdecode(bytes), result)

    def test_encoding(self):
        self.failUnlessEqual(bdecode("l1:\x801:\x81e", "cp1252"), [u"\u20ac", "\x81"])

    def test_bread_stream(self):
        self.failUnlessEqual(bread(BytesIO(b"de")), {})

    def test_bread_file(self):
        with mockedopen({"empty_dict": b"de"}):
            self.failUnlessEqual(bread("empty_dict"), {})


class EncoderTest(unittest.TestCase):

    def test_values(self):
        testcases = (
            (4, "i4e"),
            (0, "i0e"),
            (-10, "i-10e"),
            (12345678901234567890, "i12345678901234567890e"),
            ("", "0:"),
            ("abc", "3:abc"),
            ("1234567890", "10:1234567890"),
            ([], "le"),
            ([1, 2, 3], "li1ei2ei3ee"),
            ([["Alice", "Bob"], [2, 3]], "ll5:Alice3:Bobeli2ei3eee"),
            ({}, "de"),
            ({"age": 25, "eyes": "blue"}, "d3:agei25e4:eyes4:bluee"),
            ({"spam.mp3": {"author": "Alice", "length": 100000}}, "d8:spam.mp3d6:author5:Alice6:lengthi100000eee"),
            ({1: "foo"}, "d1:13:fooe"),
        )
        for obj, result in testcases:
            self.failUnlessEqual(bencode(obj), result)

    def test_bwrite_stream(self):
        data = BytesIO()
        bwrite(data, {})
        self.failUnlessEqual(data.getvalue(), "de")

    def test_bwrite_file(self):
        with mockedopen() as files:
            bwrite("data", {})
            self.failUnlessEqual(files["data"], "de")


if __name__ == "__main__":
    unittest.main()
