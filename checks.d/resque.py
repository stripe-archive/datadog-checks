# project
from checks import AgentCheck

import redis

class ResqueVMCheck(AgentCheck):

    SCALAR_KEYS = {
        'resque:stat:failed': 'resque.jobs_failed',
        'resque:stat:processed': 'resque.jobs_processed',
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
            value = conn.get(key)
            self.gauge(name, value)

        # Get set cardinality
        for key, name in self.CARD_KEYS.iteritems():
            value = conn.scard(key)
            self.gauge(name, value)

        del conn
