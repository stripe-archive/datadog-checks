import subprocess

from checks import AgentCheck


class UnboundCheck(AgentCheck):
    SERVICE_CHECK_NAME = 'unbound'

    def get_cmd(self):
        if self.init_config.get('sudo'):
            cmd = 'sudo unbound-control stats'
        else:
            cmd = 'unbound-control stats'

        return cmd

    def get_stats(self):
        cmd = self.get_cmd()

        try:
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
        except subprocess.CalledProcessError as e:
            error_msg = 'ERROR CALLING {0}: {1}  {2}'.format(cmd, e, e.output)
            self.service_check(
                self.SERVICE_CHECK_NAME,
                AgentCheck.CRITICAL,
                message=error_msg,
            )
            self.log.error()
            return None

        return output

    def parse_stat(self, stat):
        label, stat = stat.split("=")
        prefix, suffix = label.split(".", 1)

        by_tag_labels = [
            'num.query.flags',
            'num.query.edns',
            'num.answer.rcode',
        ]

        tags = []
        if prefix.startswith('thread'):
            tags.append("thread:{}".format(prefix[-1]))
            metric = suffix
        elif label.startswith('histogram'):
            # E.g. histogram.000000.524288.to.000001.000000=59
            # This the count of requests needing recursive processing whose processing time fell in the window
            # specified by  <sec>.<usec>.to.<sec>.<usec>.
            metric = "histogram"
            _, window = label.split(".", 1)
            tags.append("bucket:{}".format(window))
        elif any(label.startswith(lbl) for lbl in by_tag_labels):
            # E.g.
            # num.query.flags.QR
            # metric = num.query.flags
            # tag = {flags: QR}
            metric, tag = label.rsplit('.', 1)
            _, tag_name = metric.rsplit('.', 1)
            tags.append("{}:{}".format(tag_name, tag))
        else:
            metric = label

        rate_metrics = [
            "histogram",
            "num.queries",
            "num.cachehits",
            "num.cachemiss",
            "num.prefetch",
            "num.recursivereplies",
            "requestlist.overwritten",
            "requestlist.exceeded",
            "tcpusage",
            "num.query.flags",
            "num.query.edns",
            "num.answer.rcode",
        ]
        gauge_metrics = [
            "requestlist.max",
            "requestlist.avg",
            "requestlist.overwritten",
            "requestlist.current.all",
            "requestlist.current.user",
            "recursion.time.avg",
            "recursion.time.median",
        ]

        rate_metrics = rate_metrics + ["total.{}".format(m) for m in rate_metrics]
        gauge_metrics= gauge_metrics + ["total.{}".format(m) for m in gauge_metrics]

        ns_metric = "unbound.{}".format(metric)
        if metric in rate_metrics:
            self.rate(ns_metric, float(stat), tags)
        elif metric in gauge_metrics:
            self.gauge(ns_metric, float(stat), tags)
        else:
            self.count(ns_metric, float(stat), tags)

    def check(self, instance):
        stats = self.get_stats()

        if stats is None:
            return

        try:
            for line in stats.split("\n"):
                if not line:
                    continue
                self.parse_stat(line)
        except Exception as e:
            self.service_check(
                self.SERVICE_CHECK_NAME,
                AgentCheck.CRITICAL,
                message="Error when parsing unbound stats: {0}".format(e),
            )
            return

        self.service_check(self.SERVICE_CHECK_NAME, AgentCheck.OK)

