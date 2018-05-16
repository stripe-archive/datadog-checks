# project
from checks import AgentCheck

VM_COUNTS = {
    'pgpgin': 'pages.in',
    'pgpgout': 'pages.out',
    'pswpin': 'pages.swapped_in',
    'pswpout': 'pages.swapped_out',
    'pgfault': 'pages.faults',
    'pgmajfault': 'pages.major_faults'
}

class MoreLinuxVMCheck(AgentCheck):
    def check(self, instance):
        tags = instance.get('tags', [])

        enabled_metrics = instance.get('enabled_metrics', list(VM_COUNTS.keys()))

        with open('/proc/vmstat', 'r') as vm_info:
            content = [line.strip().split() for line in vm_info.readlines()]

            for line in content:
                if line[0] in enabled_metrics:
                    self.monotonic_count("system.linux.vm.{0}".format(VM_COUNTS[line[0]]), int(line[1]), tags=tags)
