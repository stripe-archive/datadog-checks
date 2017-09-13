from os import path, getuid
#from tempfile import mkstemp, gettempdir

# project
from checks import AgentCheck
from tests.checks.common import AgentCheckTest, load_check
from unittest import skipIf
from nose.tools import *

class TestFileUnit(AgentCheckTest):
    CHECK_NAME = 'system.oom'
    FIXTURE_PATH = path.join(
        path.dirname(path.realpath(__file__)),
        'fixtures',
        'oom'
    )

    def check_and_assert(self, filename, matches,
        kernel_line_regex='^(?P<timestamp>.+?) (?P<host>\S+) kernel: \[\s*(?P<uptime>\d+(?:\.\d+)?)\] (?P<message>.*)$',
        kill_message_regex='^Out of memory: Kill process (?P<pid>\d+) \((?P<pname>.*?)\) score (?P<score>.*?) or sacrifice child'
    ):
        if filename[0] != '/':
            filename = path.join(self.FIXTURE_PATH, filename)

        conf = {
            'init_config': {},
            'instances': [{
                'logfile': filename,
                'kernel_line_regex': kernel_line_regex,
                'kill_message_regex': kill_message_regex
            }]
        }

        check = load_check('oom', conf, {})
        check.check(conf['instances'][0])

        service_checks = check.get_service_checks()

        self.assertEqual(
            len(service_checks),
            len(matches),
            "Got %s service checks but specified %s matches" % (len(service_checks), len(matches))
        )

        for idx, obj in enumerate(service_checks):
            match = matches[idx]

            self.assertEqual(
                obj.get('check'),
                self.CHECK_NAME,
                "(%s) Service check name should be %s" % (idx, self.CHECK_NAME)
            )

            if 'status' in match:
                self.assertEqual(
                    obj.get('status'),
                    match.get('status'),
                    "(%s) Status should be %s" % (idx, match.get('status'))
                )

            if 'message' in match:
                if match.get('message') is None:
                    self.assertEqual(
                        obj.get('message'),
                        None,
                        "(%s) Service check should have no message" % idx
                    )
                else:
                    self.assertRegexpMatches(
                        obj.get('message'),
                        match.get('message'),
                        "(%s) Message should match %s" % (idx, match.get('message'))
                    )

    def test_no_file(self):
        self.check_and_assert('kern.nonexistent.log', [
            { 'status': AgentCheck.WARNING, 'message': 'No such file or directory' }
        ])

    @skipIf(getuid() == 0, "Can't run access test as root")
    def test_no_access(self):
        if getuid() > 0:
            # previously used a root-owned file, but docker build as a user can't
            # build an image then. instead, chose a file a regular user shouldn't
            # have access to but should exist. we can cheat this way with a little
            # more confidence since we're relying on docker anyway for a reliable
            # test environment

            self.check_and_assert('/etc/shadow', [
                { 'status': AgentCheck.CRITICAL, 'message': 'Permission denied' }
            ])
        else:
            print "Skipping"

    def test_no_kills(self):
        self.check_and_assert('kern.clean.log', [
            { 'status': AgentCheck.OK, 'message': None }
        ])

    def test_kills(self):
        self.check_and_assert('kern.killed.log', [
            { 'status': AgentCheck.CRITICAL, 'message': 'Process OOM killed' }
        ])

    def test_kills_latest(self):
        self.check_and_assert('kern.killed.log', [
            { 'status': AgentCheck.CRITICAL, 'message': "Process OOM killed.*'pid': '2093'" }
        ])

    def test_kills_reboot(self):
        self.check_and_assert('kern.rebooted.log', [
            { 'status': AgentCheck.OK, 'message': None }
        ])

    def test_no_kills_no_uptime(self):
        self.check_and_assert('kern.clean.log', [
            { 'status': AgentCheck.OK, 'message': None }
        ], kernel_line_regex='^(?P<timestamp>.+?) (?P<host>\S+) kernel: \[\s*(?P<nope>\d+(?:\.\d+)?)\] (?P<message>.*)$')

    def test_kills_no_uptime(self):
        self.check_and_assert('kern.killed.log', [
            { 'status': AgentCheck.CRITICAL, 'message': 'Process OOM killed' }
        ], kernel_line_regex='^(?P<timestamp>.+?) (?P<host>\S+) kernel: \[\s*(?P<nope>\d+(?:\.\d+)?)\] (?P<message>.*)$')

    def test_kills_reboot_no_uptime(self):
        self.check_and_assert('kern.rebooted.log', [
            { 'status': AgentCheck.CRITICAL, 'message': 'Process OOM killed' }
        ], kernel_line_regex='^(?P<timestamp>.+?) (?P<host>\S+) kernel: \[\s*(?P<nope>\d+(?:\.\d+)?)\] (?P<message>.*)$')
