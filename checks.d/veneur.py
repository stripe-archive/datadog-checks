import datetime
from urlparse import urljoin
import requests

# project
from checks import AgentCheck

class Veneur(AgentCheck):

    VERSION_METRIC_NAME = 'veneur.deployed_version'
    BUILDAGE_METRIC_NAME = 'veneur.build_age_seconds'
    ERROR_METRIC_NAME = 'veneur.agent_check.errors_total'

    def check(self, instance):
        success = 0

        host = instance['host']
        tags = instance.get('tags', [])

        try:
            r = requests.get(urljoin(host, '/version'))
            tags.extend(['sha:{0}'.format(r.text)])
            success = 1

            r = requests.get(urljoin(host, '/builddate'))
            builddate = datetime.datetime.fromtimestamp(int(r.text))

            tdelta = datetime.datetime.now() - builddate
            self.gauge(self.BUILDAGE_METRIC_NAME, tdelta.total_seconds())

        except:
            success = 0
            self.increment(self.ERROR_METRIC_NAME)
            raise
        finally:
            self.gauge(self.VERSION_METRIC_NAME, success, tags = tags)
