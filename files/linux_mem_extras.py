# project
from checks import AgentCheck
from utils.platform import Platform
import utils.subprocess_output

import re
import subprocess

STATS_ABOUT_WHICH_WE_CARE = ('Slab', 'PageTables', 'SwapCached')

class MoreLinuxMemCheck(AgentCheck):

    def check(self, instance):
        if Platform.is_linux():
            tags = instance.get('tags', [])

            try:
                with open('/proc/meminfo', 'r') as mem_info:
                    lines = mem_info.readlines()

            except Exception:
                self.log.exception('Cannot get memory metrics from /proc/meminfo')
                return False

            regexp = re.compile(r'^(\w+):\s+([0-9]+)')  # We run this several times so one-time compile now
            meminfo = {}

            for line in lines:
                try:
                    match = re.search(regexp, line)
                    if match is not None:
                        meminfo[match.group(1)] = match.group(2)
                except Exception:
                    self.log.exception("Parsing error on /proc/meminfo line: %s" % line)

            for sawwc in STATS_ABOUT_WHICH_WE_CARE:
                try:
                  self.gauge('linux.memory.%s' % sawwc.lower(), int(meminfo.get(sawwc, 0)) / 1024, tags)
                except Exception:
                  self.log.exception("Cannot compute stat `linux.memory.%s' from value `%i'" % (sawwc.lower(), int(meminfo.get(sawwc, 0))))

        else:
            return False
