from os import path, getuid
#from tempfile import mkstemp, gettempdir

# project
from checks import AgentCheck
from tests.checks.common import AgentCheckTest, load_check
from unittest import skipIf
from nose.tools import *
from datetime import datetime

class TestFileUnit(AgentCheckTest):
    CHECK_NAME = 'system.segfault'
    METRIC_BASE = 'system.segfault'
    FIXTURE_PATH = path.join(
        path.dirname(path.realpath(__file__)),
        'fixtures',
        'segfault'
    )

    def check_and_assert(self, filename, expected_metrics,
        kernel_line_regex = '^(?P<timestamp>.+?) (?P<host>\S+) kernel: \[\s*(?P<uptime>\d+(?:\.\d+)?)\] (?P<message>.*)$',
        process_name_regex = '^(?P<process>[^\[]+)\[(?P<pid>\d+)\]: segfault',
        timestamp_format = '%b %d %H:%M:%S',
        time_window_seconds = 60,
        config = None,
        tags = [],
        # the timestamps in the fixture files are written generally leading up to this datetime
        mock_now = datetime(2018, 11, 29, 2, 12),
    ):
        if filename[0] != '/':
            filename = path.join(self.FIXTURE_PATH, filename)

        conf = {
            'init_config': {},
            'instances': [config or {
                'logfile': filename,
                'kernel_line_regex': kernel_line_regex,
                'process_name_regex': process_name_regex,
                'timestamp_format': timestamp_format,
                'time_window_seconds': time_window_seconds,
                'tags': tags,
                'mock_now': mock_now,
            }]
        }

        check = load_check('segfault', conf, {})
        check.check(conf['instances'][0])

        received_metrics = sorted(check.get_metrics())

        self.assertEqual(
            len(received_metrics),
            len(expected_metrics),
            "Got %s metrics but specified %s matches" % (len(received_metrics), len(expected_metrics))
        )

        for idx, obj in enumerate(received_metrics):
            metric_name, timestamp, metric_value, opts = obj
            received_tags = opts.get('tags', [])

            expected = expected_metrics[idx]
            expected_tags = expected.get('tags', [])

            self.assertTrue(
                metric_name.startswith(self.METRIC_BASE),
                "(%s) Service check name should begin with `%s`" % (idx, self.METRIC_BASE)
            )

            if 'name' in expected:
                self.assertEqual(
                    metric_name,
                    expected.get('name'),
                    "(%s) metric name should be `%s`, got `%s`" % (idx, expected.get('name'), metric_name)
                )

            if 'value' in expected:
                self.assertEqual(
                    metric_value,
                    expected.get('value'),
                    "(%s) metric value should be `%s`, got `%s`" % (idx, expected.get('value'), metric_value)
                )

            if 'type' in expected:
                self.assertEqual(
                    opts.get('type'),
                    expected.get('type'),
                    "(%s) metric type should be `%s`, got `%s`" % (idx, expected.get('type'), opts.get('type'))
                )

            for idx, expected_tag in enumerate(expected_tags):
                exists = (expected_tag in received_tags)
                self.assertEqual(
                    exists,
                    True,
                    "(%s) `type` tag should include `%s`, got tags: %s" % (idx, expected_tag, received_tags)
                )

        return received_metrics

    def test_invalid_config(self):
        self.check_and_assert('kern.nonexistent.log', [
            { 'name': 'system.segfault.errors', 'type': 'rate', 'tags': ['type:config', 'foo:bar'] }
        ], kernel_line_regex=None, tags=['foo:bar'])
        self.check_and_assert('kern.nonexistent.log', [
            { 'name': 'system.segfault.errors', 'type': 'rate', 'tags': ['type:config'] }
        ], config={"foo":1})

    def test_no_file(self):
        self.check_and_assert('kern.nonexistent.log', [
            { 'name': 'system.segfault.errors', 'type': 'rate', 'tags': ['type:io'] }
        ])

    @skipIf(getuid() == 0, "Can't run access test as root")
    def test_no_access(self):
        if getuid() > 0:
            # previously used a root-owned file, but docker build as a user can't
            # build an image then. instead, chose a file a regular user shouldn't
            # have access to but should exist. we can cheat this way with a little
            # more confidence since we're relying on docker anyway for a reliable
            # test environment

            self.check_and_assert('/etc/shadow', [
                { 'name': 'system.segfault.errors', 'type': 'rate', 'tags': ['type:io'] }
            ])
        else:
            print "Skipping"

    def test_no_segfaults(self):
        metrics = self.check_and_assert('kern.clean.log', [])
        self.assertEqual(len(metrics), 0, "Expected no metrics, got: %s" % metrics)

    def test_non_matching(self):
        metrics = self.check_and_assert('kern.garbage.log', [])
        self.assertEqual(len(metrics), 0, "Expected no metrics, got: %s" % metrics)
        metrics = self.check_and_assert('kern.envoy_segfaults.log', [], time_window_seconds=65, process_name_regex='whaargarbl')
        self.assertEqual(len(metrics), 0, "Expected no metrics, got: %s" % metrics)


    def test_segfaults(self):
        self.check_and_assert('kern.envoy_segfaults.log', [
            { 'name': 'system.segfault.count', 'type': 'gauge', 'value': 1.0, 'tags': ['process:envoy', 'time_window:65'] }
        ], time_window_seconds=65)
        self.check_and_assert('kern.envoy_segfaults.log', [
            { 'name': 'system.segfault.count', 'type': 'gauge', 'value': 4.0, 'tags': ['process:envoy', 'time_window:7200'] }
        ], time_window_seconds=7200)
        self.check_and_assert('kern.multi_segfaults.log', [
            { 'name': 'system.segfault.count', 'type': 'gauge', 'value': 1.0, 'tags': ['process:anvoy', 'time_window:7200'] },
            { 'name': 'system.segfault.count', 'type': 'gauge', 'value': 3.0, 'tags': ['process:envoy', 'time_window:7200'] },
        ], time_window_seconds=7200)

    def test_segfault_no_process(self):
        self.check_and_assert('kern.envoy_segfaults.log', [
            { 'name': 'system.segfault.count', 'type': 'gauge', 'value': 1.0, 'tags': ['time_window:65'] }
        ], time_window_seconds=65, process_name_regex=None)
        self.check_and_assert('kern.envoy_segfaults.log', [
            { 'name': 'system.segfault.count', 'type': 'gauge', 'value': 1.0, 'tags': ['process:yovne', 'time_window:65'] }
        ], time_window_seconds=65, process_name_regex=None, tags=['process:yovne'])
