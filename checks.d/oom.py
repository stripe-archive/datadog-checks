# Add lib/ to the import path:
import sys
import os
agent_lib_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), '../lib')
sys.path.insert(1, agent_lib_dir)

import re
import errno

from checks import AgentCheck
from helpers import reverse_readline

class OOM(AgentCheck):
    def check(self, instance):
        kernlogRE = re.compile(instance.get('kernel_line_regex'))
        killedRE = re.compile(instance.get('kill_message_regex'), re.IGNORECASE)

        last = None

        try:
            fh = open(instance.get('logfile'), 'rt')
        except IOError as err:
            if err.errno == errno.ENOENT:
                level = AgentCheck.WARNING
            else:
                level = AgentCheck.CRITICAL

            self.service_check('system.oom', level, message=str(err))
        else:
            last_killed = None
            count = 0

            with fh:
                for line in reverse_readline(fh):
                    result = kernlogRE.match(line)

                    if not result:
                        continue

                    results = result.groupdict()

                    message = results['message']

                    if 'uptime' in results:
                        uptime = float(results['uptime'])

                        # only process lines since the last reboot -- we're processing backwards,
                        # so if we see an uptime larger than the last one we saw, it indicates
                        # a reboot (the current line is the lowest uptime in the current sequence)
                        #
                        # this is not entirely optimal for a filtered kernel log: it won't abort on
                        # equal timestamps, such as multiple reboot messages with timestamp 0, even
                        # though we would otherwise want to. if you filter your target log that heavily,
                        # though, it shouldn't be a problem -- and the complexity of capturing this case
                        # plus a full count of OOMs is not really worth the optimization
                        if last != None and uptime > last:
                            break

                        last = uptime

                    killed_match = killedRE.match(message)
                    if not killed_match:
                        continue

                    count += 1
                    last_killed = last_killed or killed_match

            self.gauge('system.oom.count', count)

            if last_killed == None:
                self.service_check('system.oom', AgentCheck.OK)
            else:
                self.service_check('system.oom', AgentCheck.CRITICAL,
                    message="Process OOM killed since last boot: %s" % last_killed.groupdict()
                )
