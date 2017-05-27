import subprocess

from checks import AgentCheck


class FileCheck(AgentCheck):
    SERVICE_CHECK_NAME = 'unbound'

    def get_stats(self):
        cmd = 'sudo unbound-control stats'
        try:
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
        except subprocess.CalledProcessError as e:
            error_msg = 'ERROR CALLING {0}: {1}  {2}'.format(cmd, e, e.output)
            self.service_check(
                self.SERVICE_CHECK_NAME,
                AgentCheck.CRITICAL,
                message=error_msg,
            )
            self.log.error()
            return None

        return output

    def check(self, instance):
        stats = self.get_stats()

        if stats is None:
            return

        try:
            for line in stats.split("\n"):
                if not line:
                    continue
                metric_name, amount = line.split('=')
                tagged_name = "unbound.{0}".format(metric_name)
                self.gauge(tagged_name, float(amount))
        except Exception as e:
            self.service_check(
                self.SERVICE_CHECK_NAME,
                AgentCheck.CRITICAL,
                message="Error when parsing unbound stats: {0}".format(e),
            )
            return

        self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.OK)

