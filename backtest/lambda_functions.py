
__author__ = "Nathan Ward"

import logging
import socket
import redis
from redis_manager import Redis

_LOGGER = logging.getLogger()
_LOGGER.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Placeholder.
    """
    print('loading library')
    meow = Redis()
    print('library loaded')
    #redis_hostname = meow.get_backtest_redis_endpoint()
    print(socket.getaddrinfo('backteststorage.9rdaay.0001.use2.cache.amazonaws.com', 6379))
    redis_hostname = '10.0.1.237'
    print('Found redis hostname: {0}'.format(redis_hostname))
    r = redis.Redis(host=redis_hostname, port=6379, db=0, decode_responses=True)
    print('test2')
    print(r.ping())
    print('test3')
    return