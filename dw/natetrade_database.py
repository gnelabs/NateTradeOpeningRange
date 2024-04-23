
__author__ = "Nathan Ward"

import logging
from sys import stdout
from os import environ
from time import time
import mysql.connector
from mysql.connector import Error

_LOGGER = logging.getLogger()
_LOGGER.setLevel(logging.INFO)

#Local logging to stdout.
#Comment this out if using in production with a built-in logger.
handler = logging.StreamHandler(stdout)
_LOGGER.addHandler(handler)


class InitizliationError(Exception):
    """Exception class if the class cannot be initialized."""
    pass


class SQLError(Exception):
    """Exception class if there is a problem talking to the SQL DB."""
    pass


class StrictSchemaError(Exception):
    """Exception class if data passed does match the schema."""
    pass


class DatabaseHelper(object):
    def __init__(self):
        required_env_vars = (
            'SQL_USERNAME',
            'SQL_PASSWORD',
            'SQL_HOSTNAME'
        )
        
        for var in required_env_vars:
            if var not in environ:
                raise InitizliationError('Missing environment variables configured in env.list.')
        
        self.sql_user = environ['SQL_USERNAME']
        self.sql_pw = environ['SQL_PASSWORD']
        self.sql_endpoint = environ['SQL_HOSTNAME']
    
    def generic_select_query(self, db: str, query_string: str) -> list:
        """
        Function to execute a select query. Returns a list of dicts.
        """
        try:
            cnx = mysql.connector.connect(
                user = self.sql_user,
                password = self.sql_pw,
                host = self.sql_endpoint,
                database = db
            )
        except Error as e:
            _LOGGER.exception('Problem accessing natetrade SQL database. {0}'.format(e))
            raise SQLError('Problem accessing natetrade SQL database. {0}'.format(e))
        
        try:
            if cnx.is_connected():
                cursor = cnx.cursor(dictionary=True)
                
                start_time = time()
                
                cursor.execute(query_string)
                result = cursor.fetchall()
                
                end_time = time()
                execution_time = round((end_time - start_time), 3)
                
                _LOGGER.info('Returned {0} rows of data in {1} seconds.'.format(len(result), execution_time))
                
                return result
        except Error as e:
            _LOGGER.exception('Problem getting greek data. {0}'.format(e))
            raise SQLError('Problem getting greek data. {0}'.format(e))
        finally:
            if cnx.is_connected():
                cursor.close()
                cnx.close()

