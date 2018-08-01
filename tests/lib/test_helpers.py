# Add lib/ to the import path:
import sys
import os
agent_lib_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), '../../lib')
sys.path.insert(1, agent_lib_dir)

# stdlib
import re
from datetime import datetime

# test
import unittest

# unit under test
import helpers

class TestHelpers(unittest.TestCase):
    def test_parse_fix_timestamp(self):
        # sane case: timestamp close to now, in the past, same year
        dt_now = datetime(2018, 6, 6, 9, 9, 9)
        parsed = helpers.parse_fix_timestamp('Jun  1 09:09:09', '%b %d %H:%M:%S', dt_now)
        self.assertEqual(2018, parsed.year)
        self.assertLess(parsed, dt_now)

        # edge case: timestamp close to now, in the future, same year
        dt_now = datetime(2018, 6, 6, 9, 9, 9)
        parsed = helpers.parse_fix_timestamp('Jun  7 01:01:01', '%b %d %H:%M:%S', dt_now)
        self.assertEqual(2018, parsed.year)
        self.assertGreater(parsed, dt_now)

        # edge case, timestamp at end of year, now at beginning of year
        dt_now = datetime(2019, 1, 1, 0, 0, 0)
        parsed = helpers.parse_fix_timestamp('Dec 31 23:59:59', '%b %d %H:%M:%S', dt_now)
        self.assertEqual(2018, parsed.year)
        self.assertLess(parsed, dt_now)

        # edge case: timestamp at start of year, now at end of year
        dt_now = datetime(2018, 12, 31, 11, 59, 59)
        parsed = helpers.parse_fix_timestamp('Jan  1 00:00:00', '%b %d %H:%M:%S', dt_now)
        self.assertEqual(2018, parsed.year)
        self.assertLess(parsed, dt_now)

        # sane case: a real timestamp format
        dt_now = datetime(2018, 12, 31, 11, 59, 59)
        parsed = helpers.parse_fix_timestamp('2010-01-01 00:00:00', '%Y-%m-%d %H:%M:%S', dt_now)
        self.assertEqual(2010, parsed.year)
