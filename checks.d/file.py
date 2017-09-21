import errno
import glob
import os
import time

from checks import AgentCheck

class FileCheck(AgentCheck):

    MAX_FILES_TO_STAT = 1024
    STATUS_ABSENT = 'absent'
    STATUS_PRESENT = 'present'

    def __init__(self, name, init_config, agentConfig, instances=None):
        AgentCheck.__init__(self, name, init_config, agentConfig, instances)
        self._last_state_by_path = {}

    def has_different_status(self, path, current):
        last_state = self._last_state_by_path.get(path, None)
        self._last_state_by_path[path] = current
        return (last_state is not None and last_state != current)

    def stat_file(self, path):
        try:
            files = glob.glob(path)
            if len(files) > 0:
                if len(files) > self.MAX_FILES_TO_STAT:
                    raise Exception("File check sanity check prevents more than %d files" % (self.MAX_FILES_TO_STAT))
                # Stat each file and return the oldest file, as it's ctime will be the first in our ascending list.
                sorted_files = sorted(files, cmp=lambda x, y: cmp(os.stat(x).st_ctime, os.stat(y).st_ctime))
                statinfo = os.stat(sorted_files[0])
                return self.STATUS_PRESENT, statinfo
            else:
                return self.STATUS_ABSENT, []
        except OSError, e:
            if e.errno == errno.ENOENT:
                return self.STATUS_ABSENT, []
            else:
                raise

    # Note that this check takes a "second" (lol self) argument that allows
    # us to override the age of the file. Since the age of the file is based on
    # the ctime, we can't modify it to rig up a test. Supply this value will
    # ignore the file's age and use the provided value instead. Yay testing!
    def check(self, instance, file_age=-1):
        """
        Stats a file and emits service_checks and metrics on file creation/age.
        """
        if 'path' not in instance:
            raise Exception("Missing 'path' in file check config")
        if 'expect' not in instance:
            raise Exception("Missing 'expect' in file check config")

        path = instance['path']
        expect = instance['expect']
        min_age = instance.get('present_minimum_age_seconds', 0)

        status, statinfo = self.stat_file(path)
        tags = [
            'expected_status:' + expect,
            'path:' + path
        ]

        timestamp = time.time()
        if status == self.STATUS_PRESENT:
            if file_age == -1:
                # We only want to change this value of we have been given a
                # value different than the default. See the note atop this
                # function.
                file_age = timestamp - statinfo.st_ctime

        # Emit a service check:
        msg = "File %s is %s" % (path, expect)
        check_status = AgentCheck.OK
        if status != expect:
            if (status == self.STATUS_PRESENT and file_age > min_age) or expect == self.STATUS_PRESENT:
                # We only want to emit this if the file is "old enough". Since
                # this check_status is used to signal the event below, we won't
                # get an event either.
                check_status = AgentCheck.CRITICAL
                msg = "File %s that was expected to be %s is %s instead" % (path, expect, status)
        self.service_check('file.existence', check_status, message=msg, tags=tags)

        # Emit an event if the previous state is known & it's different:
        if self.has_different_status(path, status):
            alert_type = 'success'
            if check_status != AgentCheck.OK:
                alert_type = 'error'

            title = 'File %s is now %s' % (path, status)
            self.event({
                'timestamp': timestamp,
                'event_type': 'file.presence_change',
                'msg_title': title,
                'alert_type': alert_type,
                'tags': tags,
                'aggregation_key': path,
            })

        # Emit age metrics (of dubious utility):
        self.gauge('file.age_seconds', file_age, tags=tags)
