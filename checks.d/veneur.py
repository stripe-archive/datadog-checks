import datetime
from urlparse import urljoin
import requests

# project
from checks import AgentCheck

class Veneur(AgentCheck):

    VERSION_METRIC_NAME = 'veneur.deployed_version'
    BUILDAGE_METRIC_NAME = 'veneur.build_age'

    def check(self, instance):
        success = 0

        host = instance['host']

        try:
            r = requests.get(urljoin(host, '/version'))
            sha = r.text
            success = 1

            r = requests.get(urljoin(host, '/builddate'))
            builddate = datetime.datetime.fromtimestamp(int(r.text))

            tdelta = datetime.datetime.now() - builddate

        except:
            success = 0
            raise
        finally:
            self.gauge(self.VERSION_METRIC_NAME, success, tags = ['sha:{0}'.format(sha)])
            self.histogram(self.BUILDAGE_METRIC_NAME, tdelta.seconds)
