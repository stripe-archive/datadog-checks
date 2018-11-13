
# project
from os import path

from checks import AgentCheck
from tests.checks.common import AgentCheckTest, load_check

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

        def get_stats():
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
        self.assertMetric("unbound.num.zero_ttl", value=0, tags=['thread:0'])

        self.assertMetric("unbound.histogram", value=0, tags=['bucket:000000.000000.to.000000.000001'])
        self.assertMetric("unbound.histogram", value=0, tags=['bucket:008192.000000.to.016384.000000'])
        self.assertServiceCheck('unbound', AgentCheck.OK)

    def test_output_failure(self):
        conf = {
            'init_config': {},
            'instances': [
                {}
            ]
        }
        def get_stats():
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
