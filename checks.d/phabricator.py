# Fetch metrics from Phabricator, using our MetricsExtension (not yet available)

# stdlib
from collections import namedtuple
import urlparse

# 3p
import requests

# project
from checks import AgentCheck
from util import headers

PhabricatorInstanceConfig = namedtuple(
    'PhabricatorInstanceConfig', [
        'service_check_tags',
        'tags',
        'timeout',
        'url'
    ]
)

class NodeNotFound(Exception):
    pass


class PhabCheck(AgentCheck):
    SERVICE_CHECK_CONNECT_NAME = 'phabricator.can_connect'
    DEFAULT_TIMEOUT = 5

    def __init__(self, name, init_config, agentConfig, instances=None):
        AgentCheck.__init__(self, name, init_config, agentConfig, instances)

    def get_instance_config(self, instance):
        url = instance.get('url')
        if url is None:
            raise Exception("An url must be specified in the instance")

        # Support URLs that have a path in them from the config, for
        # backwards-compatibility.
        parsed = urlparse.urlparse(url)
        if parsed[2] != "":
            url = "%s://%s" % (parsed[0], parsed[1])
        port = parsed.port
        host = parsed.hostname

        custom_tags = instance.get('tags', [])
        service_check_tags = [
            'host:%s' % host,
            'port:%s' % port
        ]
        service_check_tags.extend(custom_tags)

        # Tag by URL so we can differentiate the metrics
        # from multiple instances
        tags = ['url:%s' % url]
        tags.extend(custom_tags)

        timeout = instance.get('timeout', self.DEFAULT_TIMEOUT)

        config = PhabricatorInstanceConfig(
            service_check_tags=service_check_tags,
            tags=tags,
            timeout=timeout,
            url=url
        )

        return config

    def check(self, instance):
        config = self.get_instance_config(instance)

        # Fetch from the metrics endpoint the list of items in the queue
        metrics_url = urlparse.urljoin(config.url, "/metrics/")
        metrics_data = self._get_data(metrics_url, config)

        self._process_queue_data(metrics_data, config)

        self.service_check(
            self.SERVICE_CHECK_CONNECT_NAME,
            AgentCheck.OK,
            tags=config.service_check_tags
        )

    def _get_data(self, url, config, send_sc=True):
        """ Hit a given URL and return the parsed json
        """
        try:
            resp = requests.get(
                url,
                timeout=config.timeout,
                headers=headers(self.agentConfig)
            )
            resp.raise_for_status()
        except Exception as e:
            if send_sc:
                self.service_check(
                    self.SERVICE_CHECK_CONNECT_NAME,
                    AgentCheck.CRITICAL,
                    message="Error {0} when hitting {1}".format(e, url),
                    tags=config.service_check_tags
                )
            raise

        return resp.json()

    def _process_queue_data(self, data, config):
        metric = 'phabricator.queued.count'

        tags = list(config.tags)

        for task in data.get('queued', []):
          for worker_class, count in task.iteritems():
            tags.append("worker:%s" % worker_class)
            self.gauge(metric, count, tags=tags)

