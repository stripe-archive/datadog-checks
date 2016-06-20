# project
from checks import AgentCheck
from tests.checks.common import AgentCheckTest, load_check

class TestFileUnit(AgentCheckTest):
    CHECK_NAME='storm_rest_api'

    def assert_tags(self, expected_tags, present_tags):
        for tag in expected_tags:
            self.assertTrue(tag in present_tags,
                            "Expected tags\n%s\n and present tags\n%s\n do not match" % (expected_tags, present_tags))

    def find_metric(self, metrics, name, tags=[]):
        tags_to_find = set(tags)
        found_metrics = (metric for metric in metrics if metric[0] == name and tags_to_find <= set(metric[3].get('tags', [])))
        return next(found_metrics)

    def test_metric_name_with_prefix(self):
        instance = {'url': 'http://localhost:8080', 'timeout': 0, 'metric_prefix': 'foo', "cache_file": "/dev/null"}
        conf = {
            'init_config': {},
            'instances': [ instance ]
        }
        self.check = load_check('storm_rest_api', conf, {})
        self.assertEqual('foo.storm.rest.baz', self.check.metric(self.check.instance_config(instance), 'baz'))

    def test_metric_name_without_prefix(self):
        instance = {'url': 'http://localhost:8080', 'timeout': 0, "cache_file": "/dev/null"}
        conf = {
            'init_config': {},
            'instances': [instance]
        }
        self.check = load_check('storm_rest_api', conf, {})
        self.assertEqual('storm.rest.baz', self.check.metric(self.check.instance_config(instance), 'baz'))

    def test_cluster(self):
        uptime = "22h 41m 49s"
        cluster = {
            "stormVersion":"0.9.3",
            "nimbusUptime": uptime,
            "supervisors":7,
            "slotsTotal":147,
            "slotsUsed":7,
            "slotsFree":140,
            "executorsTotal":11415,
            "tasksTotal":11415
        }
        instance = {'url': 'http://localhost:8080', 'timeout': 0, 'tags': ['cluster_want:form'], "cache_file": "/dev/null"}
        conf = {
            'init_config': {},
            'instances': [instance]
        }
        self.check = load_check('storm_rest_api', conf, {})
        self.check.report_cluster(self.check.instance_config(instance), cluster)
        metrics = self.check.get_metrics()

        cluster_uptime = self.find_metric(metrics, 'storm.rest.cluster.nimbus_uptime_seconds')
        self.assertEqual(81709, cluster_uptime[2])
        self.assert_tags(['cluster_want:form'], cluster_uptime[3]['tags'])

        cluster_slots_used = self.find_metric(metrics, 'storm.rest.cluster.slots_used_count')
        self.assertEqual(7, cluster_slots_used[2])
        print cluster_slots_used
        self.assert_tags(['cluster_want:form'], cluster_slots_used[3]['tags'])

        for metric_name in ['supervisor_count', 'slots_total_count', 'slots_free_count', 'executors_total_count', 'tasks_total_count']:
            metric = self.find_metric(metrics, 'storm.rest.cluster.%s' % metric_name)
            self.assert_tags(['cluster_want:form'], metric[3]['tags'])
            self.assertTrue(metric[2] > 0)


    def test_supervisors(self):
        instance = {'url': 'http://localhost:8080', 'timeout': 0, "cache_file": "/dev/null"}
        conf = {
            'init_config': {},
            'instances': [instance]
        }
        self.check = load_check('storm_rest_api', conf, {})
        supervisors = {"supervisors":[
            {"id":"cb91ebc3-8212-43d4-bad2-75da548ee00b","host":"10.100.8.142","uptime":"1d 1h 28m 37s","slotsTotal":21,"slotsUsed":0},
            {"id":"56768ca7-07e9-485d-aa0e-63d42a70fbbb","host":"10.100.40.149","uptime":"8h 54m 32s","slotsTotal":21,"slotsUsed":1},
            {"id":"f8db3c29-c65e-4004-9da5-89f449965b88","host":"10.100.29.85","uptime":"1d 1h 29m 27s","slotsTotal":21,"slotsUsed":1},
            {"id":"ddab8e08-195c-4759-87ff-bafd31306326","host":"10.100.41.184","uptime":"1d 1h 29m 34s","slotsTotal":21,"slotsUsed":1}]}

        self.check.report_supervisors(self.check.instance_config(instance), supervisors)
        metrics = self.check.get_metrics()
        self.assertEqual(1 + 4*3, len(metrics))

    def test_topologies(self):
        instance = {'url': 'http://localhost:8080', 'timeout': 0, 'topologies': '^(sometopo)_.*$', "cache_file": "/dev/null"}
        conf = {
            'init_config': {},
            'instances': [
                instance
            ],
        }
        self.check = load_check('storm_rest_api', conf, {})
        collected_topos = {
            "sometopo": {"id":"sometopo_987IMDEAD6798a-3-1464117779","encodedId":"sometopo_987IMDEAD6798a-3-1464117779","name":"sometopo_987IMDEAD6798a","status":"KILLED","uptime":"10s","tasksTotal":11366,"workersTotal":7,"executorsTotal":11366},
        }
        self.check.report_topologies(self.check.instance_config(instance), collected_topos)
        metrics = self.check.get_metrics()
        self.assertTrue(len(metrics) > 0)

        uptime_metric = self.find_metric(metrics, 'storm.rest.topologies.uptime_seconds')
        self.assertEqual(10, uptime_metric[2])
        self.assert_tags(['storm_topology:sometopo'], uptime_metric[3]['tags'])

        executors_metric = self.find_metric(metrics, 'storm.rest.topologies.executors_total')
        self.assertEqual(11366, executors_metric[2])
        self.assert_tags(['storm_topology:sometopo'], executors_metric[3]['tags'])

    def test_topology_details(self):
        topology_from_sum = {"id":"sometopo_987IENien9887a-3-1464117779","encodedId":"sometopo_987IENien9887a-3-1464117779","name":"sometopo_987IENien9887a","status":"ACTIVE","uptime":"30s","tasksTotal":11366,"workersTotal":7,"executorsTotal":11366}
        name = 'sometopo'
        topology_details = {
            "spouts": [
                {"executors": 48, "emitted": 0, "errorLapsedSecs": 13822, "completeLatency": "2.030", "transferred": 50, "acked": 40, "errorPort": 6711, "spoutId": "somespout", "tasks": 48, "errorHost": "", "lastError": "", "errorWorkerLogLink": "", "failed": 20, "encodedSpoutId": "somespout"},
                {"executors": 48, "emitted": 0, "errorLapsedSecs": 13822, "completeLatency": "2.030", "transferred": 50, "acked": 40, "errorPort": 6711, "spoutId": "detailspout", "tasks": 48, "errorHost": "", "lastError": "", "errorWorkerLogLink": "", "failed": 20, "encodedSpoutId": "detailspout"}
            ],
            "bolts": [
                {"executors": 3, "emitted": 10, "errorLapsedSecs": None, "transferred": 12, "acked": 9, "errorPort": "", "executeLatency": "2.300", "tasks": 4, "executed": 12, "processLatency": "2.501", "boltId": "somebolt", "errorHost": "", "lastError": "", "errorWorkerLogLink": "", "capacity": "0.020", "failed": 2, "encodedBoltId": "somebolt"},
                {"executors": 3, "emitted": 10, "errorLapsedSecs": None, "transferred": 12, "acked": 3, "errorPort": "", "executeLatency": "2.300", "tasks": 4, "executed": 12, "processLatency": "2.501", "boltId": "detail::bolt", "errorHost": "", "lastError": "", "errorWorkerLogLink": "", "capacity": "0.020", "failed": 2, "encodedBoltId": "detail%3A%3Abolt"}

            ]
        }
        instance = {
            'url': 'http://localhost:8080',
            'timeout': 0,
            'topologies': '^(sometopo)_.*$',
            'executor_details_whitelist': ['detailspout', 'detail::bolt'],
            'task_tags': {
                'spout': {
                    'somespout': [
                        'is_a_great_spout:true'
                    ]
                },
                'bolt': {
                    'somebolt': [
                        'is_a_great_bolt:true'
                    ]
                }
            },
            "cache_file": "/dev/null"
        }
        conf = {
            'init_config': {},
            'instances': [
                instance
            ],
        }
        self.check = load_check('storm_rest_api', conf, {})

        self.check.report_topology(self.check.instance_config(instance), name, topology_details)
        self.check.report_topology(self.check.instance_config(instance), name, topology_details)

        metrics = self.check.get_metrics()
        spout_workers_metric = self.find_metric(metrics, 'storm.rest.spout.executors_total', ['storm_task_id:somespout'])
        self.assertEqual(48, spout_workers_metric[2])
        print spout_workers_metric[3]
        self.assert_tags(['storm_topology:sometopo', 'storm_task_id:somespout', 'is_a_great_spout:true'], spout_workers_metric[3]['tags'])

        complete_latency_metric = self.find_metric(metrics, 'storm.rest.spout.complete_latency_us', ['storm_task_id:somespout'])
        self.assertEqual(2.030, complete_latency_metric[2])

        bolt_workers_metric = self.find_metric(metrics, 'storm.rest.bolt.executors_total', ['storm_task_id:somebolt'])
        self.assertEqual(3, bolt_workers_metric[2])
        self.assert_tags(['storm_topology:sometopo', 'storm_task_id:somebolt', 'is_a_great_bolt:true'], bolt_workers_metric[3]['tags'])

        bolt_executed_metric = self.find_metric(metrics, 'storm.rest.bolt.executed_total', ['storm_task_id:somebolt'])
        self.assertEqual(0, bolt_executed_metric[2])
        self.assert_tags(['storm_topology:sometopo', 'storm_task_id:somebolt', 'is_a_great_bolt:true'], bolt_workers_metric[3]['tags'])

    def test_executor_metrics_for_bolt(self):
        data = {
            "executors": 72,
            "componentErrors": [],
            "encodedId": "detail%3A%3Abold",
            "boltStats":[
                {"emitted":0,"windowPretty":"10m 0s","transferred":0,"acked":0,"executeLatency":"0.000","executed":0,"processLatency":"0.000","window":"600","failed":0}
                ,{"emitted":0,"windowPretty":"3h 0m 0s","transferred":0,"acked":0,"executeLatency":"0.000","executed":0,"processLatency":"0.000","window":"10800","failed":0}
            ],
            "topologyId": "a_topology-6-1464634734",
            "name": "a_topology_8Y1e7Vi5fIvwSp",
            "executorStats": [
                {
                    "workerLogLink": "http://10.100.14.0:8000/log?file=worker-6710.log",
                    "emitted": 0,
                    "port": 6710,
                    "transferred": 0,
                    "host": "10.100.14.0",
                    "acked": 0,
                    "uptime": "4m 0s",
                    "encodedId": "%5B10751-10751%5D",
                    "executeLatency": "0",
                    "executed": 15,
                    "processLatency": "0",
                    "capacity": "0.000",
                    "id": "[10751-10751]",
                    "failed": 0
                },
                {
                    "workerLogLink": "http://10.100.29.85:8000/log?file=worker-6711.log",
                    "emitted": 0,
                    "port": 6711,
                    "transferred": 0,
                    "host": "10.100.29.85",
                    "acked": 0,
                    "uptime": "2m 32s",
                    "encodedId": "%5B10752-10752%5D",
                    "executeLatency": "0.000",
                    "executed": 4,
                    "processLatency": "0.000",
                    "capacity": "0.000",
                    "id": "[10752-10752]",
                    "failed": 0
                }],
            "tasks": 72,
            "window": "600",
            "inputStats": [],
            "componentType": "bolt",
            "windowHint": "10m 0s",
            "encodedTopologyId": "a_topology-6-1464634734",
            "id": "detail::bolt",
            "outputStats": []
        }
        instance = {
            'url': 'http://localhost:8080',
            'timeout': 0,
            'topologies': '^(a_topology)_.*$',
            'executor_details_whitelist': ['detail::bolt'],
            'task_tags': {
                'bolt': {
                    'detail::bolt': [
                        'is_a_great_bolt:true'
                    ]
                }
            },
            "cache_file": "/dev/null"
        }
        conf = {
            'init_config': {},
            'instances': [
                instance
            ],
        }
        self.check = load_check('storm_rest_api', conf, {})
        self.check.report_executor_details(self.check.instance_config(instance), data)
        self.check.report_executor_details(self.check.instance_config(instance), data)
        metrics = self.check.get_metrics()
        executor_count = self.find_metric(metrics, 'storm.rest.executor.executors_total')
        self.assertEqual(72, executor_count[2])
        self.assert_tags(['storm_task_id:detail::bolt', 'storm_component_type:bolt', 'storm_topology:a_topology', 'is_a_great_bolt:true'], executor_count[3]['tags'])

        executed_counts_1 = self.find_metric(metrics, 'storm.rest.executor.executed_total', ['storm_host:10.100.29.85'])
        executed_counts_2 = self.find_metric(metrics, 'storm.rest.executor.executed_total', ['storm_host:10.100.14.0'])
        self.assertEqual(0, executed_counts_1[2])
        self.assertEqual(0, executed_counts_2[2])
        self.assert_tags(['storm_task_id:detail::bolt', 'storm_component_type:bolt', 'storm_topology:a_topology', 'is_a_great_bolt:true'], executed_counts_2[3]['tags'])
        uptime_1 = self.find_metric(metrics, 'storm.rest.executor.uptime_seconds', ['storm_host:10.100.29.85'])
        uptime_2 = self.find_metric(metrics, 'storm.rest.executor.uptime_seconds', ['storm_host:10.100.14.0'])
        self.assertEqual(152, uptime_1[2])
        self.assertEqual(240, uptime_2[2])



    def test_executor_metrics_for_spout(self):
        data = {
            "executors": 72,
            "componentErrors": [],
            "encodedId": "detail%3A%3Aspout",
            "spoutSummary": [{"windowPretty": "10m 0s", "window": "600", "emitted": 0, "transferred": 0, "completeLatency": "0.000", "acked": 0, "failed": 0},
                             {"windowPretty": "3h 0m 0s", "window": "10800", "emitted": 0, "transferred": 0, "completeLatency": "0.000", "acked": 0, "failed": 0},
            ],
            "topologyId": "a_topology-6-1464634734",
            "name": "a_topology_8Y1e7Vi5fIvwSp",
            "executorStats": [
                {
                    "workerLogLink": "http://10.100.14.0:8000/log?file=worker-6710.log",
                    "emitted": 0,
                    "port": 6710,
                    "transferred": 0,
                    "host": "10.100.14.0",
                    "acked": 0,
                    "uptime": "4m 0s",
                    "encodedId": "%5B10751-10751%5D",
                    "executeLatency": "0",
                    "executed": 15,
                    "processLatency": "0",
                    "capacity": "0.000",
                    "id": "[10751-10751]",
                    "failed": 0
                },
                {
                    "workerLogLink": "http://10.100.29.85:8000/log?file=worker-6711.log",
                    "emitted": 0,
                    "port": 6711,
                    "transferred": 0,
                    "host": "10.100.29.85",
                    "acked": 0,
                    "uptime": "2m 32s",
                    "encodedId": "%5B10752-10752%5D",
                    "executeLatency": "0.000",
                    "executed": 4,
                    "processLatency": "0.000",
                    "capacity": "0.000",
                    "id": "[10752-10752]",
                    "failed": 0
                }],
            "tasks": 72,
            "window": "600",
            "inputStats": [],
            "componentType": "spout",
            "windowHint": "10m 0s",
            "encodedTopologyId": "a_topology-6-1464634734",
            "id": "detail::spout",
            "outputStats": []
        }
        instance = {
            'url': 'http://localhost:8080',
            'timeout': 0,
            'topologies': '^(a_topology)_.*$',
            'executor_details_whitelist': ['detail::spout'],
            'task_tags': {
                'spout': {
                    'detail::spout': [
                        'is_a_great_spout:true'
                    ]
                }
            },
            "cache_file": "/dev/null"
        }
        conf = {
            'init_config': {},
            'instances': [
                instance
            ],
        }
        self.check = load_check('storm_rest_api', conf, {})
        self.check.report_executor_details(self.check.instance_config(instance), data)
        self.check.report_executor_details(self.check.instance_config(instance), data)
        metrics = self.check.get_metrics()
        executor_count = self.find_metric(metrics, 'storm.rest.executor.executors_total')
        self.assertEqual(72, executor_count[2])
        self.assert_tags(['storm_task_id:detail::spout', 'storm_component_type:spout', 'storm_topology:a_topology', 'is_a_great_spout:true'], executor_count[3]['tags'])

        executed_counts_1 = self.find_metric(metrics, 'storm.rest.executor.executed_total', ['storm_host:10.100.29.85'])
        executed_counts_2 = self.find_metric(metrics, 'storm.rest.executor.executed_total', ['storm_host:10.100.14.0'])
        self.assertEqual(0, executed_counts_1[2])
        self.assertEqual(0, executed_counts_2[2])
        self.assert_tags(['storm_task_id:detail::spout', 'storm_component_type:spout', 'storm_topology:a_topology', 'is_a_great_spout:true'], executed_counts_1[3]['tags'])

        uptime_1 = self.find_metric(metrics, 'storm.rest.executor.uptime_seconds', ['storm_host:10.100.29.85'])
        uptime_2 = self.find_metric(metrics, 'storm.rest.executor.uptime_seconds', ['storm_host:10.100.14.0'])
        self.assertEqual(152, uptime_1[2])
        self.assertEqual(240, uptime_2[2])
