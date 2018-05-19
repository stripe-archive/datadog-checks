# stdlib
from collections import defaultdict
from urlparse import urljoin
from xml.dom import minidom

# Add lib/ to the import path:
import sys
import os
agent_lib_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), '../lib')
sys.path.insert(1, agent_lib_dir)

# 3rd party
import requests
from requests.auth import HTTPBasicAuth

# project
from checks import AgentCheck
from stats_helpers import Timing

class Splunk(AgentCheck):

    DEFAULT_TIMEOUT = 5
    CONNECT_CHECK_NAME = 'splunk.can_connect'
    INDEX_HEALTH_CHECK_NAME = 'splunk.index.is_healthy'
    INDEX_REPL_HEALTH_CHECK_NAME = 'splunk.index_copy.is_replicated'
    INDEX_SEARCH_HEALTH_CHECK_NAME = 'splunk.index_copy.is_searchable'
    PEER_HEALTH_CHECK_NAME = 'splunk.peer.is_healthy'
    REQUEST_TIMING_METRIC_NAME = 'splunk.stats_fetch_duration_seconds'

    FIXUP_LEVELS = ['streaming', 'data_safety', 'generation', 'replication_factor', 'search_factor', 'checksum_sync']

    def check(self, instance):
        if 'url' not in instance:
            raise Exception('Splunk instance missing "url" value.')

        # Load values from the instance config
        url = instance['url']
        instance_tags = instance.get('tags', []) + ['instance:{0}'.format(url)]
        default_timeout = self.init_config.get('default_timeout', self.DEFAULT_TIMEOUT)
        username = instance.get('username')
        password = instance.get('password')
        timeout = float(instance.get('timeout', default_timeout))

        # Grab a session key for authentication
        try:
            r = requests.post(urljoin(url, '/services/auth/login'), verify=False, timeout=timeout, data={'username':username, 'password':password})
            sessionkey = minidom.parseString(r.text).getElementsByTagName('sessionKey')[0].childNodes[0].nodeValue
        except requests.exceptions.Timeout:
            # If there's a timeout
            self.service_check(self.CONNECT_CHECK_NAME, AgentCheck.CRITICAL,
                message='Timed out after {0} seconds.'.format(timeout),
                tags = instance_tags)
            return

        except requests.exceptions.HTTPError:
            self.service_check(self.CONNECT_CHECK_NAME, AgentCheck.CRITICAL,
                message='Returned a status of {0}'.format(r.status_code),
                tags = instance_tags)
            return

        except Exception as e:
            self.service_check(self.CONNECT_CHECK_NAME, AgentCheck.CRITICAL,
                message='Got exception {0}: {1}'.format(e.__class__.__name__, e),
                tags = instance_tags)
            return
        else:
            self.service_check(self.CONNECT_CHECK_NAME, AgentCheck.OK,
                tags = instance_tags
            )

        if self.is_license_master(instance_tags, url, sessionkey, timeout):
            self.do_license_metrics(instance_tags, url, sessionkey, timeout)

        if self.is_master(instance_tags, url, sessionkey, timeout):
            self.do_index_metrics(instance_tags, url, sessionkey, timeout)
            self.do_peer_metrics(instance_tags, url, sessionkey, timeout)
            self.do_fixup_metrics(instance_tags, url, sessionkey, timeout)

        if self.is_captain(instance_tags, url, sessionkey, timeout):
            self.do_search_metrics(instance_tags, url, sessionkey, timeout)
            self.do_shmember_metrics(instance_tags, url, sessionkey, timeout)

        if self.is_forwarder(instance_tags, url, sessionkey, timeout):
            self.do_forwarder_metrics(instance_tags, url, sessionkey, timeout)

    def is_license_master(self, instance_tags, url, sessionkey, timeout):
        try:
            users = self.get_json(url, '/services/licenser/slaves', instance_tags, sessionkey, timeout, emit_count=False, emit_timers=False)
            # If we don't have > 1 license user we're not a real LM
            return len(users['entry']) > 1
        except:
            return False

    def is_master(self, instance_tags, url, sessionkey, timeout):
        try:
            self.get_json(url, '/services/cluster/master/info', instance_tags, sessionkey, timeout, emit_count=False, emit_timers=False)
        except:
            return False
        else:
            return True

    def is_captain(self, instance_tags, url, sessionkey, timeout):
        try:
            self.get_json(url, '/services/shcluster/captain/jobs', instance_tags, sessionkey, timeout, emit_count=False, emit_timers=False)
        except:
            return False
        else:
            return True

    def is_forwarder(self, instance_tags, url, sessionkey, timeout):
        try:
            self.get_json(url, '/services/data/inputs/all', instance_tags, sessionkey, timeout, emit_count=False, emit_timers=False)
        except Exception as inst:
            return False
        else:
            return True

    def do_forwarder_metrics(self, instance_tags, url, sessionkey, timeout):
        response = self.get_json(url, '/services/admin/inputstatus/TailingProcessor:FileStatus', instance_tags, sessionkey, timeout, emit_count=True, emit_timers=False)

        count = 0
        for fname in response['entry'][0]['content']['inputs']:
            input_status = response['entry'][0]['content']['inputs'][fname]
            # Not every input is actually followed. Those that are have a few
            # keys. We'll use percent as our signal.
            if 'percent' in input_status:
                count += 1
                status_percent = input_status['percent']
                if status_percent != 100:
                    # To keep cardinality down, we're only going to emit only metrics
                    # for "incomplete" files.
                    self.count('splunk.forwarder.incomplete_files_total', 1, tags=instance_tags + [
                        'filename:{0}'.format(fname)
                    ])

        self.gauge('splunk.forwarder.files_read_count', count, tags=instance_tags)

    def do_shmember_metrics(self, instance_tags, url, sessionkey, timeout):
        response = self.get_json(url, '/services/shcluster/captain/members', instance_tags, sessionkey, timeout, params={'count': -1})

        members = defaultdict(lambda: defaultdict(lambda: 0))

        captains = defaultdict(lambda: 0)
        for entry in response['entry']:
            members[entry['content']['site']][entry['content']['status']] += 1

            # Count the # of captains so we can detect splitbrains
            if entry['content']['is_captain']:
                captains[entry['content']['site']] += 1

        for site, count in captains.items():
            self.gauge('splunk.search_cluster.captains', count, tags=instance_tags + [
                'site:{0}'.format(site)
            ])

        for member_site in members.keys():
            for status, count in members[member_site].items():
                self.gauge('splunk.search_cluster.member_statuses', count, tags=instance_tags + [
                    'site:{0}'.format(member_site),
                    'status:{0}'.format(status)
                ])

    def do_search_metrics(self, instance_tags, url, sessionkey, timeout):
        response = self.get_json(url, '/services/search/jobs', instance_tags, sessionkey, timeout, params={'summarize': True, 'search': 'isDone=false'})

        searches = defaultdict(lambda: defaultdict(lambda: 0))

        for entry in response['entry']:
            searches[entry['content']['isSavedSearch']][entry['author']] += 1

        for search_saved in searches.keys():
            for search_owner in searches[search_saved].keys():
                self.gauge('splunk.searches.in_progress', searches[search_saved][search_owner], tags=instance_tags + [
                    'is_saved:{0}'.format(search_saved),
                    'search_owner:{0}'.format(search_owner)
                ])

    def do_fixup_metrics(self, instance_tags, url, sessionkey, timeout):
        for level in self.FIXUP_LEVELS:
            response = self.get_json(url, '/services/cluster/master/fixup', instance_tags, sessionkey, timeout, params={'level': level, 'count': -1})

            # Accumulate a count by index so we can emit a gauge.
            index_tasks = defaultdict(lambda: 0)
            for entry in response['entry']:
                index = entry['content']['index']
                index_tasks[index] += 1

            for index, count in index_tasks.items():
                self.gauge('splunk.fixups.jobs_present', count, tags=instance_tags + [
                    'index_name:{0}'.format(index),
                    'fixup_level:{0}'.format(level)
                ])

    def do_license_metrics(self, instance_tags, url, sessionkey, timeout):
        response = self.get_json(url, '/services/licenser/pools', instance_tags, sessionkey, timeout, params={ 'count': -1})

        for entry in response['entry']:
            license = entry['name']
            effective_quota = entry['content']['effective_quota']
            used_bytes = entry['content']['used_bytes']
            used_percent = 0
            if effective_quota > 0:
                used_percent = used_bytes / float(effective_quota)

            self.gauge('splunk.license.quota_bytes', effective_quota, tags=instance_tags + [
                'license_name:{0}'.format(license),
            ])
            self.gauge('splunk.license.used_bytes', used_bytes, tags=instance_tags + [
                'license_name:{0}'.format(license),
            ])
            self.gauge('splunk.license.used_percent', used_percent, tags=instance_tags + [
                'license_name:{0}'.format(license),
            ])

    def do_peer_metrics(self, instance_tags, url, sessionkey, timeout):
        response = self.get_json(url, '/services/cluster/master/peers', instance_tags, sessionkey, timeout, params={'count': -1})
        peer_statuses = defaultdict(lambda: defaultdict(lambda: 0))
        for peer in response['entry']:
            host = peer['content']['label']
            site = peer['content']['site']

            tags = instance_tags + [
                'peer_name:{0}'.format(host),
                'site:{0}'.format(site),
            ]

            peer_statuses[site][peer['content']['status']] += 1

            searchable = peer['content']['is_searchable']
            if not searchable:
                self.service_check(self.PEER_HEALTH_CHECK_NAME, AgentCheck.CRITICAL,
                    message='Host {0} is not searchable.'.format(host),
                    tags = tags)
            else:
                self.service_check(self.PEER_HEALTH_CHECK_NAME, AgentCheck.OK,
                    tags = tags)

            self.gauge('splunk.peers.delayed_buckets_to_discard', len(peer['content']['delayed_buckets_to_discard']), tags=tags)
            self.gauge('splunk.peers.primary_count', peer['content']['primary_count'], tags=tags)
            self.gauge('splunk.peers.primary_count_remote', peer['content']['primary_count_remote'], tags=tags)
            self.gauge('splunk.peers.replication_count', peer['content']['replication_count'], tags=tags)

            if peer['content']['bucket_count_by_index'] is not None:
                for bucket, count in peer['content']['bucket_count_by_index'].items():
                    self.gauge('splunk.peers.bucket_count', count, tags=tags + ['index_name:{0}'.format(bucket)])

            if peer['content']['status_counter'] is not None:
                for status, count in peer['content']['status_counter'].items():
                    self.gauge('splunk.peers.bucket_status', count, tags=tags + ['bucket_status:{0}'.format(status)])

        # This is a synthetic metric to make it easier to count the number of peers
        # in whatever status.
        for site in peer_statuses.keys():
            for status, count in peer_statuses[site].items():
                self.gauge('splunk.peers.peers_present', count, tags=tags + [
                    'status:{0}'.format(status),
                    'site:{0}'.format(site)
                ])

    def do_index_metrics(self, instance_tags, url, sessionkey, timeout):
        response = self.get_json(url, '/services/cluster/master/indexes', instance_tags, sessionkey, timeout, params={'count': -1})
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
                index_tags = tags + [ 'index_copy:{0}'.format(index_index) ]
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

    def get_json(self, url, path, instance_tags, sessionkey, timeout, emit_count=True, emit_timers=True, params={}):
        request_params = {
            'output_mode': 'json'
        }
        request_params.update(params)

        if emit_timers:
            timing_mode = Timing.WITH_TIMING
        elif emit_count:
            timing_mode = Timing.WITH_COUNT
        else:
            timing_mode = None

        try:
            with Timing(self, self.REQUEST_TIMING_METRIC_NAME, tags={'path': path}, emit=timing_mode):
                r = requests.get(
                    urljoin(url, path),
                    verify=False,
                    headers={'Authorization': "Splunk {0}".format(sessionkey)},
                    timeout=timeout,
                    params=request_params
                )
                r.raise_for_status()

        except requests.exceptions.Timeout:
            raise Exception("Timeout when hitting URL")
        except requests.exceptions.HTTPError:
            raise Exception("Got {0} when hitting URL".format(r.status_code))

        return r.json()
