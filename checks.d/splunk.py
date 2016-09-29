# stdlib
import time
from collections import Counter
from urlparse import urljoin

# 3rd party
import requests
from requests.auth import HTTPBasicAuth

# project
from checks import AgentCheck

class Splunk(AgentCheck):

    DEFAULT_TIMEOUT = 5
    CONNECT_CHECK_NAME = 'splunk.can_connect'
    INDEX_HEALTH_CHECK_NAME = 'splunk.index.is_healthy'
    PEER_HEALTH_CHECK_NAME = 'splunk.peer.is_healthy'

    def check(self, instance):
        # if 'url' not in instance:
        #     raise Exception('Splunk instance missing "url" value.')

        # Load values from the instance config
        url = instance['url']
        instance_tags = instance.get('tags', [])
        default_timeout = self.init_config.get('default_timeout', self.DEFAULT_TIMEOUT)
        username = instance.get('username')
        password = instance.get('password')
        timeout = float(instance.get('timeout', default_timeout))

        self.do_index_metrics(url, username, password, timeout)
        self.do_peer_metrics(url, username, password, timeout)

    def do_peer_metrics(self, url, username, password, timeout):
        response = self.get_json(url, '/services/cluster/master/peers', username, password, timeout)
        for peer in response['entry']:
            host = peer['content']['label']
            site = peer['content']['site']
            searchable = peer['content']['is_searchable']

            if searchable == 'false':
                status = 'Host %s is not searchable.' % (host)

            tags = [
                'peer_name:{0}'.format(host),
                'site:{0}'.format(site),
            ]

            self.increment('splunk.peers.peers_present', 1, tags=tags + [
                'searchable:{0}'.format(searchable),
                'status:{0}'.format(peer['content']['status'])
            ])

            self.gauge('splunk.peers.delayed_buckets_to_discard', peer['content']['delayed_buckets_to_discard'], tags=tags)
            self.gauge('splunk.peers.fixup_set', len(peer['content']['fixup_set']), tags=tags)
            self.gauge('splunk.peers.pending_job_count', peer['content']['pending_job_count'], tags=tags)
            self.gauge('splunk.peers.primary_count', peer['content']['primary_count'], tags=tags)
            self.gauge('splunk.peers.primary_count_remote', peer['content']['primary_count_remote'], tags=tags)
            self.gauge('splunk.peers.replication_count', peer['content']['replication_count'], tags=tags)

            if peer['content']['bucket_count_by_index'] is not None:
                for bucket, count in peer['content']['bucket_count_by_index'].items():
                    self.gauge('splunk.peers.bucket_count', count, tags=tags + ['index:{0}'.format(bucket)])

            if peer['content']['status_counter'] is not None:
                for status, count in peer['content']['status_counter'].items():
                    self.gauge('splunk.peers.bucket_status', count, tags=tags + ['bucket_status:{0}'.format(status)])

            if status is not None:
                self.service_check(self.PEER_HEALTH_CHECK_NAME, AgentCheck.CRITICAL,
                    message=status,
                    tags = [ 'peer_name:' + host ])


    def do_index_metrics(self, url, username, password, timeout):
        response = self.get_json(url, '/services/cluster/master/indexes', username, password, timeout)
        for index in response['entry']:
            name = index['name']
            searchable = 'true' if index['content']['is_searchable'] == '1' else 'false'
            # We'll use this as a sigil for index health at the end of the loop
            status = None

            if searchable == 'false':
                status = 'Index %s is not searchable.' % (name)

            tags = [
                'index_name:{0}'.format(name),
                'searchable:{0}'.format(searchable)
            ]

            self.gauge('splunk.indexes.size_bytes', index['content']['index_size'], tags=tags)
            self.gauge('splunk.indexes.total_excess_bucket_copies', index['content']['total_excess_bucket_copies'], tags=tags)
            self.gauge('splunk.indexes.total_excess_searchable_copies', index['content']['total_excess_searchable_copies'], tags=tags)

            for index_index, index_copy in index['content']['replicated_copies_tracker'].items():
                index_tags = tags + [ 'copy_index:{0}'.format(index_index) ]
                actual_copies = int(index_copy['actual_copies_per_slot'])
                expected_copies = int(index_copy['expected_total_per_slot'])
                self.gauge('splunk.indexes.replication.actual_copies', actual_copies, tags=index_tags)
                self.gauge('splunk.indexes.replication.expected_copies', expected_copies, tags=index_tags)

                if actual_copies != expected_copies:
                    status = 'Index %s is not correctly replicated.'

            if status is not None:
                self.service_check(self.INDEX_HEALTH_CHECK_NAME, AgentCheck.CRITICAL,
                    message=status,
                    tags = [ 'index_name:' + name ])

    def get_json(self, url, path, username, password, timeout):
        # For future reference
        # 'search': 'search earliest=-10@s | eval size=len(_raw) | stats sum(size) by host, source',
        # params
        #     'adhoc_search_level': 'fast',
        #     'exec_mode': 'oneshot'
        try:
            start_time = time.time()
            r = requests.get(urljoin(url, path), verify=False, timeout=timeout, auth=HTTPBasicAuth(username, password), data={
                'output_mode': 'json',
            })
            r.raise_for_status()
            elapsed_time = time.time() - start_time
            self.histogram('splunk.stats_fetch_duration_seconds', int(elapsed_time), tags = { 'path': path })
        except requests.exceptions.Timeout:
            # If there's a timeout
            self.service_check(self.CONNECT_CHECK_NAME, AgentCheck.CRITICAL,
                message='Timed out after %s seconds.' % (timeout),
                tags = [])
            raise Exception("Timeout when hitting URL")

        except requests.exceptions.HTTPError:
            print(r.text)
            self.service_check(self.CONNECT_CHECK_NAME, AgentCheck.CRITICAL,
                message='Returned a status of %s' % (r.status_code),
                tags = [])
            raise Exception("Got %s when hitting URL" % (r.status_code))

        else:
            self.service_check(self.CONNECT_CHECK_NAME, AgentCheck.OK,
                tags = []
            )
        return r.json()
