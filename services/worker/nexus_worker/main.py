"""
NEXUS Background Worker Service
Processes asynchronous DAG steps, long-running agent tasks, and knowledge indexing.
"""

import asyncio
import signal
import sys

from packages.config.nexus_config import get_settings
from packages.shared.nexus_shared.logging import configure_logging, get_logger

logger = get_logger("nexus.worker")


class NexusWorker:
    def __init__(self):
        self.settings = get_settings()
        self.running = False
        self._shutdown_event = asyncio.Event()

    async def start(self):
        configure_logging(
            log_level=self.settings.log_level,
            json_format=(self.settings.nexus_env == "production"),
        )
        self.running = True
        logger.info("nexus_worker_started", env=self.settings.nexus_env)

        # Loop processing background tasks / heartbeats
        try:
            while self.running:
                logger.debug("worker_heartbeat", queue="default", status="idle")
                # Wait 10 seconds or until shutdown signaled
                try:
                    await asyncio.wait_for(self._shutdown_event.wait(), timeout=10.0)
                except TimeoutError:
                    pass

                if self._shutdown_event.is_set():
                    break
        except asyncio.CancelledError:
            logger.info("worker_task_cancelled")
        finally:
            await self.shutdown()

    async def shutdown(self):
        logger.info("nexus_worker_shutting_down")
        self.running = False


async def main():
    worker = NexusWorker()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: worker._shutdown_event.set())
        except NotImplementedError:
            # Signal handlers not implemented on some platforms/threads
            pass

    await worker.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)
