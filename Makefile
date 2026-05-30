.PHONY: game server nats

game:
	python game.py

server:
	python server.py

nats:
	nats-server
