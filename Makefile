.PHONY: venv test wheels deb install-user clean

VENV := .venv
PY := $(VENV)/bin/python

venv:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --quiet -e .[dev]

test: venv
	$(VENV)/bin/pytest -q

wheels:
	python3 -m pip wheel . -w dist/wheels --quiet

deb:
	packaging/deb/build-deb.sh

install-user:
	packaging/install.sh

clean:
	rm -rf $(VENV) dist build src/*.egg-info .pytest_cache
	find . -name __pycache__ -type d -exec rm -rf {} +
