# Stripe Datadog checks

This is a collection of plugins — [checks](http://docs.datadoghq.com/guides/agent_checks/) in Datadog parlance — for the [Datadog agent](https://github.com/datadog/dd-agent) that Stripe has found useful with Datadog.

# Motivation

We've sent a lot of patches to [Datadog](https://www.datadoghq.com/) and we regularly work closely with them on our ideas. But sometimes we want something that isn't a fit for the mainline Datadog agent. To that end we've created this repository to hold work that is either in flight or was decided to not be a fit for inclusion in the core agent set. We hope you find it useful!

# Using The Checks

Place the `.py` file you want to use in to the checks directory — `/etc/dd-agent/checks.d` by default — and the YAML config file in the config directory — `/etc/dd-agent/conf.d` by default — and you should be ready to go! Restart the agent and run `/etc/init.d/datadog-agent info` to verify that the plugin is working.

Each plugin here is provided with a sample config file containing some documentation.

# Checks

Here's our list of checks!

## File

Uses Python's `glob.glob` to look look for at least one file matching the provided `path`. You can control the success or failure of this check via `expect` using one of `present` or `absent`. For example if you use `expect: present` and the file does not exist, this check will fail. If you use `expect: absent` and the file is absent, it will emit ok!

The service check and any emitted metrics are tagged with the `path`, `expected_status` and `actual_status`. It's check message will be `File %s that was expected to be %s is %s instead" % (path, expect, status)`.

If this check *does* find a path that matches it will also emit a gauge `file.age_seconds` containing the age of the *oldest* file in seconds that matches the path.

```
---
init_config:

instances:
  # Puppet locks (these might turn stale):
  - path: '/etc/stripe/facts/puppet_locked.txt'
    expect: absent

  # Package upgrades requiring reboots
  - path: '/var/run/stripe/restart-required/*'
    expect: absent
```

## Resque

Fetches metrics about processed jobs from Resque. It's pretty minimal, but we only needed it for a small thing.

## Jenkins Metrics

Fetches metrics from Jenkin's [Metrics Plugin](https://wiki.jenkins-ci.org/display/JENKINS/Metrics+Plugin) (which you must install separately). It fetches all the metrics under `vm.*` and emits them as gauges except the `vm.gc.*.count` and `vm.gc.*.time` which are emitted as `monotonic_count`.

## Linux VM Extras

Fetches the following metrics by polling Linux' '/proc/vmstat':

* `system.linux.vm`
  * `pgpgin` as `pages.in`,
  * `pgpgout` as `pages.out`,
  * `pswpin` as `pages.swapped_in`,
  * `pswpout` as `pages.swapped_out`,
  * `pgfault` as `pages.faults`,
  * `pgmajfault` as `pages.major_faults`

## NSQ

Fetches the following metrics by polling NSQ's `/stats` endpoint:

* `nsq.topic_count`
* `nsq.topic.channel_count`
* `nsq.topic` (all tagged with `topic_name`):
  * `depth`
  * `backend_depth`
  * `message_count` (count, not gauge)
* `nsq.topic.channel` (all tagged with `topic_name` and `channel_name`):
  * `depth`
  * `backend_depth`
  * `in_flight_count`
  * `deferred_count`
  * `message_count` (count, not gauge)
  * `requeue_count`
  * `timeout_count`
  * `e2e_processing_latency.p50` (nanoseconds)
  * `e2e_processing_latency.p95` (nanoseconds)
  * `e2e_processing_latency.p99` (nanoseconds)
  * `e2e_processing_latency.p999` (nanoseconds)
  * `e2e_processing_latency.p9999` (nanoseconds)
* `nsq.topic.channel.client` (all tagged with `topic_name`, `channel_name` and `client_id`, `client_version`, `tls`, `user_agent`, `deflate` and `snappy`):
  * `ready_count`
  * `in_flight_count`
  * `message_count` (count, not gauge)
  * `finish_count`
  * `requeue_count`

## Nagios Runner

The Nagios Runner check takes a list of check "instances". The instances are each executed and, [according to the Nagios Plugin API](https://assets.nagios.com/downloads/nagioscore/docs/nagioscore/3/en/pluginapi.html) the return value is inspected and a [service check](http://docs.datadoghq.com/api/#service_checks) is submitted using the provided name.

**Note**: The checks supplied are executed sequentially. You may run in to performance issues if you attempt to run too many checks or checks that execute very slowly. This will effectively block the agent and cause all sorts of hiccups!

```yaml
init_config:
  # Not needed

instances:
  - name: "stripe.check.is_llama_on_rocket"
    command: "/usr/lib/nagios/plugins/check_if_llama_is --on rocket"
  - name: "stripe.check.falafel_length"
    command: "/usr/lib/nagios/plugins/check_falafel -l 1234"
```

## OpenVPN


The OpenVPN check counts the number of active VPN connections per user. Combined with a Datadog monitor, it ensures that the same user isn't logged in mtoo many times (e.g., multiple, sustained VPN connections for the same user is indicative of a laptop compromise).

Each VPN is accessible over both TCP and UDP, and is available to both privileged (Stripe employees) and unprivileged users (vendors). The unique combination of these is considered a VPN "level", and OpenVPN emits a status file every 10 seconds for each level to indicate the currently-active connections. When a user disconnects (e.g. if their Internet connection drops out) or if their IP address/port changes, they may appear in the status file multiple times. This is fine, as long as the number of connections per user drops down to 1 within a minute or so.

The status file also contains useful information such as the IP (which can be used for geolookups), the connection duration (which can be used to ensure that the VPN is online and that it isn't cycling users), and the number of bytes sent/received (which could be used to detect erratic behavior).

## Out of memory killer (OOM)

This check emits a failure when any process has been killed by the OOM killer
since the system last started up. It continues to emit criticals until the log file is removed or the system is restarted (providing the log file contains uptimes to detect a reboot)

It reads the configured `logfile` as syslog kernel output for lines matching the `kernel_line_regex` property. The regular expression should provide named capture groups for `message` and, optionally, `uptime`. The `uptime` capture group is how it detects system reboots; it will stop looking for OOM instances when it detects a reboot. The second configurable regular expression extracts information from the `message` data itself, which is included in the service check message (not as tags, as this would pose problems with alert recovery).

An example configuration for a base Ubuntu system goes like this:

```yaml
---
init_config:
instances:
  - logfile: '/var/log/kern.log'
    kernel_line_regex: '^(?P<timestamp>.+?) (?P<host>\S+) kernel: \[\s*(?P<uptime>\d+(?:\.\d+)?)\] (?P<message>.*)$'
    kill_message_regex: '^Out of memory: Kill process (?P<pid>\d+) \((?P<pname>.*?)\) score (?P<score>.*?) or sacrifice child'
```

This file is included in `conf.d/oom.yaml`.

Two error cases also emit service checks:
1. If the log file is not present, a warning is emitted; this is not inherently a problem but could indicate misconfiguration
2. If a permission error prevents dd-agent from reading the file, a critical is emitted; this is a definite failure and needs correcting


## Outdated Packages

This check verifies that the given packages are not outdated (currently, only
on Ubuntu).  You can specify a set of package names and versions (split out by
release), and this check will report critical if the current version of that
package is older than the specified version.  For example:

```yaml
init_config:
  # Not needed

instances:
  - package: bash
    version:
      precise: "4.2-2ubuntu2.6"
      trusty: "4.3-7ubuntu1.5"

  - package: openssl
    version:
      precise: "1.0.1-4ubuntu5.31"
      trusty: "1.0.1f-1ubuntu2.15"
```

## Resque

Inspects the Redis storage for a Resque instance and ouputs some metrics:

* `resque.jobs.failed_total` - number of jobs failed (monotonic_count)
* `resque.jobs.processed_total` - number of jobs processed (monotonic_count)
* `resque.queues_count` - number of queues (gauge)
* `resque.worker_count` - number of workers (gauge)


## Slapd (OpenLDAP's Stand-alone LDAP Daemon)

This check queries and surfaces statistics from the [`monitor`
backend][ldapmon] of a running `slapd` instance.  It will emit the following
metrics:

* `slapd.connect_time` - time taken to connect to the server (histogram)
* `slapd.connections.total` - total number of connections (monotonic_count)
* `slapd.connections.current` - current number of connections (gauge)
* `slapd.statistics.bytes_total` - total bytes sent (monotonic_count)
* `slapd.statistics.entries_total` - total entries sent (monotonic_count)
* `slapd.threads.active` - number of active threads (gauge)
* `slapd.threads.open` - number of open threads (gauge)
* `slapd.threads.pending` - number of pending threads (gauge)
* `slapd.threads.starting` - number of threads being started (gauge)
* `slapd.waiters.read` - the number of clients waiting to read (gauge)
* `slapd.waiters.write` - the number of clients waiting to write (gauge)

In addition, the check will emit a service check (`slapd.can_connect`) that
indicates whether it was able to successfully connect to the LDAP server.

[ldapmon]: http://www.openldap.org/doc/admin24/monitoringslapd.html

### Slapd Configuration

To enable the `monitor` backend, you can add the following lines to
`slapd.conf`:

```
moduleload back_monitor
database monitor
access to dn="cn=monitor"
  by peername=127.0.0.1 read
  by * none
```

This allows only clients on the local machine to access the backend, since it
may contain potentially-sensitive information.

## Storm REST API

This check comes in two parts: One is a cronjob-able script in
`scripts/cache-storm-data` (intended to run every minute, or whichever
interval doesn't overload your nimbus), and the other is a check that
reads the generated JSON file and emits metrics.

For the check, we recommend running it at an interval 2x faster than
the cache-storm-data cron job runs (using the
`min_collection_interval: <Nsec>` config parameter in `init_config`).

You can configure the topologies considered for emission using the
`topologies` regex, and the check will group all the matched metrics
(picking the youngest `ACTIVE` metric for each that have name
collisions).

The caching process can be very time-consuming since storm's executor
and per-topology stats take a really long time to generate. It's best
to run the cache script a few times across the lifetime of your storm
topologies to get a feel for how long it takes and how
resource-intensive the metrics-gathering can be.

The [`storm_rest_api.yaml`](conf.d/storm_rest_api.yaml.example) config file is used by both the
cache strip and the check.

## Splunk

Collects metrics from a Splunk master about the status of a Splunk cluster. It assumes you are
using Search Head Clustering and queries the SHC captain for search information.

It emits these service checks:
  * `splunk.can_connect` when things break during fetching status
  * `splunk.index.is_healthy` for "unhealthy" indices, tagged by `index_name`. See the message for more details.
  * `splunk.peer.is_healthy` for "unhealthy" nodes, tagged by `peer_name`. See the message for more details.

It emits these metrics:
* `splunk.fixups`
  * `jobs_present` tagged by `index_name` and `fixup_level`
* `splunk.indexes` tagged by `index_name`
  * `replication` tagged by `index_copy`, for each "copy"
    * `actual_copies` - Number of copies that actually exist.
    * `expected_copies` - Number of copies that *should* exist.
  * `search` tagged by `index_copy`, for each "copy"
    * `actual_copies` - Number of copies that actually exist.
    * `expected_copies` - Number of copies that *should* exist.
  * `size_bytes` - The total size in bytes.
  * `total_excess_bucket_copies` - The total number of excess copies for all buckets.
  * `total_excess_searchable_copies` - The total number of excess searchable copies for all buckets.
* `splunk.peers` tagged by `peer_name`, and `site`
  * `bucket_count` - The number of buckets on this peer tagged additionally by `index`.
  * `bucket_status` - The number of buckets in a given status on this peer, tagged additionally by `bucket_status`.
  * `delayed_buckets_to_discard` - The number of buckets waiting to be discarded on this peer.
  * `peers_present` - The number of peers available (as a gauge) tagged additionally by `status`.
  * `primary_count` - The number of buckets for which the peer is primary in its local site, or the number of buckets that return search results from same site as the peer.
  * `primary_count_remote`  - The number of buckets for which the peer is primary that are not in its local site.
  * `replication_count` - The number of replications this peer is part of, as either source or target.
* `splunk.search_cluster`
  * `captains` - The count of captains tagged by `site`. This can be used to ensure a captain and detect splitbrain
  * `member_statuses` - The number of members in the search cluster tagged by `status` and `site`.
* `splunk.searches`
  * `in_progress` - In progress search gauge, tagged by `is_saved` and `search_owner`.

You can configure it thusly:
```yaml
---
init_config:
  default_timeout: 30

instances:
  - url: https://localhost:8089
    username: obsrobot
    password: foobar
```

## SubDir Sizes

The SubDir Sizes is a sister to Datadog's `directory` integeration. Our needs required enough differences that making a new integration
seemed the easier path and made for a less complex configuration.  It takes a `directory` and emits a total size (in bytes) and a
count of files therein for each subdirectory it finds. It also can use a regular expression to dynamically create tags for each subdirectory.
This integation is useful for getting tag-friendly metrics for backup directories and things like Kafka that store in subdirectories.

Here's the config we use for Kafka:
```yaml
init_config:

instances:
  - directory: "/pay/kafka/data"
    dirtagname: "name"
    subdirtagname: "topic"
    subdirtagname_regex: "(?P<topic>.*)-(?P<partition>\\d+)"
```

**Note**: The regular expression provided to `subdirtagname_regex` should use [named groups](https://docs.python.org/2/howto/regex.html#non-capturing-and-named-groups)
such that calling `groupdict()` on the resulting match provides name-value pairs for use as tags!

And here are the metrics, each of which will be tagged with `$dirtagname:$DIRECTORY` and `$subdirtagname:basename(subdir)` and whatever tags come from `subdirtagname_regex`:
  * `system.sub_dir.bytes`
  * `system.sub_dir.files`
