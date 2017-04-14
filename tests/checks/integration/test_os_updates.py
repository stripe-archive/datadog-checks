# 3p
import mock

# project
from tests.checks.common import AgentCheckTest


class TestFileUnit(AgentCheckTest):
    CHECK_NAME = 'os_updates'

    def __init__(self, *args, **kwargs):
        AgentCheckTest.__init__(self, *args, **kwargs)
        self.config = {
            "init_config": {},
            "instances": [{}]
        }

    @mock.patch('os_updates.UpdatesCheck.get_subprocess_output', return_value='2;1')
    @mock.patch('os_updates.UpdatesCheck.get_reboot_required_flag_status', return_value=True)
    def test_basic_check(self, *args):
        self.run_check(self.config)

        self.assertMetric('updates.available', value=2)
        self.assertMetric('updates.security', value=1)
        self.assertMetric('updates.reboot_required', value=1)

    @mock.patch('os_updates.UpdatesCheck.get_subprocess_output', return_value=None)
    @mock.patch('os_updates.UpdatesCheck.get_reboot_required_flag_status', return_value=None)
    def test_no_error_if_no_binary(self, *args):
        self.run_check(self.config)

        # Shouldn't have any metrics if we can't fetch anything
        self.assertMetric('updates.available', count=0)
        self.assertMetric('updates.security', count=0)
        self.assertMetric('updates.reboot_required', count=0)

    @mock.patch('os_updates.UpdatesCheck.get_subprocess_output', return_value='not-splittable')
    @mock.patch('os_updates.UpdatesCheck.get_reboot_required_flag_status', return_value=None)
    def test_no_error_if_bad_format(self, *args):
        self.run_check(self.config)
        self.assertMetric('updates.available', count=0)
        self.assertMetric('updates.security', count=0)
        self.assertMetric('updates.reboot_required', count=0)

    @mock.patch('os_updates.UpdatesCheck.get_subprocess_output', return_value='a;b')
    @mock.patch('os_updates.UpdatesCheck.get_reboot_required_flag_status', return_value='a')
    def test_no_error_if_not_numeric(self, *args):
        self.run_check(self.config)
        self.assertMetric('updates.available', count=0)
        self.assertMetric('updates.security', count=0)
        self.assertMetric('updates.reboot_required', count=0)

    @mock.patch('utils.platform.Platform.is_linux', return_value=False)
    def test_only_on_linux(self, *args):
        self.run_check(self.config)

        # Shouldn't have any metrics on non-Linux platforms
        self.assertMetric('updates.available', count=0)
        self.assertMetric('updates.security', count=0)
