from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
import unittest
from datetime import datetime, date, timedelta
from steemrewarding.utils import isfloat, tags_included, tags_excluded


class Testcases(unittest.TestCase):
    def test_isfloat(self):
        self.assertTrue(isfloat("1.023"))
        self.assertTrue(isfloat("1023"))
        self.assertTrue(isfloat("1.023e1"))
        self.assertFalse(isfloat("1abc"))

    def test_tags_included(self):
        self.assertTrue(tags_included("", ["a", "b"]))
        self.assertTrue(tags_included(None, ["a", "b"]))
        self.assertTrue(tags_included("a", ["a", "b"]))
        self.assertTrue(tags_included("a,b", ["a", "b"]))
        self.assertTrue(tags_included("a,b", ["c", "b"]))
        self.assertTrue(tags_included("a&b", ["a", "b"]))
        self.assertTrue(tags_included("a&b,c", ["a", "b",  "c"]))
        self.assertTrue(tags_included("a&b&c", ["a", "b", "c"]))

        self.assertFalse(tags_included("a", ["b", "c"]))
        self.assertFalse(tags_included("a&b", ["b", "c"]))
        self.assertFalse(tags_included("a&b&c", ["b", "c"]))
        self.assertFalse(tags_included("a,a&b", ["b", "c"]))
        self.assertFalse(tags_included("a,a&c", ["b", "c"]))
        self.assertFalse(tags_included("d", ["b", "c"]))

    def test_tags_excluded(self):
        self.assertTrue(tags_excluded("", ["a", "b"]))
        self.assertTrue(tags_excluded(None, ["a", "b"]))
        self.assertTrue(tags_excluded("c", ["a", "b"]))
        self.assertTrue(tags_excluded("c,d", ["a", "b"]))
        self.assertTrue(tags_excluded("a,d", ["c", "b"]))
        self.assertTrue(tags_excluded("a&c", ["a", "b"]))
        self.assertTrue(tags_excluded("a&d,d", ["a", "b",  "c"]))
        self.assertTrue(tags_excluded("a&b&d", ["a", "b", "c"]))

        self.assertFalse(tags_excluded("b", ["b", "c"]))
        self.assertFalse(tags_excluded("b&c", ["b", "c"]))
        self.assertFalse(tags_excluded("a&b&c", ["a", "b", "c"]))
        self.assertFalse(tags_excluded("a,a&b", ["a", "b", "c"]))
        self.assertFalse(tags_excluded("d,a&c", ["a", "b", "c"]))
        self.assertFalse(tags_excluded("c", ["b", "c"]))
