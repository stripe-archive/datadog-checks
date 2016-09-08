import mock

from checks import AgentCheck
from tests.checks.common import AgentCheckTest, load_check


class TestFileUnit(AgentCheckTest):
    CHECK_NAME = 'vulnerable_packages'

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

    @mock.patch('vulnerable_packages.VulnerablePackagesCheck.get_package_version', return_value='2.0.0')
    def test_package_is_up_to_date(self, *args):
        self.config['instances'].append({
            'package': 'foo',
            'version': '1.0.0',
        })
        self.run_check(self.config)

        # Package is newer than the expected value - should be good
        self.assertServiceCheckOK(
            'package.up_to_date',
            tags=['package:foo', 'expected_version:1.0.0'],
            count=1
        )

    @mock.patch('vulnerable_packages.VulnerablePackagesCheck.get_package_version', return_value='1.0.0')
    def test_package_is_outdated(self, *args):
        self.config['instances'].append({
            'package': 'bar',
            'version': '1.3.5',
        })
        self.run_check(self.config)

        # Package is older than the expected value - should error
        self.assertServiceCheckCritical(
            'package.up_to_date',
            tags=['package:bar', 'expected_version:1.3.5'],
            count=1
        )
