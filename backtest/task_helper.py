
__author__ = "Nathan Ward"

"""
Helpers to access low level implimentation of celery send task.
"""

import logging
import os
import socket
from uuid import uuid4
from typing import Dict, List, Optional
import ujson
from pybase64 import b64encode
import redis


_LOGGER = logging.getLogger()
_LOGGER.setLevel(logging.INFO)


async def send_task(
    queue: str,
    task_name: str,
    task_args: Optional[List] = None,
    task_kwargs: Optional[Dict] = None,
) -> None:
    """
    Low level helper to inject new tasks into celery by directly talking to Redis.
    This allows increased task injection performance by mimicking the message
    format.
    """
    r = redis.asyncio.from_url("redis://localhost:6379", db=0, decode_responses=True)

    if not task_args:
        task_args = []
    
    if not task_kwargs:
        task_kwargs = {}
    
    task_id = str(uuid4())
    delivery_tag = str(uuid4())
    reply_to_id = str(uuid4())
    body = b64encode(ujson.dumps((task_args, task_kwargs, {})).encode("utf-8")).decode("utf-8")

    #Message format for celery 5.4.0.
    message = {
        "body": body,
        "content-encoding": "utf-8",
        "content-type": "application/json",
        "headers": {
            "lang": "py",
            "task": task_name,
            "id": task_id,
            "shadow": None,
            "eta": None,
            "expires": None,
            "group": None,
            "group_index": None,
            "retries": 0,
            "timelimit": [None, None],
            "root_id": task_id,
            "parent_id": None,
            "argsrepr": repr(task_args),
            "kwargsrepr": repr(task_kwargs),
            "origin": f"{os.getpid()}@{socket.gethostname()}",
            "ignore_result": False,
            "replaced_task_nesting": 0,
            "stamped_headers": None,
            "stamps": {}
        },
        "properties": {
            "correlation_id": task_id,
            "reply_to": reply_to_id,
            "delivery_mode": 2,  # persistent
            "delivery_info": {"exchange": "", "routing_key": queue},
            "priority": 0,
            "body_encoding": "base64",
            "delivery_tag": delivery_tag,
        },
    }

    try:
        await r.lpush(queue, ujson.dumps(message))
    except Exception as e:
        _LOGGER.exception(f"action=send_task, status=fail, {e}")