
__author__ = "Nathan Ward"

import logging
import redis
from redis_manager import Redis

_LOGGER = logging.getLogger()
_LOGGER.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Placeholder.
    """
    meow = Redis()
    redis_hostname = meow.get_backtest_redis_endpoint()
    _LOGGER.info('Found redis hostname: {0}'.format(redis_hostname))
    r = redis.Redis(host=redis_hostname, port=6379, db=0, decode_responses=True)
    _LOGGER.info('test2')
    r.ping()
    return