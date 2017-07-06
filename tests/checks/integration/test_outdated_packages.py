import mock

from checks import AgentCheck
from tests.checks.common import AgentCheckTest, load_check


class TestFileUnit(AgentCheckTest):
    CHECK_NAME = 'outdated_packages'

    def setUp(self):
        self.config = {
	    "init_config": {},
	    "instances": [],
        }

    @mock.patch('utils.platform.Platform.is_linux', return_value=False)
    def test_only_on_linux(self, *args):
        self.run_check(self.config)

        # Shouldn't have any metrics on non-Linux platforms
        self.assertEqual(len(self.service_checks), 0)
        self.assertMetric('package.up_to_date.change', count=0)

    @mock.patch('outdated_packages.OutdatedPackagesCheck.get_package_version', return_value='2.0.0')
    @mock.patch('outdated_packages.OutdatedPackagesCheck.is_package_installed', return_value=True)
    def test_package_is_up_to_date(self, *args):
        self.config['instances'].append({
            'package': 'foo',
            'version': {
                'precise': '1.0.0',
                'trusty': '1.0.0',
            },
        })
        self.run_check(self.config)

        # Package is newer than the expected value - should be good
        self.assertServiceCheckOK(
            'package.up_to_date',
            tags=['package:foo', 'expected_version:1.0.0'],
            count=1
        )

    @mock.patch('outdated_packages.OutdatedPackagesCheck.get_package_version', return_value='1.0.0')
    @mock.patch('outdated_packages.OutdatedPackagesCheck.is_package_installed', return_value=True)
    def test_package_is_outdated(self, *args):
        self.config['instances'].append({
            'package': 'bar',
            'version': {
                'precise': '1.3.5',
                'trusty': '1.3.5',
            },
        })
        self.run_check(self.config)

        # Package is older than the expected value - should error
        self.assertServiceCheckCritical(
            'package.up_to_date',
            tags=['package:bar', 'expected_version:1.3.5'],
            count=1
        )

    @mock.patch('outdated_packages.OutdatedPackagesCheck.get_package_version', return_value='2.0.0')
    @mock.patch('outdated_packages.OutdatedPackagesCheck.is_package_installed', return_value=False)
    def test_package_does_not_exist(self, *args):
        self.config['instances'].append({
            'package': 'foo',
            'version': {
                'precise': '1.0.0',
                'trusty': '1.0.0',
            },
        })
        self.run_check(self.config)

        self.assertEqual(len(self.service_checks), 0)
        self.assertMetric('package.up_to_date.change', count=0)

    @mock.patch('outdated_packages.OutdatedPackagesCheck.get_lsb_codename', return_value='trusty')
    @mock.patch('outdated_packages.OutdatedPackagesCheck.get_package_version', return_value='1.0.0')
    @mock.patch('outdated_packages.OutdatedPackagesCheck.is_package_installed', return_value=True)
    def test_unknown_release(self, *args):
        self.config['instances'].append({
            'package': 'foo',
            'version': {
                'utopic': '1.0.0',
            },
        })
        self.run_check(self.config)

        self.assertServiceCheckUnknown(
            'package.up_to_date',
            tags=['package:foo'],
            count=1
        )

    @mock.patch('outdated_packages.OutdatedPackagesCheck.get_lsb_codename', return_value='trusty')
    @mock.patch('outdated_packages.OutdatedPackagesCheck.get_package_version', return_value='2.0.0')
    @mock.patch('outdated_packages.OutdatedPackagesCheck.is_package_installed', return_value=True)
    def test_correct_release(self, *args):
        self.config['instances'].append({
            'package': 'foo',
            'version': {
                'precise': '1.0.0',
                'trusty': '3.0.0',
            },
        })
        self.run_check(self.config)

        # The check should succeed if we're on Precise, since the expected
        # version is older than the current one.  It should fail on Trusty,
        # since we are thus out of date.
        self.assertServiceCheckCritical(
            'package.up_to_date',
            tags=['package:foo', 'expected_version:3.0.0'],
            count=1
        )
