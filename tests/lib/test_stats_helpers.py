# Add lib/ to the import path:
import sys
import os
agent_lib_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), '../../lib')
sys.path.insert(1, agent_lib_dir)

from time import sleep

# project
import unittest
import logging

from stats_helpers import Timing

class MockException(Exception):
    pass

class MockCheck():
    def __init__(self, test):
        self.metrics = []
        self.test = test
    def increment(self, name, **kwargs):
        self.metrics.append((name, 'increment', 1, kwargs))
    def histogram(self, name, value, **kwargs):
        self.metrics.append((name, 'histogram', value, kwargs))
    def check_and_assert(self, expected):
        expected_metrics = len(expected)
        got_metrics = len(self.metrics)
        self.test.assertEqual(
            expected_metrics,
            got_metrics,
            "Expected %s metrics, got %s" % (
                expected_metrics,
                got_metrics
            )
        )
        for idx, got in enumerate(self.metrics):
            expected = expected[idx]
            for idx, expectation_type in enumerate(['name', 'type', 'value']):
                if idx < len(expected) and expected[idx]:
                    self.test.assertEqual(
                        expected[idx],
                        got[idx],
                        "(%s) Expected metric %s `%s`, got `%s`" % (
                            expected[0],
                            expectation_type,
                            expected[idx],
                            got[idx]
                        )
                    )
            if len(expected) == 4:
                if 'tags' in expected[3]:
                    expected_tags = sorted(expected[3]['tags'])
                    got_tags = sorted(got[3]['tags'])
                    self.test.assertEqual(
                        expected_tags,
                        got_tags,
                        "(%s) Expected tags %s, got %s" % (
                            expected[0],
                            expected_tags,
                            got_tags
                        )
                    )

class TestFileUnit(unittest.TestCase):
    def test_default(self):
        check = MockCheck(self)

        with Timing(check, 'foo'):
            pass

        check.check_and_assert([])

    def test_without_timing(self):
        check = MockCheck(self)

        with Timing(check, 'foo', emit=Timing.WITH_COUNT):
            pass

        check.check_and_assert([
            ['foo.count', 'increment', None, {'tags': [
                'is_error:false',
                'error_type:none'
            ]}]
        ])

    def test_with_timing(self):
        check = MockCheck(self)

        with Timing(check, 'foo', emit=Timing.WITH_TIMING):
            sleep(0.1)

        check.check_and_assert([
            ['foo', 'histogram', None, {'tags': [
                'is_error:false',
                'error_type:none'
            ]}]
        ])

        self.assertTrue(check.metrics[0][2] >= 0.1, "Expected a timing value >= 0.1")

    def test_count_with_tags(self):
        check = MockCheck(self)

        with Timing(check, 'foo', emit=Timing.WITH_COUNT, tags={'foo':'bar'}):
            pass

        check.check_and_assert([
            ['foo.count', 'increment', None, {'tags': [
                'is_error:false',
                'error_type:none',
                'foo:bar'
            ]}]
        ])

    def test_with_tag_override(self):
        check = MockCheck(self)

        with Timing(check, 'foo', emit=Timing.WITH_COUNT, tags={'error_type':'keke'}):
            pass

        check.check_and_assert([
            ['foo.count', 'increment', None, {'tags': [
                'is_error:false',
                'error_type:keke'
            ]}]
        ])

    def test_with_error(self):
        check = MockCheck(self)

        try:
            with Timing(check, 'foo', emit=Timing.WITH_COUNT):
                raise MockException("foo")
        except MockException:
            pass

        check.check_and_assert([
            ['foo.count', 'increment', None, {'tags': [
                'is_error:true',
                'error_type:mockexception',
            ]}]
        ])
