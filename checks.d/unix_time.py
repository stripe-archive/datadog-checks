# project
from checks import AgentCheck
from utils.platform import Platform

import time

class UnixTimeCheck(AgentCheck):

    def check(self, instance):
        if not Platform.is_linux():
            return

        t = time.time()
        self.gauge('system.current_time', t)
