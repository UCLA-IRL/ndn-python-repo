FROM python:3.10-alpine AS ndn-python-repo

COPY . /repo

RUN pip install --disable-pip-version-check -e /repo[mongodb]

ENV HOME=/config
VOLUME /config
VOLUME /run/nfd

ENTRYPOINT ["/usr/local/bin/ndn-python-repo"]
CMD ["-c", "/config/repo.conf"]