.PHONY: start stop logs reset-whatsapp

PROJECT_NAME = newspapershub

start:
	@echo "Starting NewsPapersHub..."
	docker compose up -d --build
	@echo "Run 'make logs' to view the WhatsApp QR code if you are not logged in."

stop:
	@echo "Stopping NewsPapersHub..."
	docker compose down

logs:
	@echo "Attaching to logs... (Press Ctrl+C to exit)"
	docker compose logs -f newspapershub

# The docker compose project name defaults to the folder name (newspapershub)
reset-whatsapp:
	@echo "Resetting WhatsApp Connection..."
	docker compose down
	rm -f db/neonize_session.sqlite3
	@echo "Old session deleted. Restarting to generate a new QR code..."
	docker compose up -d
	@echo ">>> RUN 'make logs' NOW TO SCAN YOUR NEW QR CODE <<<"
