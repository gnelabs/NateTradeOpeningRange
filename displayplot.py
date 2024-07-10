
__author__ = "Nathan Ward"

"""
Module to help render a simple plot based on the backtest result.
"""

from os import environ
import mysql.connector
from mysql.connector import Error
import ujson
import plotly.express as px
import pandas as pd


class SQLError(Exception):
    """Exception class if there is a problem talking to the SQL DB."""
    pass


def pull_data(backtest_id: str, table_name: str) -> dict:
    try:
        sql_user = environ['DB_USERNAME']
        sql_pw = environ['DB_PASSWORD']
        sql_endpoint = environ['DB_ENDPOINT']
        sql_dbname = environ['DB_NAME']
        sql_tablename = environ['DB_TABLE']
    except KeyError:
        raise SQLError('Error: Missing database credentials.')

    QUERY = """
    SELECT trade_stats
    FROM results.{table}
    WHERE backtest_id = '{backtest}';
    """.format(
        table = table_name,
        backtest = backtest_id
    )

    result = []

    try:
        cnx = mysql.connector.connect(user=sql_user, password=sql_pw, host=sql_endpoint, database=sql_dbname)
        
        if cnx.is_connected():
            cursor = cnx.cursor()
            cursor.execute(QUERY)
            result = cursor.fetchall()
            print('Found {0} results in DB.'.format(len(result)))
    except Error as e:
        _LOGGER.exception('Problem getting backtest result data from SQL. {0}'.format(e))
    finally:
        if cnx.is_connected():
            cnx.close()
    
    if result:
        sql_data = ujson.loads(result[0][0])
        return sql_data
    else:
        return {}

def display(backtest_id: str, table_name: str):
    result = pull_data(backtest_id=backtest_id, table_name=table_name)
    if result:
        columns = ['date', 'stock_price_change', 'cumulative_profit']
        data = []
        cumulative_profit = []
        cumlative_stock_price_change = []
        last_price = 0

        for k, v in result.items():
            cumulative_profit.append(v['snp'])

            if not last_price:
                last_price = v['1']['top']
                cumlative_stock_price_change.append(v['1']['top'] - last_price)
                data.append((k, sum(cumlative_stock_price_change), sum(cumulative_profit)))
            else:
                cumlative_stock_price_change.append(v['1']['top'] - last_price)
                data.append((k, sum(cumlative_stock_price_change), sum(cumulative_profit)))
                last_price = v['1']['top']

        df = pd.DataFrame(data, columns=columns)


        fig = px.line(
            df,
            x = 'date',
            y = df.columns,
            hover_data = {'date': '|%B %d, %Y'},
            title = 'Backtest {0} results'.format(backtest_id)
        )

        fig.update_xaxes(
            dtick = 'M1',
            tickformat = '%b\n%Y',
            rangeslider_visible = True
        )

        fig.show()

    return