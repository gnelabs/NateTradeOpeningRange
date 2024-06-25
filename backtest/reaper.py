
__author__ = "Nathan Ward"

"""
Reaper to lifecycle result data out of Redis and into SQL.


"""

import logging
from os import environ
from io import StringIO
from time import time
import mysql.connector
from mysql.connector import Error
import redis
import ujson
from celery_worker import app

_LOGGER = logging.getLogger()
_LOGGER.setLevel(logging.INFO)


class SQLError(Exception):
    """Exception class if there is a problem talking to the SQL DB."""
    pass


def batch(iterable, n=1):
    """Simpler list batcher."""
    l = len(iterable)
    for ndx in range(0, l, n):
        yield iterable[ndx:min(ndx + n, l)]


@app.task(bind=True)
def lifecycle_result_data(self) -> None:
    """
    Regularly scan Redis for task worker result data, and
    lifecycle that data to MySQL.
    """
    start_time = time()

    try:
        sql_user = environ['DB_USERNAME']
        sql_pw = environ['DB_PASSWORD']
        sql_endpoint = environ['DB_ENDPOINT']
        sql_dbname = environ['DB_NAME']
        sql_tablename = environ['DB_TABLE']
    except KeyError:
        _LOGGER.exception('Error: Missing database credentials.')
        raise SQLError('Error: Missing database credentials.')

    r = redis.Redis(
        host = environ['REDIS_ENDPOINT'],
        port = 6379,
        db = 0,
        decode_responses=True
    )

    #Iterate through available keys, load them into memory.
    matching_keys = []
    celery_task_ids_to_delete = []
    results = {}

    #Only dig up completed task ids, using non-blocking search.
    for key_task_id in r.scan_iter('celery-task-meta-*'):
        matching_keys.append(key_task_id)

    #Bulk get keys and filter.
    for key_task_id in r.mget(matching_keys):
        data = ujson.loads(key_task_id)
        if data['status'] == 'SUCCESS':
            if 'net_profit' in data['result']:
                results[data['task_id']] = data['result']
                celery_task_ids_to_delete.append(''.join(['celery-task-meta-', data['task_id']]))

    #Limit batch size for DB performance.
    batch_size = 5000

    sql_converted_data = []

    #Convert data in preperation for upload.
    for result_key, result_data in results.items():
        #Convert the data types to SQl data types defined in the schema.
        #Makes it easier to do searching and sorting in SQL.
        #VARCHAR, DATETIME, DATE needs to be in double quotes.
        #JSON data type needs to be in single quotes.
        sql_converted_data.append(
            {
                'trade_id': '"{0}"'.format(result_key),
                'stops_triggered': result_data['stops_triggered'],
                'trades_triggered': result_data['trades_triggered'],
                'net_profit': result_data['net_profit'],
                'average_holding_period': result_data['average_holding_period'],
                'trade_stats': "'{0}'".format(ujson.dumps(result_data['trade_stats']))
            }
        )

    try:
        cnx = mysql.connector.connect(
            user = sql_user,
            password = sql_pw,
            host = sql_endpoint,
            database = sql_dbname
        )
        
        for batch_rows in batch(sql_converted_data, batch_size):
            statement = StringIO()
            #Ignore errors, just write.
            statement.write('INSERT IGNORE INTO {0} ('.format(sql_tablename))
            statement.write(','.join([k for k in sql_converted_data[0].keys()]))
            statement.write(') VALUES ')
            
            for index, row in enumerate(batch_rows):
                statement.write('(')
                #For manually prepared statements, need to convert the object to string for stringio.
                statement.write(','.join([str(v) for v in row.values()]))
                
                #Trailing commas cause a syntax error in SQL.
                if index != len(batch_rows) - 1:
                    statement.write('), ')
                else:
                    statement.write(');')
            
            if cnx.is_connected():
                cursor = cnx.cursor()
                cursor.execute(statement.getvalue())
                cnx.commit()
    except Error as e:
        _LOGGER.exception('Problem inserting results data from Redis into SQL. {0}'.format(e))
    finally:
        if cnx.is_connected():
            cnx.close()

    #Clear out any successfully completed tasks from Redis.
    if celery_task_ids_to_delete:
        r.delete(*celery_task_ids_to_delete)

    end_time = time()
    execution_time = round((end_time - start_time), 3)

    return {
        'status': 'SUCCESS',
        'message': 'Reaper successfully lifecycled {0} rows to MySQL.'.format(len(results)),
        'duration': execution_time
    }