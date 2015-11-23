# Stripe Datadog checks

This is a collection of plugins — [checks](http://docs.datadoghq.com/guides/agent_checks/) in Datadog parlance — for the [Datadog agent](https://github.com/datadog/dd-agent) that Stripe has found useful with Datadog.

# Motivation

We've sent a lot of patches to [Datadog](https://www.datadoghq.com/) and we regularly work closely with them on our ideas. But sometimes we want something that isn't a fit for the mainline Datadog agent. To that end we've created this repository to hold work that is either in flight or was decided to not be a fit for inclusion in the core agent set. We hope you find it useful!

# Checks

## Nagios Runner

The Nagios Runner check takes a list of check "instances". The instances are each executed and, [according to the Nagios Plugin API](https://assets.nagios.com/downloads/nagioscore/docs/nagioscore/3/en/pluginapi.html) the return value is inspected and a [service check](http://docs.datadoghq.com/api/#service_checks) is submitted using the provided name.

```yaml
init_config:
  # Not needed

instances:
  - name: "stripe.check.is_llama_on_rocket"
    command: "/usr/lib/nagios/plugins/check_if_llama_is --on rocket"
  - name: "stripe.check.falafel_length"
    command: "/usr/lib/nagios/plugins/check_falafel -l 1234"
```
