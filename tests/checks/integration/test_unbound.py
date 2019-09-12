
# project
from os import path

from checks import AgentCheck
from tests.checks.common import AgentCheckTest, load_check
import mock

class TestFileUnit(AgentCheckTest):
    CHECK_NAME = 'unbound'

    FIXTURE_PATH = path.join(
        path.dirname(path.realpath(__file__)),
        'fixtures',
        'unbound'
    )

    def test_check_exists(self):
        conf = {}
        load_check('unbound', conf, {})

    def test_output(self):
        conf = {
            'init_config': {},
            'instances': [
                {}
            ]
        }
        filename = path.join(self.FIXTURE_PATH, 'stats.txt')

        def get_stats(instance):
            with open(filename, "r") as fh:
                return fh.read()

        # Run twice to establish rates.
        self.run_check_twice(conf, mocks={'get_stats': get_stats})

        self.assertMetric("unbound.num.queries", value=0, tags=['thread:0'])
        self.assertMetric("unbound.total.requestlist.max", value=1212)
        self.assertMetric("unbound.requestlist.max", value=1079, tags=['thread:2'])
        self.assertMetric("unbound.num.query.flags", value=0, tags=['flags:RD'])
        self.assertMetric("unbound.num.query.edns", value=0, tags=['edns:present'])
        self.assertMetric("unbound.num.answer.rcode", value=0, tags=['rcode:NOERROR'])
        self.assertMetric("unbound.num.query.class", value=0, tags=['class:IN'])
        self.assertMetric("unbound.num.query.opcode", value=0, tags=['opcode:QUERY'])
        self.assertMetric("unbound.num.query.type", value=0, tags=['type:A'])
        self.assertMetric("unbound.num.query.type", value=0, tags=['type:AAAA'])
        self.assertMetric("unbound.num.zero_ttl", value=0, tags=['thread:0'])

        self.assertServiceCheck('unbound', AgentCheck.OK)

    def test_override_rate_as_counter(self):
        conf = {
            'init_config': {
                'override_rate_as_counter_metrics': ['num.queries']
            },
            'instances': [
                {}
            ]
        }

        filename = path.join(self.FIXTURE_PATH, 'stats.txt')

        def get_stats(instance):
            with open(filename, "r") as fh:
                return fh.read()

        # Run twice to establish rates.
        self.run_check_twice(conf, mocks={'get_stats': get_stats})

        # Now reports as individual values instead of caclulating the rate
        self.assertMetric("unbound.num.queries", value=884, tags=['thread:0'])
        self.assertMetric("unbound.total.num.queries", value=59379)

        # Make sure metrics that are not overriden are still reported as a rate
        # (in this case 0 since the data doesn't change between runs
        self.assertMetric("unbound.num.query.type", value=0, tags=['type:A'])

    def test_exclude_metrics(self):
        conf = {
            'init_config': {
                'exclude_metrics': ['num.queries']
            },
            'instances': [
                {}
            ]
        }

        filename = path.join(self.FIXTURE_PATH, 'stats.txt')

        def get_stats(instance):
            with open(filename, "r") as fh:
                return fh.read()

        # Run twice to establish rates.
        self.run_check_twice(conf, mocks={'get_stats': get_stats})

        self.assertMetric("unbound.num.queries", count=0)
        self.assertMetric("unbound.total.num.queries", count=0)

        # Make sure metrics that are not excluded are still reported
        self.assertMetric("unbound.num.query.type", at_least=1)

    def test_output_failure(self):
        conf = {
            'init_config': {},
            'instances': [
                {}
            ]
        }
        def get_stats(instance):
            return "garbageoutput"

        self.run_check(conf, mocks={'get_stats': get_stats})

        self.assertServiceCheck('unbound', AgentCheck.CRITICAL)

    def check_sudo(self, sudo_value):
        conf = {
            'init_config': {"sudo": sudo_value},
            'instances': [
                {}
            ]
        }

        check = load_check('unbound', conf, {})
        cmd = check.get_cmd()
        self.assertEqual(cmd.startswith("sudo "), sudo_value)

    def test_sudo(self):
        self.check_sudo(True)
        self.check_sudo(False)

    def test_unbound_config_path(self):
        conf = {
            'init_config': {},
            'instances': [
                {
                    'unbound_config_path': 'unbound1.conf'
                },
                {
                    'unbound_config_path': 'unbound2.conf'
                }
            ]
        }

        with mock.patch('subprocess.check_output', return_value="") as check_output_mock:
            self.run_check(conf)

            self.assertEqual(check_output_mock.call_count, 2)
            check_output_mock.assert_any_call("unbound-control -c unbound1.conf stats", stderr=mock.ANY, shell=mock.ANY)
            check_output_mock.assert_any_call("unbound-control -c unbound2.conf stats", stderr=mock.ANY, shell=mock.ANY)

    def test_additional_tags(self):
        conf = {
            'init_config': {},
            'instances': [
                {
                    'extra_tags': ['tag_name1:tag_value1', 'tag_name2:tag_value2']
                }
            ]
        }

        filename = path.join(self.FIXTURE_PATH, 'stats.txt')

        def get_stats(instance):
            with open(filename, "r") as fh:
                return fh.read()

        # Run twice to establish rates.
        self.run_check(conf, mocks={'get_stats': get_stats})

        self.assertMetric("unbound.recursion.time.avg", value=122.983901, tags=['thread:0', 'tag_name1:tag_value1', 'tag_name2:tag_value2'])
