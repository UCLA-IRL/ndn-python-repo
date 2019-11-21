test:
	pytest tests

venv:
	python3 -m venv venv
	python3 -m pip install -r requirements.txt

install:
	ln -sf $(CURDIR)/ndn-repo.service /etc/systemd/system/ndn-repo.service
	ln -sf $(CURDIR)/_config.yaml /usr/local/etc/ndn/ndn-repo.conf
	ln -sf $(CURDIR)/main.py /usr/local/bin/ndn-repo