# Ensures that package are up-to-date, according to some configuration

import time
import subprocess

from checks import AgentCheck
from utils.platform import Platform


SUPPORTED_RELEASES = frozenset([
    'precise',
    'trusty',
    'utopic',
    'vivid',
])


class VulnerablePackagesCheck(AgentCheck):

    def __init__(self, name, init_config, agentConfig, instances=None):
        AgentCheck.__init__(self, name, init_config, agentConfig, instances)
        self._last_state_by_package = {}

    def has_different_status(self, package, current):
        last_state = self._last_state_by_package.get(package, None)
        self._last_state_by_package[package] = current
        return (last_state is not None and last_state != current)

    def get_lsb_codename(self):
        return subprocess.check_output(['lsb_release', '-cs']).strip()

    def get_package_version(self, package_name):
        """
        Gets the current version of a package.
        """
        cmd = ['dpkg-query', '-W', '-f', '${Version}', package_name]
        return subprocess.check_output(cmd)

    def version_compare(self, version_a, comparison, version_b):
        cmd = ['dpkg', '--compare-versions', version_a, comparison, version_b]
        ret = subprocess.call(cmd)
        if ret == 0:
            return True
        elif ret == 1:
            return False

        # Some other error
        raise subprocess.CalledProcessError(
            ret,
            subprocess.list2cmdline(cmd),
            None
        )

    def check(self, instance):
        """
        Checks for a vulnerable package and emits a service_check based on
        whether it's up-to-date.
        """
        if 'package' not in instance:
            raise Exception("Missing 'package' in vulnerable package check config")
        if 'version' not in instance:
            raise Exception("Missing 'version' in vulnerable package check config")

        if not Platform.is_linux():
            return

        codename = self.get_lsb_codename()
        if codename not in SUPPORTED_RELEASES:
            raise Exception("Release not supported: {0}".format(codename))

        # Inputs
        package = instance["package"]
        expected_versions = instance["version"]

        # Default (successful) outputs
        tags = ['package:' + package]
        msg = "Package {0} is up-to-date".format(package)
        status = 'current'
        check_status = AgentCheck.OK

        # Handle unknown releases
        expected_version = expected_versions.get(codename)
        if expected_version is not None:
            tags.append('expected_version:' + expected_version)

            curr_version = self.get_package_version(package)
            up_to_date = self.version_compare(curr_version, 'ge', expected_version)

            if not up_to_date:
                status = 'outdated'
                check_status = AgentCheck.CRITICAL
                msg = "Package '{0}' is outdated: current version {1} is older than expected version {2}".format(
                    package,
                    curr_version,
                    expected_version,
                )
        else:
            status = 'unknown'
            check_status = AgentCheck.UNKNOWN
            msg = "Package '{0}' does not specify version for release: {1}".format(package, codename)

        self.service_check('package.up_to_date', check_status, message=msg, tags=tags)

        # Emit an event if the previous state is known & it's different:
        if self.has_different_status(package, status):
            timestamp = time.time()
            alert_type = 'success'
            if check_status != AgentCheck.OK:
                alert_type = 'error'

            title = "Package '{0}' is now: {1}".format(
                package,
                status
            )
            self.event({
                'timestamp': timestamp,
                'event_type': 'package.up_to_date.change',
                'msg_title': title,
                'alert_type': alert_type,
                'tags': tags,
                'aggregation_key': package,
            })
