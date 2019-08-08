
# project
from tests.checks.common import AgentCheckTest, load_check


class TestKernelUnit(AgentCheckTest):
    CHECK_NAME = 'kernel'

    def test_check_exists(self):
        conf = {}
        load_check(self.CHECK_NAME, conf, {})

    def test_output(self):
        conf = {
            'init_config': {},
            'instances': [
                {}
            ]
        }

        def get_linux_release():
            return 'xenial'

        def get_kernel_version():
            return '1.2.3.4-generic'

        def get_grub_menu_lines():
            return [
                '# title stuff about grub \n',
                'some other stufff\n',
                'title\t\tUbuntu 16.04.5 LTS, kernel 1.2.3.3-generic\n',
            ]

        self.run_check(conf, mocks={
            'get_linux_release': get_linux_release,
            'get_kernel_version': get_kernel_version,
            'get_grub_menu_lines': get_grub_menu_lines,
        })

        self.assertMetric("linux.kernel", value=1, metric_type='gauge',
                          tags=['kernel:1.2.3.4-generic',
                                'release:xenial',
                                'grub_default:1.2.3.3-generic'])

    def test_output_no_grub(self):
        conf = {
            'init_config': {},
            'instances': [
                {}
            ]
        }

        def get_linux_release():
            return 'xenial'

        def get_kernel_version():
            return '1.2.3.4-generic'

        def get_grub_menu_lines():
            return [
                '# title stuff about grub \n',
                'no title here\n',
            ]

        self.run_check(conf, mocks={
            'get_linux_release': get_linux_release,
            'get_kernel_version': get_kernel_version,
            'get_grub_menu_lines': get_grub_menu_lines,
        })

        self.assertMetric("linux.kernel", value=1, metric_type='gauge',
                          tags=['kernel:1.2.3.4-generic',
                                'release:xenial',
                                'grub_default:unknown'])
