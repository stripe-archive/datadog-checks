# stdlib
import time
from urlparse import urljoin

# 3rd party
import requests

# project
from checks import AgentCheck

class JenkinsMetrics(AgentCheck):

    DEFAULT_TIMEOUT = 5
    CONNECT_CHECK_NAME = 'jenkins.can_connect'

    def check(self, instance):
        if 'url' not in instance:
            raise Exception('Jenkins instance missing "url" value.')

        # Load values from the instance config
        url = instance['url']
        instance_tags = instance.get('tags', [])
        default_timeout = self.init_config.get('default_timeout', self.DEFAULT_TIMEOUT)
        timeout = float(instance.get('timeout', default_timeout))

        response = self.get_json(url, timeout)
        if response is not None:
            if not response.get('gauges'):
                for key, value in response.iteritems():
                    if value.get('healthy'):
                        self.service_check('jenkins.healthcheck.' + key, AgentCheck.OK, message = value.get('message'), tags = [])
                    else:
                        self.service_check('jenkins.healthcheck.' + key, AgentCheck.CRITICAL, message = value.get('message'), tags = [])
            else:
                for m in response['gauges']:
                    if m.startswith("vm."):
                        if m.startswith("vm.gc."):
                            self.monotonic_count('jenkins.' + m, response['gauges'][m]['value'], tags=instance_tags)
                        else:
                            self.gauge('jenkins.' + m, response['gauges'][m]['value'], tags=instance_tags)

    def get_json(self, url, timeout):
        try:
            start_time = time.time()
            r = requests.get(url, timeout=timeout)
            r.raise_for_status()
            elapsed_time = time.time() - start_time
            self.histogram('jenkins.stats_fetch_duration_seconds', int(elapsed_time))
        except requests.exceptions.Timeout:
            # If there's a timeout
            self.service_check(self.CONNECT_CHECK_NAME, AgentCheck.CRITICAL,
                message='Timed out after %s seconds.' % (timeout),
                tags = [])
            raise Exception("Timeout when hitting URL")

        except requests.exceptions.HTTPError:
            self.service_check(self.CONNECT_CHECK_NAME, AgentCheck.CRITICAL,
                message='Returned a status of %s' % (r.status_code),
                tags = [])
            raise Exception("Got %s when hitting URL" % (r.status_code))

        else:
            self.service_check(self.CONNECT_CHECK_NAME, AgentCheck.OK,
                tags = []
            )

        return r.json()
