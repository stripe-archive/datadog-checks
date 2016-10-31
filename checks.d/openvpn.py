import csv
from collections import defaultdict

# project
from checks import AgentCheck


# Each user really should only have one active connection
# but empirically, a user can have 3 connections within a 10-second
# interval without it being the sign of a problem (probably 
# due to reconnections)
USER_MAX_CONNECTIONS = 4

class Splunk(AgentCheck):
    def check(self, instance):
        filename = instance['path']
        self.parse_status_file(filename)


    def parse_status_file(self, filename):
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
                if num > USER_MAX_CONNECTIONS:
                    raise Exception('User {0} connected too many times: {1}'.format(user, str(num)))







