
__author__ = "Nathan Ward"

"""
Functionality to start the backtesting system.
"""

import logging
from frange import frange
from celery_worker import app

_LOGGER = logging.getLogger()
_LOGGER.setLevel(logging.INFO)


@app.task(bind=True)
def create_processing_jobs(
    self,
    range_start: float,
    range_end: float,
    range_increment: float,
    range_id: str,
    fixed_settings: dict
) -> None:
    """
    Batch create processing tasks based on a single range to limit the batch size.

    Directly calls the backtest engine.
    """
    for item in frange(range_start, range_end, range_increment):
        fixed_settings[range_id] = round(item, 2)
        res = app.send_task(
            'backtest.engine.backtest_redux',
            kwargs = fixed_settings,
            queue='worker_main'
        )

    return

