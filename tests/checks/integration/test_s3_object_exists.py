import datetime
import os
import json
from tempfile import mkstemp, gettempdir

# 3rd party
from botocore import stub

# project
from checks import AgentCheck
from tests.checks.common import AgentCheckTest, load_check


class TestFileUnit(AgentCheckTest):
    CHECK_NAME = 's3_object_exists'

    def check_with_contents(self, *contents, **instance_config):
        fd, path = mkstemp()
        with os.fdopen(fd, 'w') as conf_file:
            json.dump({"id": "the_id", "key": "the_key"}, conf_file)
        conf = {
            "init_config": {
                "credentials_json_file_path": path,
                "aws_access_key_id_field_name": "id",
                "aws_secret_access_key_field_name": "key",
            },
            "instances": [
                dict(
                    {
                        "uri": "s3://my-bucket/my/path/prefix/{date_stamp}",
                        "sla_seconds": 36000,
                        "min_size_bytes": 10000,
                        "run_time": "2016-12-01 13:05:01",
                    },
                    **instance_config
                ),
            ],
        }

        content_default = {
            'Key': 'part-00000-m-00000.parquet',
            'LastModified': datetime.datetime(2015, 1, 1),
            'ETag': 'the-tag',
            'Size': 10000000,
            'StorageClass': 'STANDARD',
            'Owner': {
                'DisplayName': 'yours truly',
                'ID': 'my id'
            }
        }
        response = {
            'IsTruncated': False,
            'Contents': [dict(content_default, **c) for c in contents],
        }
        check = load_check('s3_object_exists', conf, {})

        stub_s3 = stub.Stubber(check.get_client())
        stub_s3.add_response(
            'list_objects',
            response,
        )
        with stub_s3:
            check.check(conf["instances"][0])

        service_checks = check.get_service_checks()
        self.assertEqual(
            1,
            len(service_checks),
            "Failed to perform service checks {0!r}".format(service_checks),
        )
        return service_checks[0]

    def test_file_present(self):
        result = self.check_with_contents({})
        self.assertEqual(0, result['status'], result)
        self.assertEqual(
            's3.object_created_within_daily_sla',
            result['check'],
            result)

    def test_file_absent(self):
        result = self.check_with_contents()
        self.assertEqual(2, result['status'], result)

    def test_file_absent_in_sla(self):
        result = self.check_with_contents(sla_seconds=(60 * 60 * 23))
        self.assertEqual(0, result['status'], result)

    def test_small_file(self):
        result = self.check_with_contents({"Size": 3})
        self.assertEqual(2, result['status'], result)
