# Stripe Datadog checks

This is a collection of plugins — [checks](http://docs.datadoghq.com/guides/agent_checks/) in Datadog parlance — for the [Datadog agent](https://github.com/datadog/dd-agent) that Stripe has found useful with Datadog.

# Motivation

We've sent a lot of patches to [Datadog](https://www.datadoghq.com/) and we regularly work closely with them on our ideas. But sometimes we want something that isn't a fit for the mainline Datadog agent. To that end we've created this repository to hold work that is either in flight or was decided to not be a fit for inclusion in the core agent set. We hope you find it useful!

# Using The Checks

Place the `.py` file you want to use in to the checks directory — `/etc/dd-agent/checks.d` by default — and the YAML config file in the config directory — `/etc/dd-agent/conf.d` by default — and you should be ready to do! Restart the agent and run `/etc/init.d/datadog-agent info` to verify that the plugin is working.

Each plugin here is provided with a sample config file containing some documentation.

# Checks

Here's our list of checks!

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

## SubDir Sizes

The SubDir Sizes is a sister to Datadog's `directory` integeration. Our needs required enough differences that making a new integration
seemed the easier path and made for a less complex configuration.  It takes a `directory` and emits a total size (in bytes) and a
count of files therein for each subdirectory it finds. It also can use a regular expression to dynamically create tags for each subdirectory.
This integation is useful for getting tag-friendly metrics for backup directories and things like Kafka that store in subdirectories.

Here's the config we use for Kafka:
```yaml
nit_config:

instances:
  - directory: "/pay/kafka/data"
    dirtagname: "name"
    subdirtagname: "topic"
    subdirtagname_regex: "(?P<topic>.*)-(?P<partition>\\d+)"
```

**Note**: The regular expression provided to `subdirtagname_regex` should use [named groups](https://docs.python.org/2/howto/regex.html#non-capturing-and-named-groups)
such that calling `groupdict()` on the resulting match provides name-value pairs for use as tags!

And here are the metrics, each of which will be tagged with `$dirtagname:$DIRECTORY` and `$subdirtagname:basename(subdir)` and whatever tags come from `subdirtagname_regex`:
  * system.sub_dir.bytes
  * system.sub_dir.files
