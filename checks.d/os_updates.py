# project
from checks import AgentCheck
from utils.platform import Platform

import os
import subprocess


class UpdatesCheck(AgentCheck):

    def check(self, instance):
        if not Platform.is_linux():
            return

        output = self.get_subprocess_output()
        if output is None:
            return

        parts = output.split(';', 1)
        if len(parts) != 2:
            self.log.debug("Unknown format: {0}".format(output))
            return

        num_updates, num_security = parts
        reboot_required = self.get_reboot_required_flag_status()
        try:
            num_updates = int(num_updates)
            num_security = int(num_security)
            reboot_required = int(reboot_required)
        except ValueError as e:
            self.log.debug("Could not convert to integer: {0}".format(e))
            return

        self.gauge('updates.available', num_updates)
        self.gauge('updates.security', num_security)
        self.gauge('updates.reboot_required', reboot_required)

    def get_subprocess_output(self):
        """
        Run apt-check and get the output.
        In a different method for easier unit-testing.
        """
        try:
            output = subprocess.check_output([
                '/usr/lib/update-notifier/apt-check',
            ], stderr=subprocess.STDOUT)
            self.log.debug("Ran apt-check: {0}".format(output))
            return output

        except subprocess.CalledProcessError as e:
            self.log.debug("Could not run apt-check: {0}".format(e.returncode))
            return None

    def get_reboot_required_flag_status(self):
        return os.path.isfile('/var/run/reboot-required')
