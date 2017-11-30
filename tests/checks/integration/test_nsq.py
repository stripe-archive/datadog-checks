import re
from tests.checks.common import AgentCheckTest, load_check


class TestFileUnit(AgentCheckTest):
    CHECK_NAME = 'nsq'


    def test_tags_from_topic_name(self):
        conf = {
            'init_config': {'topic_name_regex': 'service-(?P<stage>prod|canary)$'},
            'instances': [{'url': 'http://localhost:4151'}]
        }
        pattern = re.compile(conf['init_config']['topic_name_regex'])
        check = load_check('nsq', conf, {})
        
        prod_result = check.tags_from_topic_name(pattern, 'service-prod')
        self.assertEqual(prod_result, ['stage:prod'])

        canary_result = check.tags_from_topic_name(pattern, 'service-canary')
        self.assertEqual(canary_result, ['stage:canary'])

        empty_result = check.tags_from_topic_name(pattern, 'other-topic')
        self.assertEqual(empty_result, [])
