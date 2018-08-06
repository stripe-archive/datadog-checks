# Add lib/ to the import path:
import sys
import os
agent_lib_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), '../lib')
sys.path.insert(1, agent_lib_dir)

import re

from checks import AgentCheck
from collections import defaultdict
from helpers import reverse_readline, parse_fix_timestamp
from datetime import datetime, timedelta

def regex_matches(line, regex):
    if not line or not regex:
        return

    result = regex.match(line)

    if not result:
        return

    return result.groupdict()

class Segfault(AgentCheck):
    def tags(self, *tags):
        return self.instance_tags + list(tags)

    def check(self, instance):
        self.instance_tags = instance.get('tags', [])
        self.mock_now = instance.get('mock_now', None)

        try:
            # the regex to parse the kernel log line with
            kernel_line_regex = re.compile(instance['kernel_line_regex'])

            # the regex to extract the process name from the message with
            process_name_regex = None
            if 'process_name_regex' in instance and instance['process_name_regex']:
                process_name_regex = re.compile(instance['process_name_regex'])

            # the format to parse the timestamp from
            # %b %d %H:%M:%S
            timestamp_format = instance['timestamp_format']

            # the number of seconds into the past to accumulate the count for
            time_window_seconds = instance['time_window_seconds']

            # the logfile to read from
            logfile_path = instance['logfile']
        except KeyError, e:
            self.increment('system.segfault.errors', tags=self.tags('type:config'))
            print >> sys.stderr, "Instance config: Key `%s` is required" % e.args[0]
            return
        except TypeError, e:
            self.increment('system.segfault.errors', tags=self.tags('type:config'))
            print >> sys.stderr, "Error loading config: %s" % e
            return

        try:
            fh = open(logfile_path, 'rt')
        except IOError, err:
            self.increment('system.segfault.errors', tags=self.tags('type:io'))
            return

        counts = defaultdict(lambda: 0)
        dt_now = self.mock_now or datetime.now()
        dt_oldest = dt_now - timedelta(seconds=time_window_seconds)

        with fh:
            for line in reverse_readline(fh):
                kern_results = regex_matches(line, kernel_line_regex)

                # no match = skip this line
                if not kern_results:
                    continue

                message = kern_results.get('message', None)
                timestamp = kern_results.get('timestamp', None)

                try:
                    dt_timestamp = parse_fix_timestamp(timestamp, timestamp_format, dt_now)
                except (ValueError, TypeError):
                    dt_timestamp = None

                if message == None or dt_timestamp == None:
                    self.increment('system.segfault.errors', tags=self.tags('type:parse'))
                    continue

                if dt_timestamp < dt_oldest:
                    # we only look back X seconds; we can end early if we hit a timestamp earlier than that
                    break

                # process name regex is an extra regex to extract the process name
                # from the 'message' capturing group. behaves the same as kernel_line_regex
                # in that a failed match = skip this line. if unspecified, do not extract
                # a process name
                process_name = None
                if process_name_regex:
                    pname_results = regex_matches(message, process_name_regex)
                    if not pname_results:
                        continue

                    process_name = pname_results.get('process', None)

                counts[process_name] += 1

        for pname, num_segfaults in counts.iteritems():
            tags = ['time_window:%s' % time_window_seconds]
            # sometimes the process name isn't present / can't be extracted
            # we might want to put the process name in the tag config, so don't
            # add on an extra 'process' tag that's empty in addition
            if pname:
                tags.append('process:%s' % pname)

            metric_tags = self.tags(*tags)
            self.gauge('system.segfault.count', num_segfaults, tags=metric_tags)
