
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
        check = load_check('unbound', conf, {})

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

        self.run_check(conf, mocks={'get_stats': get_stats})

        self.assertMetric("unbound.thread0.num.queries", value=884)
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
