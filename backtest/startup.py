
__author__ = "Nathan Ward"

"""
Functionality to start the backtesting system.
"""

import logging
from os import environ
import redis
from frange import frange
from backtest.task_helper import send_task

_LOGGER = logging.getLogger()
_LOGGER.setLevel(logging.INFO)


def seed_backtest_requests():
    task_args = []

    for limit in frange(1, 20):
        for stopiteration in frange(1, 4):
            for cooloff in frange(30, 300, 30):
                for stop_distance in frange(0.1, 2, 0.1):
                    task_args.append([limit, stopiteration, cooloff, stop_distance])

    print('Sending {0} backtest tasks to be processed.'.format(len(task_args)))

    count = 0
    r = redis.Redis(host=environ['REDIS_ENDPOINT'], port=6379, db=0, decode_responses=True)

    #https://redis-py.readthedocs.io/en/stable/advanced_features.html#default-pipelines
    with r.pipeline() as pipe:
        for item in task_args:
            count += 1
            message_to_send = send_task(
                queue = 'worker_main',
                task_name = 'backtest.engine.backtest_redux',
                task_kwargs = {
                    'stop_distance': item[3],
                    'stop_count_limit': item[1],
                    'stop_cooloff_period': item[2],
                    'limit_distance': item[0],
                }
            )
            pipe.lpush('worker_main', message_to_send)

            #Limit pipeline batches to 1000 to reduce risk of deadlock.
            if count % 1000 == 0:
                print('sent {0} tasks to redis'.format(count))
                pipe.execute()