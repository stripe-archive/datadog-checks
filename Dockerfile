FROM ubuntu:14.04
MAINTAINER The Stripe Observability Team <support@stripe.com>

RUN apt-get update && apt-get install -y build-essential python-dev python-pip python-virtualenv curl
RUN DD_API_KEY='foo' DD_INSTALL_ONLY=true bash -c "$(curl -L https://raw.githubusercontent.com/DataDog/dd-agent/master/packaging/datadog-agent/source/install_agent.sh)"

ADD . /src
RUN make -C /src test
RUN make -C /src install

CMD true
