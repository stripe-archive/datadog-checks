import datetime
from urlparse import urljoin
import requests

# project
from checks import AgentCheck

class Veneur(AgentCheck):

    VERSION_METRIC_NAME = 'veneur.deployed_version'
    BUILDAGE_METRIC_NAME = 'veneur.build_age'

    MAX_AGE_CHECK_NAME = 'veneur.build_age.fresh'

    # Check that the build is no more than one week old
    MAX_DEPLOYMENT_INTERVAL = 604800


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

            if tdelta.seconds > self.MAX_DEPLOYMENT_INTERVAL:
                self.service_check(self.MAX_AGE_CHECK_NAME, AgentCheck.CRITICAL,
                        message='Build date {0} is too old (build must be no more than {1} seconds old)'.format(builddate.strftime('%Y-%m-%d %H:%M:%S'), self.MAX_DEPLOYMENT_INTERVAL))

        except:
            success = 0
            raise
        finally:
            self.gauge(self.VERSION_METRIC_NAME, success, tags = ['sha:{0}'.format(sha)])
            self.histogram(self.BUILDAGE_METRIC_NAME, tdelta.seconds)
