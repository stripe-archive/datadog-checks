install:
	mkdir -p /build
	cp -Rp ./checks.d /build
	cp -Rp ./conf.d /build

/src/venv:
	virtualenv /src/venv

test-requirements: /src/venv requirements.txt requirements-test.txt
	/src/venv/bin/pip install -r requirements.txt
	/src/venv/bin/pip install -r requirements-test.txt

test: test-requirements
	ln -sf /src/checks.d/* /opt/datadog-agent/agent/checks.d/
	sh -c '. /src/venv/bin/activate ; env PYTHONPATH=$(echo $PYTHONPATH):/opt/datadog-agent/agent nosetests tests/checks/integration/test_*.py'

.PHONY: test-requirements test install
