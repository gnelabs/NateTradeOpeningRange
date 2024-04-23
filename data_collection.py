
__author__ = "Nathan Ward"

from collections import defaultdict
from datetime import datetime, timezone
from dw.natetrade_database import DatabaseHelper


class CollectOpeningRanges(object):
    def __init__(self):
        #There isn't any high resolution data in the DB before this point.
        self.high_resolution_beginning_date_epoch = 1682343000

        #30 seconds for the strategy
        self.opening_range_duration = 30

        self.helper = DatabaseHelper()

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
                open_end = epoch_time + 30
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

        data = self.helper.generic_select_query('options', query)

        return data
    
    def organize_data(self, range_data:list) -> dict:
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
