import csv
import os
import datetime
from collections import defaultdict
from collections import Counter
import re

# project
from checks import AgentCheck

IPV4_REGEX = re.compile('^((?:[0-9]{1,3}\.){3}[0-9]{1,3})(:\d+)*$')

# Removes the port from an IP address
# Currently assumes that the address is
# an IPv4 address
def strip_port(ipv4_address):
    matches = IPV4_REGEX.match(ipv4_address)
    if matches is not None:
        return matches.group(1)
    return None

# Infers the /24 of the address.
# e.g. 192.168.1.1 will return 192.168.1.0/24
def infer_subnet_24(ipv4_address):
    return '.'.join(ipv4_address.split('.', 3)[0:3] + ['0']) + '/24'

class OpenVPN(AgentCheck):

    # 15 seconds appears to be too short of an interval
    FILE_REFRESH_SECONDS = 25

    VPN_IS_RUNNING_CHECK_NAME = 'openvpn.status.is_running'


    def check(self, instance):
        # path and vpn_name should always be present
        filename = instance['path']
        vpn_name = instance['vpn_name']
        instance_tags = instance['tags']
        self.parse_status_file(filename, instance_tags)

        if not os.path.isfile(filename):
            self.service_check(self.VPN_IS_RUNNING_CHECK_NAME, AgentCheck.CRITICAL,
                    message='VPN level {0} is not running (status file is missing)'.format(vpn_name),
                    tags = instance_tags)

        mtimestamp = os.path.getmtime(filename)
        now = int(datetime.datetime.now().strftime("%s"))
        if now - mtimestamp > self.FILE_REFRESH_SECONDS:
            self.service_check(self.VPN_IS_RUNNING_CHECK_NAME, AgentCheck.CRITICAL,
                    message='VPN level {0} is not running (status file has not been refreshed since ${1})'.format(vpn_name, str(mtimestamp)),
                    tags = instance_tags)

    def parse_status_file(self, filename, instance_tags):
        with open(filename) as csvfile:
            reader = csv.reader(csvfile, delimiter='\t')
            users = defaultdict(list)
            for row in reader:
                if len(row) < 3:
                    continue
                if row[0] != "CLIENT_LIST":
                    continue
                #TODO parse ROUTING_TABLE entries as well
                username = row[1]

                # we don't care if the user's port changed
                real_address = strip_port(row[2])

                users[username].append(real_address)

            for user, addresses in users.iteritems():
                c = Counter(addresses)
                self.gauge('openvpn.users.connections.distinct_ip4', len(c), tags=instance_tags + ['common_name:{0}'.format(user)])
                for address in c:
                    count = c[address]
                    subnet = infer_subnet_24(address)
                    self.gauge('openvpn.users.connections', count, tags=instance_tags + ['common_name:{0}'.format(user),
                        'ip:{0}'.format(address),
                        'subnet:{0}'.format(subnet),
                        ])
