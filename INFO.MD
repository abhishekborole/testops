Run Backend
.venv\Scripts\python -m uvicorn app.main:app --reload --reload-exclude ".venv" --reload-exclude "alembic"

Run Frontend
npm run dev

Start Kafka
bin\windows\kafka-server-start.bat config\kraft\server.properties

Kafka Consumer
bin\windows\kafka-console-consumer.bat --topic testops-topic --from-beginning --bootstrap-server localhost:9092
