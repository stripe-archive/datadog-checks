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
    INDEX_REPL_HEALTH_CHECK_NAME = 'splunk.index_copy.is_replicated'
    INDEX_SEARCH_HEALTH_CHECK_NAME = 'splunk.index_copy.is_searchable'
    PEER_HEALTH_CHECK_NAME = 'splunk.peer.is_healthy'

    def check(self, instance):
        # if 'url' not in instance:
        #     raise Exception('Splunk instance missing "url" value.')

        # Load values from the instance config
        url = instance['url']
        instance_tags = instance.get('tags', []) + ['instance:{0}'.format(url)]
        default_timeout = self.init_config.get('default_timeout', self.DEFAULT_TIMEOUT)
        username = instance.get('username')
        password = instance.get('password')
        timeout = float(instance.get('timeout', default_timeout))

        self.do_index_metrics(instance_tags, url, username, password, timeout)
        self.do_peer_metrics(instance_tags, url, username, password, timeout)

    def do_peer_metrics(self, instance_tags, url, username, password, timeout):
        response = self.get_json(url, '/services/cluster/master/peers', instance_tags, username, password, timeout)
        for peer in response['entry']:
            host = peer['content']['label']
            site = peer['content']['site']

            tags = instance_tags + [
                'peer_name:{0}'.format(host),
                'site:{0}'.format(site),
            ]

            searchable = peer['content']['is_searchable']
            if not searchable:
                self.service_check(self.PEER_HEALTH_CHECK_NAME, AgentCheck.CRITICAL,
                    message='Host {0} is not searchable.'.format(host),
                    tags = tags)
            else:
                self.service_check(self.PEER_HEALTH_CHECK_NAME, AgentCheck.OK,
                    tags = tags)


            # This is a synthetic metric to make it easier to count the number of peers
            # in twhatever status. It's a counter so that you can view it `as count`
            # in a chart or monitor and get a reasonable visualization. The rate
            # is obviously useless.
            self.increment('splunk.peers.peers_present', 1, tags=tags + [
                'searchable:{0}'.format(str(searchable)),
                'status:{0}'.format(peer['content']['status'])
            ])

            self.gauge('splunk.peers.delayed_buckets_to_discard', peer['content']['delayed_buckets_to_discard'], tags=tags)
            self.gauge('splunk.peers.primary_count', peer['content']['primary_count'], tags=tags)
            self.gauge('splunk.peers.primary_count_remote', peer['content']['primary_count_remote'], tags=tags)
            self.gauge('splunk.peers.replication_count', peer['content']['replication_count'], tags=tags)

            if peer['content']['bucket_count_by_index'] is not None:
                for bucket, count in peer['content']['bucket_count_by_index'].items():
                    self.gauge('splunk.peers.bucket_count', count, tags=tags + ['index:{0}'.format(bucket)])

            if peer['content']['status_counter'] is not None:
                for status, count in peer['content']['status_counter'].items():
                    self.gauge('splunk.peers.bucket_status', count, tags=tags + ['bucket_status:{0}'.format(status)])

    def do_index_metrics(self, instance_tags, url, username, password, timeout):
        response = self.get_json(url, '/services/cluster/master/indexes', instance_tags, username, password, timeout)
        for index in response['entry']:
            name = index['name']

            tags = instance_tags + [
                'index_name:{0}'.format(name)
            ]

            # Yes, in this version of Splunk this is a number as a string instead
            # of a boolean. Maybe they'll fix this and break the integration?
            if index['content']['is_searchable'] != '1':
                self.service_check(self.INDEX_HEALTH_CHECK_NAME, AgentCheck.CRITICAL,
                    message='Index {0} is not searchable.'.format(name),
                    tags = tags)
            else:
                self.service_check(self.INDEX_HEALTH_CHECK_NAME, AgentCheck.OK,
                    tags = tags)

            self.gauge('splunk.indexes.size_bytes', index['content']['index_size'], tags=tags)
            self.gauge('splunk.indexes.total_excess_bucket_copies', index['content']['total_excess_bucket_copies'], tags=tags)
            self.gauge('splunk.indexes.total_excess_searchable_copies', index['content']['total_excess_searchable_copies'], tags=tags)

            for index_index, index_copy in index['content']['replicated_copies_tracker'].items():
                index_tags = tags + [ 'index_copy:{0}'.format(index_index) ]
                actual_copies = int(index_copy['actual_copies_per_slot'])
                expected_copies = int(index_copy['expected_total_per_slot'])
                self.gauge('splunk.indexes.replication.actual_copies', actual_copies, tags=index_tags)
                self.gauge('splunk.indexes.replication.expected_copies', expected_copies, tags=index_tags)

                if actual_copies != expected_copies:
                    self.service_check(self.INDEX_REPL_HEALTH_CHECK_NAME, AgentCheck.CRITICAL,
                        message='Index {0} copy {1} is not correctly replicated.'.format(name, index_copy),
                        tags = [
                            'index_name:{0}'.format(name),
                            'index_copy:{0}'.format(index_index)
                        ])
                else:
                    self.service_check(self.INDEX_REPL_HEALTH_CHECK_NAME, AgentCheck.OK,
                        tags = [
                            'index_name:{0}'.format(name),
                            'index_copy:{0}'.format(index_index)
                        ])

            for index_index, index_copy in index['content']['searchable_copies_tracker'].items():
                index_tags = tags + [ 'copy_index:{0}'.format(index_index) ]
                actual_copies = int(index_copy['actual_copies_per_slot'])
                expected_copies = int(index_copy['expected_total_per_slot'])
                self.gauge('splunk.indexes.search.actual_copies', actual_copies, tags=index_tags)
                self.gauge('splunk.indexes.search.expected_copies', expected_copies, tags=index_tags)

                if actual_copies != expected_copies:
                    self.service_check(self.INDEX_SEARCH_HEALTH_CHECK_NAME, AgentCheck.CRITICAL,
                        message='Index {0} copy {1} is not fully serachable.'.format(name, index_copy),
                        tags = [
                            'index_name:{0}'.format(name),
                            'index_copy:{0}'.format(index_index)
                        ])
                else:
                    self.service_check(self.INDEX_SEARCH_HEALTH_CHECK_NAME, AgentCheck.OK,
                        tags = [
                            'index_name:{0}'.format(name),
                            'index_copy:{0}'.format(index_index)
                        ])

    def get_json(self, url, path, instance_tags, username, password, timeout):
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
            self.histogram('splunk.stats_fetch_duration_seconds', int(elapsed_time), tags = [ 'path:{0}'.format(path) ])
        except requests.exceptions.Timeout:
            # If there's a timeout
            self.service_check(self.CONNECT_CHECK_NAME, AgentCheck.CRITICAL,
                message='Timed out after {0} seconds.'.format(timeout),
                tags = instance_tags)
            raise Exception("Timeout when hitting URL")

        except requests.exceptions.HTTPError:
            self.service_check(self.CONNECT_CHECK_NAME, AgentCheck.CRITICAL,
                message='Returned a status of {0}'.format(r.status_code),
                tags = instance_tags)
            raise Exception("Got {0} when hitting URL".format(r.status_code))

        else:
            self.service_check(self.CONNECT_CHECK_NAME, AgentCheck.OK,
                tags = instance_tags
            )
        return r.json()
