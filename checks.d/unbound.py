import subprocess

from checks import AgentCheck


class UnboundCheck(AgentCheck):
    SERVICE_CHECK_NAME = 'unbound'
    def __init__(self, name, init_config, agentConfig, instances=None):
        AgentCheck.__init__(self, name, init_config, agentConfig, instances)
        self.define_metric_types(init_config)

    def define_metric_types(self, init_config):
        override_rate_as_counter_metrics = init_config.get('override_rate_as_counter_metrics', [])

        rate_metrics = [
            "histogram",
            "num.answer.bogus",
            "num.answer.rcode",
            "num.answer.secure",
            "num.cachehits",
            "num.cachemiss",
            "num.dnscrypt.cert",
            "num.dnscrypt.cleartext",
            "num.dnscrypt.crypted",
            "num.dnscrypt.malformed",
            "num.prefetch",
            "num.queries",
            "num.queries_ip_ratelimited",
            "num.query.aggressive",
            "num.query.authzone.down",
            "num.query.authzone.up",
            "num.query.class",
            "num.query.dnscrypt.replay",
            "num.query.dnscrypt.shared_secret.cachemiss",
            "num.query.edns",
            "num.query.flags",
            "num.query.ipv6",
            "num.query.opcode",
            "num.query.ratelimited",
            "num.query.subnet",
            "num.query.subnet_cache",
            "num.query.tcp",
            "num.query.tcpout",
            "num.query.tls",
            "num.query.tls.resume",
            "num.query.type",
            "num.recursivereplies",
            "num.rrset.bogus",
            "num.zero_ttl",
            "requestlist.exceeded",
            "requestlist.overwritten",
            "unwanted.queries",
            "unwanted.replies",
        ]

        # Remove any rate metrics that have explicitly been overriden to be
        # reported as counters
        rate_metrics = list(set(rate_metrics) - set(override_rate_as_counter_metrics))

        gauge_metrics = [
            "dnscrypt_nonce.cache.count",
            "dnscrypt_shared_secret.cache.count",
            "infra.cache.count",
            "key.cache.count",
            "mem.cache.dnscrypt_nonce",
            "mem.cache.dnscrypt_shared_secret",
            "mem.cache.message",
            "mem.cache.rrset",
            "mem.mod.iterator",
            "mem.mod.validator",
            "mem.streamwait",
            "msg.cache.count",
            "recursion.time.avg",
            "recursion.time.median",
            "requestlist.avg",
            "requestlist.current.all",
            "requestlist.current.user",
            "requestlist.max",
            "rrset.cache.count",
            "tcpusage",
            "time.elapsed",
            "time.now",
            "time.up",
        ]

        self.by_tag_labels = [
            "num.answer.rcode",
            "num.query.aggressive",
            "num.query.class",
            "num.query.edns",
            "num.query.flags",
            "num.query.opcode",
            "num.query.type",
        ]

        self.rate_metrics = rate_metrics + ["total.{}".format(m) for m in rate_metrics]
        self.gauge_metrics= gauge_metrics + ["total.{}".format(m) for m in gauge_metrics]

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
        elif any(label.startswith(lbl) for lbl in self.by_tag_labels):
            # E.g.
            # num.query.flags.QR
            # metric = num.query.flags
            # tag = {flags: QR}
            metric, tag = label.rsplit('.', 1)
            _, tag_name = metric.rsplit('.', 1)
            tags.append("{}:{}".format(tag_name, tag))
        else:
            metric = label

        ns_metric = "unbound.{}".format(metric)
        if metric in self.rate_metrics:
            self.rate(ns_metric, float(stat), tags)
        elif metric in self.gauge_metrics:
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

