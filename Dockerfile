FROM ubuntu:14.04
MAINTAINER The Stripe Observability Team <support@stripe.com>

RUN apt-get update && apt-get install -y build-essential python-dev python-virtualenv curl
RUN curl https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py && python /tmp/get-pip.py && pip --version
RUN DD_API_KEY='foo' DD_INSTALL_ONLY=true bash -c "$(curl -L https://raw.githubusercontent.com/DataDog/dd-agent/master/packaging/datadog-agent/source/install_agent.sh)"
RUN mkdir /src
ADD requirements.txt requirements-test.txt Makefile /src/
RUN make -C /src test-requirements

ADD . /src

CMD make -C /src test install
