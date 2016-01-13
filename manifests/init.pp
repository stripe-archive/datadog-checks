class stripe_datadog_checks {
  
  file { ["/opt/datadog-agent", "/opt/datadog-agent/agent/", "/opt/datadog-agent/agent/checks.d"]:
    ensure  => "directory"
  }

  file { "/opt/datadog-agent/agent/checks.d/nagios_runner.py":
    ensure => present,
    source => "puppet:///modules/stripe_datadog_agent/nagios_runner.py",
    owner   => root,
    group   => root,
    mode    => '0644',
    notify  => Service[$datadog_agent::params::service_name]
  }

  file { "/opt/datadog-agent/agent/checks.d/linux_proc_extras.py":
    ensure => present,
    source => "puppet:///modules/stripe_datadog_agent/linux_proc_extras.py",
    owner   => root,
    group   => root,
    mode    => '0644',
    notify  => Service[$datadog_agent::params::service_name]
  }

  file { "/etc/dd-agent/conf.d/linux_proc_extras.yaml":
    ensure => present,
    owner   => root,
    group   => root,
    mode    => '0644',
    notify  => Service[$datadog_agent::params::service_name],
    content => template('stripe_datadog_agent/linux_proc_extras.yaml')
  }

  file { "/opt/datadog-agent/agent/checks.d/linux_mem_extras.py":
    ensure => present,
    source => "puppet:///modules/stripe_datadog_agent/linux_mem_extras.py",
    owner   => root,
    group   => root,
    mode    => '0644',
    notify  => Service[$datadog_agent::params::service_name]
  }

  file { "/etc/dd-agent/conf.d/linux_mem_extras.yaml":
    ensure => present,
    owner   => root,
    group   => root,
    mode    => '0644',
    notify  => Service[$datadog_agent::params::service_name],
    content => template('stripe_datadog_agent/linux_mem_extras.yaml')
  }
}
