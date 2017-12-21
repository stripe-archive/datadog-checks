# project
from checks import AgentCheck
from utils.platform import Platform

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
        try:
            num_updates = int(num_updates)
            num_security = int(num_security)
        except ValueError as e:
            self.log.debug("Could not convert to integer: {0}".format(e))
            return

        # We create "boolean" versions of these metrics because Datadog doesn't
        # seem to have a way to compute them in queries.

        self.gauge('updates.available', num_updates)
        self.gauge('updates.available.boolean', 1 if num_updates > 0 else 0)

        self.gauge('updates.security', num_security)
        self.gauge('updates.security.boolean', 1 if num_security > 0 else 0)

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
