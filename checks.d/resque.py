# project
from checks import AgentCheck

import redis

class ResqueVMCheck(AgentCheck):

    SCALAR_KEYS = {
        'resque:stat:failed': 'resque.jobs.failed_total',
        'resque:stat:processed': 'resque.jobs.processed_total',
    }

    CARD_KEYS = {
        'resque:queues': 'resque.queues_count',
        'resque:workers': 'resque.worker_count',
    }

    def check(self, instance):
        tags = instance.get('tags', [])

        host = instance.get('host')
        port = instance.get('port')

        conn = redis.Redis(host=host, port=port)

        # Get scalars
        for key, name in self.SCALAR_KEYS.iteritems():
            value = conn.get(key) or 0
            self.monotonic_count(name, int(value))

        # Get set cardinality
        for key, name in self.CARD_KEYS.iteritems():
            value = conn.scard(key) or 0
            self.gauge(name, int(value))

        del conn
