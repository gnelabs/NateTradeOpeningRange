
__author__ = "Nathan Ward"

import logging
from statistics import fmean
from collections import defaultdict
from datetime import datetime, timezone
import numpy as np
from dw.natetrade_database import DatabaseHelper

_LOGGER = logging.getLogger()
_LOGGER.setLevel(logging.INFO)

HELPER = DatabaseHelper()


class CollectOpeningRanges(object):
    def __init__(self):
        #There isn't any high resolution data in the DB before this point.
        self.high_resolution_beginning_date_epoch = 1682343000

        #30 seconds for the strategy
        self.opening_range_duration = 30

        #Markets are usually open for normal hours, at least, assume that is the case.
        self.market_open_duration = 23400

    def epoch_date_ranges(self) -> list:
        """
        Generate a list of ranges in epoch time to pass into the SQL.

        Some of the dates will be weekends or market holidays, but these 
        will return no data from the DB as a workaround.
        """
        current_time_epoch = int(datetime.now(timezone.utc).timestamp())
        epoch_range = []

        #Skip the first one since this is included in the SQL already.
        for i in range(self.high_resolution_beginning_date_epoch + 86400, current_time_epoch, 86400):
            epoch_range.append(i)
        
        return epoch_range
    
    def get_opening_range_data(self, range_data:list) -> list:
        """
        Queries the database to get a dictionary of 30 second opening range
        data for all securities.

        Should grab about ~3500 rows per day, runs quickly. Returns data in order from oldest to newest.
        Returns data like: [{'timestamp_utc': 1684503026, 'ticker': 'MSFT', 'underlying': 316.88}]
        """
        #Build the SQL syntax using the date ranges
        statement = ''
        for epoch_time in range_data:
            statement += 'OR timestamp_utc BETWEEN {open_start} AND {open_end} '.format(
                open_start = epoch_time,
                open_end = epoch_time + self.opening_range_duration
            )
        
        query = """
        SELECT timestamp_utc, ticker, underlying
        FROM `options`.`greeks`
        WHERE timestamp_utc BETWEEN {initial_open} AND {initial_end} {statement};
        """.format(
            initial_open = self.high_resolution_beginning_date_epoch,
            initial_end = self.high_resolution_beginning_date_epoch + 30,
            statement = statement
        )

        data = HELPER.generic_select_query('options', query)

        return data
    
    def organize_opening_range_data(self, range_data:list) -> dict:
        """
        Cleans up the data from the database based on the security, and gives the 
        opening range information.
        """
        organized_data = defaultdict(dict)

        #First pass, populate tickers and initial data structure.
        for row in range_data:
            if row['ticker'] not in organized_data:
                organized_data[row['ticker']] = {datetime.fromtimestamp(row['timestamp_utc']).strftime('%Y-%m-%d'): defaultdict(int)}
        
        #Second pass, populate dates and the rest of the data.
        for row in range_data:
            date = datetime.fromtimestamp(row['timestamp_utc']).strftime('%Y-%m-%d')
            if date not in organized_data[row['ticker']]:
                organized_data[row['ticker']][date] = {
                    'open_price': row['underlying'],
                    'high': row['underlying'],
                    'low': row['underlying'],
                    'count_trades': 1,
                    'trading_start': row['timestamp_utc']
                }
            else:
                organized_data[row['ticker']][date]['count_trades'] += 1

                if row['underlying'] > organized_data[row['ticker']][date]['high']:
                    organized_data[row['ticker']][date]['high'] = row['underlying']
                
                if row['underlying'] < organized_data[row['ticker']][date]['low']:
                    organized_data[row['ticker']][date]['low'] = row['underlying']
                
                if row['timestamp_utc'] > organized_data[row['ticker']][date]['trading_start']:
                    organized_data[row['ticker']][date]['trading_start'] = row['timestamp_utc']

        return organized_data
    
    def pull_intraday_market_data(self, starting_epoch_range:int, ticker:str) -> list:
        """
        Query the DB for intraday price data within the range.

        Should take about ~2 seconds on average per query, returning a max of 70k rows.
        """
        query = """
        SELECT DISTINCT timestamp_utc, underlying
        FROM `options`.`greeks`
        WHERE timestamp_utc BETWEEN {open_range} AND {closing_range}
        AND ticker = '{ticker}'
        """.format(
            open_range = starting_epoch_range,
            closing_range = starting_epoch_range + self.market_open_duration,
            ticker = ticker
        )

        data = HELPER.generic_select_query('options', query)

        return data


class StatsAdHoc(object):
    def __init__(self):
        pass

    def query_correlation(self, ticker:str) -> list:
        """
        Query correlation to SPY.
        """
        query = """
        SELECT ticker, date, close_price
        FROM stocks.daily_underlying
        WHERE ticker IN ('SPY', '{ticker}')
        ;
        """.format(
            ticker = ticker
        )

        data = HELPER.generic_select_query('stocks', query)

        return data
    
    def process_correlation(self, raw_price_data:list) -> float:
        """
        Calculate long term correlation to the SP500.
        """
        spy_returns = []
        comparison_returns = []
        match_timeseries = {}

        #First pass, get SPY dates to match i.e. inner join
        for row in raw_price_data:
            if row['ticker'] == 'SPY':
                match_timeseries[str(row['date'])] = row['close_price']
        
        #Second pass, combine
        for row in raw_price_data:
            if row['ticker'] != 'SPY':
                #Ignore dates where this is mismatched information.
                if str(row['date']) in match_timeseries:
                    spy_returns.append(match_timeseries[str(row['date'])])
                    comparison_returns.append(row['close_price'])
        
        try:
            return np.corrcoef(comparison_returns, spy_returns)[0][1]
        except IndexError:
            return 0