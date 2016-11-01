import csv
import os
import datetime
from collections import defaultdict

# project
from checks import AgentCheck


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
            users = defaultdict(int)
            for row in reader:
                if len(row) < 2:
                    continue 
                if row[0] != "CLIENT_LIST":
                    continue
                #TODO parse routing table as well
                username = row[1]
                users[username] += 1

            for user, num in users.iteritems():
                self.gauge('openvpn.users.connections', num, tags=instance_tags + ['common_name:{0}'.format(user)])


