import requests

from checks import AgentCheck
import collections


class HadoopResourceManager(AgentCheck):
    DEFAULT_TIMEOUT = 1
    CONNECT_CHECK_NAME = 'hadoop_resourcemanager.can_connect'

    def check(self, instance):
        if 'url' not in instance:
            self.log.info("Skipping instance, no url found.")
            return

        if 'resourcemanager_url' not in instance:
            self.log.info("Skipping instance no resourcemanager_url found.")
            return

        instance_tags = instance.get('tags', [])
        timeout = self.init_config.get('default_timeout', self.DEFAULT_TIMEOUT)
        job_tracker_resp = self.get_json(instance['url'] + "/jobs/", timeout)
        resourcemanager_resp = self.get_json(instance['resourcemanager_url'] + "/ws/v1/cluster/metrics", timeout)

        jobs = filter(lambda item: item['details']['state'] == 'RUNNING', job_tracker_resp)

        metrics = collections.Counter(
            maps_pending=0,
            maps_running=0,
            reduces_pending=0,
            reduces_running=0,
        )
        for j in jobs:
            if j['details']['mapProgress'] < 100:
                metrics['maps_running'] += j['details']['mapsRunning']
                metrics['maps_pending'] += j['details']['mapsPending']
            else:
                metrics['reduces_running'] += j['details']['reducesRunning']
                metrics['reduces_pending'] += j['details']['reducesPending']

        self.gauge('data.mapreduce.jobs.running', metrics['maps_running'], tags=instance_tags + ['job_type:map'])
        self.gauge('data.mapreduce.jobs.running', metrics['reduces_running'], tags=instance_tags + ['job_type:reduce'])
        self.gauge('data.mapreduce.jobs.pending', metrics['maps_pending'], tags=instance_tags + ['job_type:map'])
        self.gauge('data.mapreduce.jobs.pending', metrics['reduces_pending'], tags=instance_tags + ['job_type:reduce'])

        self.gauge('data.mapreduce.vcores',  resourcemanager_resp['clusterMetrics']['totalVirtualCores'], tags=instance_tags)
        self.gauge('data.mapreduce.nodes',  resourcemanager_resp['clusterMetrics']['activeNodes'], tags=instance_tags + ['status=active'])
        self.gauge('data.mapreduce.nodes',  resourcemanager_resp['clusterMetrics']['lostNodes'], tags=instance_tags + ['status=lost'])

    def get_json(self, url, timeout):
        try:
            r = requests.get(url, timeout=timeout, headers={'accept': 'application/json'})
            r.raise_for_status()
        except requests.exceptions.Timeout:
            # If there's a timeout
            self.service_check(
                self.CONNECT_CHECK_NAME, AgentCheck.CRITICAL,
                message='%s timed out after %s seconds.' % (url, timeout),
                tags=["url:{0}".format(url)]
            )
            raise Exception("Timeout when hitting %s" % url)

        except requests.exceptions.HTTPError:
            self.service_check(
                self.CONNECT_CHECK_NAME, AgentCheck.CRITICAL,
                message='%s returned a status of %s' % (url, r.status_code),
                tags=["url:{0}".format(url)]
            )
            raise Exception("Got %s when hitting %s" % (r.status_code, url))

        else:
            self.service_check(
                self.CONNECT_CHECK_NAME, AgentCheck.OK,
                tags=["url:{0}".format(url)]
            )

        return r.json()
