from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
import unittest
from datetime import datetime, date, timedelta
from steemrewarding.utils import isfloat


class Testcases(unittest.TestCase):
    def test_isfloat(self):
        self.assertTrue(isfloat("1.023"))
        self.assertTrue(isfloat("1023"))
        self.assertTrue(isfloat("1.023e1"))
        self.assertFalse(isfloat("1abc"))
