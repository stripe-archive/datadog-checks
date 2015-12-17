# project
from checks import AgentCheck
from utils.platform import Platform
import utils.subprocess_output

import re
import subprocess

class MoreUnixCheck(AgentCheck):
    def check(self, instance):
        if Platform.is_linux():
            tags = instance.get('tags', [])

            try:
                with open('/proc/meminfo', 'r') as mem_info:
                    lines = mem_info.readlines()

            except Exception:
                self.logger.exception('Cannot get memory metrics from /proc/meminfo')
                return False

            regexp = re.compile(r'^(\w+):\s+([0-9]+)')  # We run this several times so one-time compile now
            meminfo = {}

            for line in lines:
                try:
                    match = re.search(regexp, line)
                    if match is not None:
                        meminfo[match.group(1)] = match.group(2)
                except Exception:
                    self.logger.exception("Cannot parse /proc/meminfo")

            try:
                self.gauge('linux.memory.slab', int(meminfo.get('Slab', 0)) / 1024, tags)
                self.gauge('linux.memory.pagetables', int(meminfo.get('PageTables', 0)) / 1024, tags)
                self.gauge('linux.memory.swapcached',int(meminfo.get('SwapCached', 0)) / 1024, tags)
            except Exception:
                self.logger.exception('Cannot compute stats from /proc/meminfo')

        else:
            return False
