# Add lib/ to the import path:
import sys
import os
agent_lib_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), '../lib')
sys.path.insert(1, agent_lib_dir)

# stdlib
from collections import namedtuple
import urlparse
import json
import time
import sys

# 3p
import requests

# project
from checks import AgentCheck
from util import headers
import re
import storm_utils


StormConfig = namedtuple(
    'StormConfig',
    [
        'metric_prefix',
        'tags',
        'task_tags',
        'timeout',
        'executor_details_whitelist',
        'topology_timeout',
        'url',
        'topologies',
        'cache_file',
        'cache_staleness',
        'task_id_cleaner_regex',
    ]
)

class StormRESTCheck(AgentCheck):
    class ConnectionFailure(StandardError):
        def __init__(self, url, timeout):
            self.url = url
            self.timeout = timeout

    DEFAULT_TIMEOUT = 5 # seconds
    DEFAULT_STALENESS=240 # seconds

    def instance_config(self, instance):
        url = instance.get('url')
        if url is None:
            raise Exception("An url must be specified in the instance")

        cache_file = instance.get('cache_file')
        if cache_file is None:
            raise Exception("You must specify a cache file (querying the storm API synchronously is too slow).")

        timeout = instance.get('timeout', self.DEFAULT_TIMEOUT)
        topology_timeout = instance.get('topology_timeout', timeout)
        topologies_re = re.compile(instance.get('topologies', '(.*)'))

        task_tags_from_json = {}
        tag_file = instance.get('task_tags_file', None)
        if tag_file is not None:
            with open(tag_file, 'r') as f:
                task_tags_from_json = json.load(f)
        task_tags = instance.get('task_tags', {}).copy()
        task_tags.update(task_tags_from_json)

        raw_whitelist = set(instance.get('executor_details_whitelist', []))
        executor_details_whitelist = [re.compile(regex) for regex in raw_whitelist]

        return StormConfig(
            metric_prefix=instance.get('metric_prefix', None),
            url=url,
            timeout=timeout,
            topology_timeout=topology_timeout,
            tags=instance.get('tags', []),
            executor_details_whitelist=executor_details_whitelist,
            task_tags=task_tags,
            cache_file=cache_file,
            cache_staleness=instance.get('cache_staleness', self.DEFAULT_STALENESS),
            topologies=topologies_re,
            task_id_cleaner_regex=instance.get('task_id_cleaner_regex', None),
        )

    def metric(self, config, name):
        if config.metric_prefix is not None:
            return "%s.storm.rest.%s" % (config.metric_prefix, name)
        else:
            return "storm.rest.%s" % name

    def check(self, instance):
        config = self.instance_config(instance)

        check_status = AgentCheck.OK
        check_msg = 'Everything went well'
        check_tags = [
            'url:' + config.url,
        ] + config.tags

        details = None
        with open(config.cache_file, 'r') as cache_f:
            details = json.load(cache_f)

        oldest_acceptable_cache_time = time.time() - config.cache_staleness
        if details['status'] == 'success' and details['updated'] > oldest_acceptable_cache_time:
            data = details['data']
            self.report_cluster(config, data['cluster'])
            self.report_supervisors(config, data['supervisors'])
            self.report_topologies(config, data['topologies'])
            for topology_detail in data['topology_details']:
                self.report_topology(config, topology_detail['name'], topology_detail['topology'])
                for executor_details in topology_detail['component_details']:
                    self.report_executor_details(config, executor_details)
        else:
            check_status = AgentCheck.CRITICAL
            if details['status'] != 'success':
                check_msg = "Could not connect to URL %s with timeout %d" % (details['error_url'], details['error_timeout'])
            else:
                check_msg = "Cache is too stale: %d vs. expected minimum %d" % (details['updated'], oldest_acceptable_cache_time)

        self.service_check(
            self.metric(config, 'cached_data_ok'),
            check_status,
            message=check_msg,
            tags=check_tags)

    def report_cluster(self, config, cluster):
        uptime = cluster.get('nimbusUptime', None)
        if uptime is not None:
            self.gauge(self.metric(config, 'cluster.nimbus_uptime_seconds'),
                    storm_utils.translate_timespec(uptime),
                    tags=config.tags)

        self.gauge(self.metric(config, 'cluster.slots_used_count'),
                   cluster['slotsUsed'],
                   tags=config.tags)
        self.gauge(self.metric(config, 'cluster.supervisor_count'),
                   cluster['supervisors'],
                   tags=config.tags)
        self.gauge(self.metric(config, 'cluster.slots_total_count'),
                   cluster['slotsTotal'],
                   tags=config.tags)
        self.gauge(self.metric(config, 'cluster.slots_free_count'),
                   cluster['slotsFree'],
                   tags=config.tags)
        self.gauge(self.metric(config, 'cluster.executors_total_count'),
                   cluster['executorsTotal'],
                   tags=config.tags)
        self.gauge(self.metric(config, 'cluster.tasks_total_count'),
                   cluster['tasksTotal'],
                   tags=config.tags)


    def report_supervisors(self, config, resp):
        self.gauge(self.metric(config, 'supervisors_total'),
                   len(resp.get('supervisors', [])),
                   tags=config.tags)
        for supe in resp.get('supervisors', []):
            supe_tags = [
                'storm_host:' + supe.get('host'),
            ] + config.tags
            self.gauge(self.metric(config, 'supervisor.slots_total'),
                       supe.get('slotsTotal'), tags=supe_tags)
            self.gauge(self.metric(config, 'supervisor.slots_used_total'),
                       supe.get('slotsUsed'), tags=supe_tags)
            self.gauge(self.metric(config, 'supervisor.uptime_seconds'),
                       storm_utils.translate_timespec(supe.get('uptime')), tags=supe_tags)

    def _topology_name(self, config, topology):
        """Returns the name if a config's topology regex matches, None otherwise."""
        match = config.topologies.match(topology.get('name'))
        if match:
            return match.group(1)
        else:
            return None

    def report_topologies(self, config, topologies):
        """Report metadata about topologies that match the topologies regex.
        """
        for pretty_name, topo in topologies.iteritems():
            uptime = topo.get('uptime', '0s')
            tags = config.tags + [
                'storm_topology:' + pretty_name,
            ]
            self.gauge(self.metric(config, 'topologies.uptime_seconds'),
                       storm_utils.translate_timespec(uptime), tags=tags)
            self.gauge(self.metric(config, 'topologies.tasks_total'),
                       topo['tasksTotal'], tags=tags)
            self.gauge(self.metric(config, 'topologies.workers_total'),
                       topo['workersTotal'], tags=tags)
            self.gauge(self.metric(config, 'topologies.executors_total'), topo['executorsTotal'], tags=tags)

    def task_id_tags(self, config, component_type, task_id):
        cleaner_id = task_id
        if config.task_id_cleaner_regex is not None:
            match = re.search(config.task_id_cleaner_regex, cleaner_id)
            if match is not None:
                cleaner_id = match.group(1)
        return config.task_tags.get(component_type, {}).get(cleaner_id, [])

    def report_topology(self, config, name, details):
        """
        Report statistics for a single topology's spouts and bolts.
        """
        tags = config.tags + [
            'storm_topology:' + name,
        ]
        def report_task(component_type, name, task, tags):
            self.gauge(self.metric(config, ('%s.executors_total' % component_type)),
                       task['executors'], task_tags)
            self.gauge(self.metric(config, ('%s.tasks_total' % component_type)),
                       task['tasks'], task_tags)

            self.monotonic_count(self.metric(config, ('%s.emitted_total' % component_type)),
                       task['emitted'], task_tags)
            self.monotonic_count(self.metric(config, ('%s.transferred_total' % component_type)),
                       task['transferred'], task_tags)
            self.monotonic_count(self.metric(config, ('%s.acked_total' % component_type)),
                       task['acked'], task_tags)
            self.monotonic_count(self.metric(config, ('%s.failed_total' % component_type)),
                       task['failed'], task_tags)

        ## Report spouts
        for spout in details.get('spouts'):
            name = spout['spoutId']
            task_tags = tags + self.task_id_tags(config, 'spout', name) + [
                'storm_component_type:spout',
                'storm_task_id:' + name,
            ]
            report_task('spout', name, spout, task_tags)
            self.gauge(self.metric(config, 'spout.complete_latency_us'),
                       float(spout['completeLatency']), task_tags)

        for bolt in details.get('bolts'):
            name = bolt['boltId']
            task_tags = tags + self.task_id_tags(config, 'bolt', name) + [
                'storm_component_type:bolt',
                'storm_task_id:' + name,
            ]
            report_task('bolt', name, bolt, task_tags)
            if bolt['executed'] is not None:
                executed_count = bolt['executed']
            else:
                executed_count = 0
            self.monotonic_count(self.metric(config, 'bolt.executed_total'),
                       executed_count, task_tags)
            self.gauge(self.metric(config, 'bolt.execute_latency_us'),
                       float(bolt['executeLatency']), task_tags)
            self.gauge(self.metric(config, 'bolt.process_latency_us'),
                       float(bolt['processLatency']), task_tags)
            self.gauge(self.metric(config, 'bolt.capacity_percent'),
                       float(bolt['capacity']) * 100, task_tags)

    def report_executor_details(self, config, details):
        """
        Report statistics for a single topology's task ID's executors.
        """

        topology_name = self._topology_name(config, details)
        name = details['id']
        task_type = details['componentType']
        tags = config.tags + self.task_id_tags(config, task_type, name) + [
            'storm_topology:' + topology_name,
            'storm_component_type:' + task_type,
            'storm_task_id:' + details['id'],
        ]
        self.gauge(self.metric(config, 'executor.executors_total'),
                               details['executors'], tags=tags)
        self.gauge(self.metric(config, 'executor.tasks_total'),
                               details['executors'], tags=tags)

        # Embarrassingly, executorStats are undocumented in the REST
        # API docs (so we might not be allowed to rely on them). But
        # they're the only way to get some SERIOUSLY useful metrics -
        # per-host metrics, in particular.
        for executor in details['executorStats']:
            executor_tags = tags + [
                'executor_id:' + executor['id'],
                'storm_host:' + executor['host'],
                'storm_port:' + str(executor['port']),
            ]
            self.monotonic_count(self.metric(config, 'executor.emitted_total'),
                       executor.get('emitted', 0), tags=executor_tags)
            self.monotonic_count(self.metric(config, 'executor.transferred_total'),
                       executor.get('transferred', 0), tags=executor_tags)
            self.monotonic_count(self.metric(config, 'executor.acked_total'),
                       executor.get('acked', 0), tags=executor_tags)
            self.monotonic_count(self.metric(config, 'executor.executed_total'),
                       executor.get('executed', 0), tags=executor_tags)
            self.monotonic_count(self.metric(config, 'executor.failed_total'),
                       executor.get('failed', 0), tags=executor_tags)

            self.gauge(self.metric(config, 'executor.execute_latency_us'),
                       float(executor.get('executeLatency', 0)), tags=executor_tags)
            self.gauge(self.metric(config, 'executor.process_latency_us'),
                       float(executor.get('processLatency', 0)), tags=executor_tags)

            self.gauge(self.metric(config, 'executor.capacity_percent'),
                       float(executor.get('capacity', 0)) * 100, tags=executor_tags)
            self.gauge(self.metric(config, 'executor.uptime_seconds'),
                       storm_utils.translate_timespec(executor.get('uptime', '0s')), tags=executor_tags)
