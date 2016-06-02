# Add lib/ to the import path:
import sys
import os
agent_lib_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), '../../lib')
sys.path.insert(1, agent_lib_dir)

# stdlib
import re

# test
import unittest

# unit under test
import storm_utils

class TestStormUtils(unittest.TestCase):
    def test_timespec(self):
        self.assertEqual(330, storm_utils.translate_timespec('5m 30s'))
        self.assertEqual(1728331, storm_utils.translate_timespec('20d 5m 31s'))
        self.assertEqual(12114041, storm_utils.translate_timespec('20w 5h 41s'))
        self.assertEqual(0, storm_utils.translate_timespec(''))
        with self.assertRaises(ValueError) as context:
            storm_utils.translate_timespec('20--')
        with self.assertRaises(ValueError) as context:
            storm_utils.translate_timespec('20Y 5m 3s')


    def test_collect_topologies(self):
        topologies_re = re.compile('^(sometopo)_.*$')

        topologies = {"topologies":[
            {"id":"sometopo_8VmCP0bp6W21qr-2-1464115959","encodedId":"sometopo_8VmCP0bp6W21qr-2-1464115959","name":"sometopo_8VmCP0bp6W21qr","status":"ACTIVE","uptime":"1d 1h 38m 13s","tasksTotal":11366,"workersTotal":7,"executorsTotal":11366},
            {"id":"sometopo_987IENien9887a-3-1464117779","encodedId":"sometopo_987IENien9887a-3-1464117779","name":"sometopo_987IENien9887a","status":"ACTIVE","uptime":"30s","tasksTotal":11366,"workersTotal":7,"executorsTotal":11366},
            {"id":"sometopo_987IMDEAD6798a-3-1464117779","encodedId":"sometopo_987IMDEAD6798a-3-1464117779","name":"sometopo_987IMDEAD6798a","status":"KILLED","uptime":"10s","tasksTotal":11366,"workersTotal":7,"executorsTotal":11366},
            {"id":"some-other-topo_8VmCP0bp6W21qr-2-1464115959","encodedId":"some-other-topo_8VmCP0bp6W21qr-2-1464115959","name":"some-other-topo_8VmCP0bp6W21qr","status":"ACTIVE","uptime":"2s","tasksTotal":5972,"workersTotal":7,"executorsTotal":5972}
        ]}
        collected_topos = storm_utils.collect_topologies(topologies_re, topologies['topologies'])

        # the interesting one:
        topo = collected_topos.get('sometopo')
        self.assertEqual(topo['id'], 'sometopo_987IENien9887a-3-1464117779')
