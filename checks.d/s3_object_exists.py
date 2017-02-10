# stdlib
import datetime
import json
import os
try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

# 3rd party
import boto3

# project
from checks import AgentCheck


class S3ObjectExists(AgentCheck):
    """
    Ensure that one or more S3 objects with a URL prefix exists by that time
    `sla_seconds` have passed since the start of the day.

    This is particularly helpful for determining if daily-generated files
    have been created on time, and to alert if they are missing.
    """

    def __init__(self, name, init_config, agentConfig, instances=None):
        AgentCheck.__init__(self, name, init_config, agentConfig, instances)
        self._client = None

    def get_client(self):
        if self._client:
            return self._client

        credentials_path = self.init_config["credentials_json_file_path"]
        if not os.path.isfile(credentials_path):
            raise Exception(
                "Credentials file does not exist: {}".format(credentials_path)
            )
        with open(credentials_path) as infile:
            try:
                all_credentials = json.load(infile)
            except:
                # Catch and re-raise here to avoid leaking credentials in the
                # exception message
                raise Exception(
                    "Error reading or parsing JSON from {}".format(credentials_path))

        key_id = all_credentials[
            self.init_config['aws_access_key_id_field_name']]
        access_key = all_credentials[
            self.init_config['aws_secret_access_key_field_name']]
        self._client = boto3.client(
            's3',
            aws_access_key_id=key_id,
            aws_secret_access_key=access_key,
        )
        return self._client

    def get_datestamp(self, now):
        return now.strftime("%Y%m%d")

    def get_date(self, now):
        return datetime.datetime(
            now.year, now.month, now.day, tzinfo=now.tzinfo)

    def check(self, instance):
        if 'uri' not in instance:
            raise Exception('s3_object_exists instance missing "uri" value')
        if 'run_time' in instance:
            now = datetime.datetime.strptime(
                instance['run_time'], '%Y-%m-%d %H:%M:%S')
        else:
            now = datetime.datetime.utcnow()
        uri_str = instance['uri'].format(date_stamp=self.get_datestamp(now))
        uri = urlparse(uri_str)
        if uri.scheme.lower() != 's3':
            raise ValueError(
                'Invalid URI scheme: {0}, expected "s3"'.format(uri.scheme)
            )
        if "sla_seconds" not in instance:
            raise Exception(
                's3_object_exists instance missing "sla_seconds" value')
        sla_seconds = instance["sla_seconds"]

        client = self.get_client()
        objects = []
        list_args = {"Bucket": uri.netloc, "Prefix": uri.path.lstrip('/')}
        while True:
            resp = client.list_objects(**list_args)
            objects.extend(resp['Contents'])
            if not resp['IsTruncated']:
                break
            list_args["Marker"] = resp['Marker']

        if 'min_size_bytes' in instance:
            min_size = instance['min_size_bytes']
            objects = [o for o in objects if o['Size'] >= min_size]
        if 'max_size_bytes' in instance:
            max_size = instance['max_size_bytes']
            objects = [o for o in objects if o['Size'] <= max_size]

        safe = objects or self.is_within_sla(sla_seconds, now)
        message = (
            "A S3 object was found at {0}".format(uri_str) if objects
            else (
                "No S3 object was found at {0} but less than {1} seconds have "
                "elapsed since the start of the day"
                if safe else "No S3 object was found at {0}"
            )
        ).format(uri_str, sla_seconds)
        self.service_check(
            check_name="s3.object_created_within_daily_sla",
            status=(AgentCheck.OK if safe else AgentCheck.CRITICAL),
            tags=instance.get('tags', []),
            message=message,
        )

    def is_within_sla(self, sla_seconds, now):
        date = self.get_date(now)
        delta = (now - date).total_seconds()
        return delta <= sla_seconds
