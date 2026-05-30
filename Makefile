.PHONY: game server nats spectate admin tests tests-nats venv

game:
	python game.py

server:
	python server.py $(filter-out $@,$(MAKECMDGOALS))

nats:
	nats-server -a 127.0.0.1

spectate:
	python game.py --spectate

admin:
	python admin.py $(filter-out $@,$(MAKECMDGOALS))

tests:
	pytest tests/ -v --ignore=tests/test_nats_integration.py

tests-nats:
	pytest tests/test_nats_integration.py -v

venv:
	python -m venv .venv
	.venv/bin/pip install -r requirements.txt

%:
	@:
