install:
	mkdir -p /build
	cp -Rp ./checks.d /build
	cp -Rp ./conf.d /build

test:
	virtualenv /src/venv
	/src/venv/bin/pip install -r requirements.txt
	/src/venv/bin/pip install -r requirements-test.txt
	ln -sf /src/checks.d/* /opt/datadog-agent/agent/checks.d/
	sh -c '. /src/venv/bin/activate ; env PYTHONPATH=$(echo $PYTHONPATH):/opt/datadog-agent/agent nosetests tests/checks/integration/test_file.py'

.PHONY: test install
