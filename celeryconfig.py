
__author__ = "Nathan Ward"

"""
Celery configuration.
"""

import socket
import ujson
from kombu.serialization import kombu_register

#Set ujson as the default celery serializer for speed.
kombu_register(
    'ujson',
    ujson.dumps,
    ujson.loads,
    content_type='application/x-ujson',
    content_encoding='utf-8'
)

#Tell celery to use ujson serializer.
CELERY_ACCEPT_CONTENT = ['ujson']
CELERY_TASK_SERIALIZER = 'ujson'
CELERY_RESULT_SERIALIZER = 'ujson'
