import logging
import signal
from threading import Event, Thread

from app.config import get_settings
from app.worker.consumer import consume
from app.worker.factory import build_runner

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def main() -> None:
    settings = get_settings()
    runner = build_runner(settings)

    stop = Event()
    for signal_number in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signal_number, lambda *_: stop.set())

    consumer_thread = Thread(target=consume, args=(settings, stop), name="kafka-consumer")
    consumer_thread.start()
    runner.run(stop)
    consumer_thread.join()


if __name__ == "__main__":
    main()
