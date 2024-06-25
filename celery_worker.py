
__author__ = "Nathan Ward"

"""
Celery application.
"""

from os import environ
from celery import Celery

app = Celery(
    'celery_worker',
    #Redis broker/queue.
    broker='redis://{0}:6379/0'.format(environ['REDIS_ENDPOINT']),
    #Redis backend for task result info.
    backend='redis://{0}:6379/0'.format(environ['REDIS_ENDPOINT']),
    #Modules to pre-import so the worker can be ready.
    include=[
        'backtest.engine',
        'startup',
        'backtest.reaper'
    ]
)

if __name__ == '__main__':
    app.start()