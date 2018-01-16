import subprocess

from checks import AgentCheck


class Veneur(AgentCheck):

    KERNEL_METRIC_NAME = 'linux.kernel'
    ERROR_METRIC_NAME = 'linux.kernel.agent_check.errors_total'

    def get_kernel_version(self):
        return subprocess.check_output(['uname', '-r']).strip()

    def get_linux_release(self):
        return subprocess.check_output(['lsb_release', '-sc']).strip()

    def get_grub_menu_lines(self):
        with open("/boot/grub/menu.lst") as menu_fh:
            return menu_fh.readlines()

    def get_grub_default(self):
        try:
            menu_lines = self.get_grub_menu_lines()
            default_line = next(l for l in menu_lines
                                if l.startswith("title"))
            grub_default = default_line.split()[-1]
        except:
            # Ignore failures for grub default since it could
            # be a different format
            pass

        return grub_default

    def check(self, instance):
        success = 0
        grub_default = 'unknown'
        kernel = 'unknown'
        release = 'unknown'

        try:
            kernel = self.get_kernel_version()
            release = self.get_linux_release()
            grub_default = self.get_grub_default()
            success = 1
        except:
            self.increment(self.ERROR_METRIC_NAME)
            raise
        finally:
            tags = instance.get('tags', [])
            tags.extend([
                'kernel:{}'.format(kernel),
                'release:{}'.format(release),
                'grub_default:{}'.format(grub_default),
            ])
            self.gauge(self.KERNEL_METRIC_NAME, success, tags=tags)
