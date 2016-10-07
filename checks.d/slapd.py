# stdlib
import time
import warnings
try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

# 3rd party
import ldap

# project
from checks import AgentCheck


class Slapd(AgentCheck):

    CONNECT_CHECK_NAME = 'slapd.can_connect'

    def check(self, instance):
        if 'uri' not in instance:
            raise Exception('slapd instance missing "uri" value.')

        # Load values from instance configuration
        instance_tags = instance.get('tags', []) + ['instance:{0}'.format(instance['uri'])]

        # Connect to the LDAP server, and also update our service check.
        try:
            start_time = time.time()
            conn = self.connect_to_server(instance)
            elapsed_time = time.time() - start_time
            self.histogram('slapd.connect_time', int(elapsed_time))
        except ldap.LDAPError:
            self.service_check(self.CONNECT_CHECK_NAME, AgentCheck.CRITICAL,
                message="Could not connect to LDAP server",
                tags=[])
            return
        else:
            self.service_check(self.CONNECT_CHECK_NAME, AgentCheck.OK, tags=[])

        # Connection info
        self.monotonic_count('slapd.connections.total',
                self.fetch_metric(conn, 'cn=Total,cn=Connections,cn=monitor'),
                tags=instance_tags)
        self.gauge('slapd.connections.current',
                self.fetch_metric(conn, 'cn=Current,cn=Connections,cn=monitor'),
                tags=instance_tags)

        # Statistics
        self.monotonic_count('slapd.statistics.bytes_total',
                self.fetch_metric(conn, 'cn=Bytes,cn=Statistics,cn=monitor'),
                tags=instance_tags)
        self.monotonic_count('slapd.statistics.entries_total',
                self.fetch_metric(conn, 'cn=Entries,cn=Statistics,cn=monitor'),
                tags=instance_tags)

        # Thread info
        self.gauge('slapd.threads.active',
                self.fetch_metric(conn, 'cn=Active,cn=Threads,cn=monitor'),
                tags=instance_tags)
        self.gauge('slapd.threads.open',
                self.fetch_metric(conn, 'cn=Open,cn=Threads,cn=monitor'),
                tags=instance_tags)
        self.gauge('slapd.threads.pending',
                self.fetch_metric(conn, 'cn=Pending,cn=Threads,cn=monitor'),
                tags=instance_tags)
        self.gauge('slapd.threads.starting',
                self.fetch_metric(conn, 'cn=Starting,cn=Threads,cn=monitor'),
                tags=instance_tags)

        # Waiters info
        self.gauge('slapd.waiters.read',
                self.fetch_metric(conn, 'cn=Read,cn=Waiters,cn=monitor'),
                tags=instance_tags)
        self.gauge('slapd.waiters.write',
                self.fetch_metric(conn, 'cn=Write,cn=Waiters,cn=monitor'),
                tags=instance_tags)

    def fetch_metric(self, conn, bind, type=int):
        self.log.debug("Running bind: {1}", bind)

        try:
            res = conn.search_s(bind, ldap.SCOPE_SUBTREE, '(objectClass=*)', ['*', '+'])
            if len(res) == 0:
                self.log.warn("No results for bind: {0}", bind)
                return None
        except ldap.NO_SUCH_OBJECT:
            self.log.warn("No such object for bind: {0}", bind)
            return None
        except ldap.LDAPError as e:
            self.log.error("Unexpected error for bind {0}:", bind, e)
            return None

        # Take first result from the server
        _, attrs = res[0]

        obj_class = attrs['structuralObjectClass'][0]
        if obj_class == 'monitoredObject':
            value_field = 'monitoredInfo'
        elif obj_class == 'monitorCounterObject':
            value_field = 'monitorCounter'
        else:
            self.log.error("Unknown type of metric: {0}", obj_class)
            return None

        try:
            # Since a single result can contain multiple values, we also take
            # the first element in the list.
            value = attrs[value_field][0]
        except (KeyError, IndexError):
            self.log.error("Unable to extract value from bind: {0}", bind)
            return None

        # Try to convert by passing the value to the type of the metric.
        converted = value
        if type is not None:
            try:
                converted = type(value)
            except (ValueError, TypeError):
                self.log.warn('Unable to convert metric for bind {0}: {1} cannot be converted to {2}',
                    bind,
                    value,
                    type.__name__
                )

        self.log.debug("Finished with bind: {0}", bind)
        return converted

    def connect_to_server(self, instance):
        uri_info = urlparse(instance['uri'])
        use_ldaps = uri_info.scheme == 'ldaps'

        l = ldap.initialize(instance['uri'])
        options = [
            ('network_timeout', ldap.OPT_NETWORK_TIMEOUT, int),
            ('protocol_version', ldap.OPT_PROTOCOL_VERSION, int),
        ]

        tls_options = [
            ('tls_cacert', ldap.OPT_X_TLS_CACERTFILE, str),
            ('tls_certfile', ldap.OPT_X_TLS_CERTFILE, str),
            ('tls_keyfile', ldap.OPT_X_TLS_KEYFILE, str),
        ]

        # Helper function that actually sets options on the connection.
        def set_options(defs):
            for name, ldapopt, ty in defs:
                val = instance.get(name)
                if not val:
                    continue

                if not isinstance(val, ty):
                    raise TypeError('slapd instance has key "%s" of type "%s", but expected type "%s"' % (
                        name,
                        type(val),
                        ty
                    ))

                l.set_option(ldapopt, val)

        # Always set generic options
        l.set_option(ldap.OPT_REFERRALS, 0)
        set_options(options)

        # Only set TLS options if necessary
        if instance.get('starttls', False) or use_ldaps:
            set_options(tls_options)

            # If we're connecting using LDAPS, we demand TLS.
            l.set_option(ldap.OPT_X_TLS, ldap.OPT_X_TLS_DEMAND if use_ldaps else ldap.OPT_X_TLS_NEVER)

            # Set up cert verification.
            l.set_option(ldap.OPT_X_TLS_REQUIRE_CERT,
                    ldap.OPT_X_TLS_DEMAND if instance.get('verify_cert') else ldap.OPT_X_TLS_ALLOW)

            # Force the creation of a new TLS context.  This must be the last TLS option.
            l.set_option(ldap.OPT_X_TLS_NEWCTX, 0) 

        # Once we're done with all options, perform STARTTLS (as long as this
        # isn't a LDAPS connection).
        if instance.get('starttls', False):
            if use_ldaps:
                warnings.warn("Can't use STARTTLS since connection is already using SSL (LDAPS)")
            else:
                l.start_tls_s()

        # Perform either simple or anonymous bind.
        password = instance.get('bind_password')
        if password:
            l.simple_bind_s(instance.get('bind_dn'), password)
        else:
            l.simple_bind_s()

        return l
