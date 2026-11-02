import json
import logging
from threading import Event

from confluent_kafka import Consumer, Message, TopicPartition

from app.config import Settings
from app.db import queries
from app.db.clock import utcnow
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

POLL_SECONDS = 1.0
RETRY_SECONDS = 5.0


def handle_message(payload: bytes) -> None:
    try:
        event = json.loads(payload)
        event_id, test_id = event["eventId"], event["testId"]
    except (ValueError, KeyError, TypeError):
        logger.warning("Ignoring malformed attempt event")
        return

    with SessionLocal() as db:
        if queries.mark_event_processed(db, event_id):
            queries.enqueue_test(db, test_id, utcnow().date())
        db.commit()


def consume(settings: Settings, stop: Event) -> None:
    consumer = Consumer(
        {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "group.id": settings.kafka_group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )
    consumer.subscribe([settings.kafka_topic])
    try:
        while not stop.is_set():
            message = consumer.poll(POLL_SECONDS)
            if message is None:
                continue
            if message.error():
                logger.warning("Kafka error: %s", message.error())
                continue
            _process(consumer, message, stop)
    finally:
        consumer.close()


def _process(consumer: Consumer, message: Message, stop: Event) -> None:
    try:
        handle_message(message.value())
        consumer.commit(message=message, asynchronous=False)
    except Exception:
        logger.exception("Could not process attempt event; retrying")
        consumer.seek(TopicPartition(message.topic(), message.partition(), message.offset()))
        stop.wait(RETRY_SECONDS)
