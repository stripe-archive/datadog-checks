import requests

from checks import AgentCheck


class Sequins(AgentCheck):
    DEFAULT_TIMEOUT = 1
    DEFAULT_MAX_DBS = 100
    CONNECT_CHECK_NAME = 'sequins.can_connect'

    def check(self, instance):
        if 'url' not in instance:
            self.log.info("Skipping instance, no url found.")
            return

        instance_tags = instance.get('tags', [])
        max_dbs = instance.get('max_dbs', self.DEFAULT_MAX_DBS)
        timeout = self.init_config.get('default_timeout', self.DEFAULT_TIMEOUT)
        resp = self.get_json(instance['url'], timeout)
        db_names = set(resp['dbs'].keys())

        requests_by_db = {}
        if 'debug_url' in instance:
            expvar_url = instance['debug_url'] + '/debug/vars'
            expvar = self.get_json(expvar_url, timeout)
            requests_by_db = expvar.get('sequins', {}).get('ByDB', {})
            db_names |= set(requests_by_db.keys())

        self.gauge('sequins.db_count', len(resp['dbs']), tags=instance_tags)
        for db_name in db_names:
            db_tags = instance_tags + ['sequins_db:%s' % db_name]

            if db_name in resp['dbs']:
                db = resp['dbs'][db_name]
                num_dbs = len(db['versions'])
                if num_dbs > max_dbs:
                    raise Exception("%d dbs is more than the configured maximum (%d)" % (num_dbs, max_dbs))

                self.gauge('sequins.version_count', num_dbs, db_tags)

                for version_name, version in db['versions'].iteritems():
                    version_tags = db_tags + ['sequins_version:%s' % version_name]
                    self.gauge('sequins.partition_count', version['num_partitions'], version_tags)
                    self.gauge('sequins.missing_partition_count', version['missing_partitions'], version_tags)
                    self.gauge('sequins.underreplicated_partition_count', version['underreplicated_partitions'], version_tags)
                    self.gauge('sequins.overreplicated_partition_count', version['overreplicated_partitions'], version_tags)
                    self.gauge('sequins.average_replication', version['average_replication'], version_tags)

                    node_counts = {}
                    for node in version['nodes'].itervalues():
                        st = node['state']
                        node_counts[st] = node_counts.get(st, 0) + 1

                    for state, count in node_counts.iteritems():
                        tags = version_tags + ['sequins_node_state:%s' % state.lower()]
                        self.gauge('sequins.node_count', count, tags)

            if db_name in requests_by_db:
                self.count('sequins.requests_by_db', requests_by_db[db_name] * 60, db_tags)

        if 'shard_id' in resp:
            self.gauge('sequins.shard_id', 1, instance_tags + ['sequins_shard:%s' % resp['shard_id']])

    def get_json(self, url, timeout):
        try:
            r = requests.get(url, timeout=timeout, headers={'accept': 'application/json'})
            r.raise_for_status()
        except requests.exceptions.Timeout:
            # If there's a timeout
            self.service_check(
                self.CONNECT_CHECK_NAME, AgentCheck.CRITICAL,
                message='%s timed out after %s seconds.' % (url, timeout),
                tags=["url:{0}".format(url)]
            )
            raise Exception("Timeout when hitting %s" % url)

        except requests.exceptions.HTTPError:
            self.service_check(
                self.CONNECT_CHECK_NAME, AgentCheck.CRITICAL,
                message='%s returned a status of %s' % (url, r.status_code),
                tags=["url:{0}".format(url)]
            )
            raise Exception("Got %s when hitting %s" % (r.status_code, url))

        else:
            self.service_check(
                self.CONNECT_CHECK_NAME, AgentCheck.OK,
                tags=["url:{0}".format(url)]
            )

        return r.json()
