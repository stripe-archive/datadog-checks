from tempfile import mkstemp, gettempdir
import time
import os

# project
from checks import AgentCheck
from tests.checks.common import AgentCheckTest, load_check

class TestFileUnit(AgentCheckTest):
    CHECK_NAME = 'file'

    def assert_tags(self, expected_tags, present_tags):
        for tag in expected_tags:
            self.assertTrue(tag in present_tags)

    def test_present_success(self):
        conf = {
            'init_config': {},
            'instances': [
                {'path': __file__, 'expect': 'present'}
            ]
        }
        self.check = load_check('file', conf, {})
        self.check.check(conf['instances'][0])
        metrics = self.check.get_metrics()
        self.assertTrue(len(metrics) == 1)
        metric = metrics[0]
        self.assertTrue(metric[2] > 0)
        self.assert_tags(['expected_status:present'], metric[3]['tags'])

        service_checks = self.check.get_service_checks()
        self.assertTrue(service_checks[0]['status'] == AgentCheck.OK)
        self.assert_tags(['expected_status:present'], service_checks[0]['tags'])

    def test_glob_present_success(self):
        # Make some temporary files, just in case
        mkstemp()
        mkstemp()

        conf = {
            'init_config': {},
            'instances': [
                {'path': gettempdir() + "/*", 'expect': 'present'}
            ]
        }
        self.check = load_check('file', conf, {})
        self.check.check(conf['instances'][0])
        metrics = self.check.get_metrics()
        self.assertTrue(len(metrics) == 1)
        metric = metrics[0]
        self.assertTrue(metric[2] > 0)
        self.assert_tags(['expected_status:present'], metric[3]['tags'])

        service_checks = self.check.get_service_checks()
        self.assertTrue(service_checks[0]['status'] == AgentCheck.OK)
        self.assert_tags(['expected_status:present'], service_checks[0]['tags'])

    def test_glob_present_failure(self):
        conf = {
            'init_config': {},
            'instances': [
                {'path': '/doesntexist/*', 'expect': 'present'}
            ]
        }
        self.check = load_check('file', conf, {})
        self.check.check(conf['instances'][0])

        service_checks = self.check.get_service_checks()
        self.assertTrue(service_checks[0]['status'] == AgentCheck.CRITICAL)
        self.assert_tags(['expected_status:present'], service_checks[0]['tags'])

    def test_absent_failure(self):
        conf = {
            'init_config': {},
            'instances': [
                {'path': __file__, 'expect': 'absent'}
            ]
        }
        self.check = load_check('file', conf, {})
        self.check.check(conf['instances'][0])
        metrics = self.check.get_metrics()
        self.assertTrue(len(metrics) == 1)
        metric = metrics[0]
        self.assertTrue(metric[2] > 0)
        self.assert_tags(['expected_status:absent'], metric[3]['tags'])

        service_checks = self.check.get_service_checks()
        self.assertTrue(service_checks[0]['status'] == AgentCheck.CRITICAL)
        self.assert_tags(['expected_status:absent'], service_checks[0]['tags'])

    def test_present_over_minimum_age_success(self):
        _, path = mkstemp()

        conf = {
            'init_config': {},
            'instances': [
                {'path': path, 'expect': 'absent', 'present_minimum_age_seconds': 59}
            ]
        }
        self.check = load_check('file', conf, {})

        # Change the temp file to be older than the minimum age we'll set below
        oldstamp = time.time() - 100

        self.check.check(conf['instances'][0], file_age=oldstamp)
        metrics = self.check.get_metrics()
        self.assertTrue(len(metrics) == 1)
        metric = metrics[0]
        self.assertTrue(metric[2] > 0)
        self.assert_tags(['expected_status:absent'], metric[3]['tags'])
        # Since the file is older then the seconds we chose, it is NOT absent
        # and therefore critical!
        service_checks = self.check.get_service_checks()
        self.assertTrue(service_checks[0]['status'] == AgentCheck.CRITICAL)
        self.assert_tags(['expected_status:absent'], service_checks[0]['tags'])

    def test_present_under_minimum_age_success(self):
        # This tempfile's mtime will be too new to fire!
        _, path = mkstemp()

        conf = {
            'init_config': {},
            'instances': [
                {'path': path, 'expect': 'absent', 'present_minimum_age_seconds': 59}
            ]
        }
        self.check = load_check('file', conf, {})
        self.check.check(conf['instances'][0])
        metrics = self.check.get_metrics()
        self.assertTrue(len(metrics) == 1)
        metric = metrics[0]
        self.assertTrue(metric[2] > 0)
        self.assert_tags(['expected_status:absent'], metric[3]['tags'])
        # Since the file is older then the seconds we chose, it is NOT absent
        # and therefore critical!
        service_checks = self.check.get_service_checks()
        self.assertTrue(service_checks[0]['status'] == AgentCheck.OK)
        self.assert_tags(['expected_status:absent'], service_checks[0]['tags'])
