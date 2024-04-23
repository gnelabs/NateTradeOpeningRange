
__author__ = "Nathan Ward"

import logging
from statistics import fmean
from collections import defaultdict
from datetime import datetime, timezone
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


class ProcessOpeningRanges(object):
    def __init__(self):
        #Markets are usually open for normal hours, at least, assume that is the case.
        self.market_open_duration = 23400

        #Adjustable stop distance for trading. To-do: Research this
        self.stop_distance = 0.25

        #Adjustable count of times stop loss is hit. To-do: Research this
        self.stop_count_limit = 4

        #adjustable cooloff period in seconds between the stop getting hit before the next trade can commence.
        self.stop_cooloff_period = 30

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
    
    def backtest(self, open_price:float, range_high:float, range_low:float, intraday_data:list) -> dict:
        """
        Using intraday data collected for each day, perform analysis based on breakouts from the
        opening range as provided.
        """
        #First level, distance between opening and range high
        level_one_profit_bullish = range_high - open_price
        level_one_profit_bearish = open_price - range_low

        #Second level, distance between range low and range high
        level_two_profit = range_high - range_low

        #Third level, overfit to recreate a profit level that is positively expectant
        level_three_profit = 5

        #Keep track of how long the holding period is in seconds for each trade to do risk analysis.
        holding_period = []

        #Keep track of the profit for each trade.
        trade_tracker = []

        #Holding object for stop price.
        stop_price = 0

        #Holding object for limit price.
        limit_price = 0

        #To simplify logic, indicate is trade is long or short.
        trade_is_long = False

        #Count of how many times the stop was hit.
        stop_triggered_count = 0

        #Stop cooloff timestamp, used to time the cooloff period.
        stop_cooloff_timestamp = 0

        for data in intraday_data:
            #Check to see if the stop has reached the risk limit.
            if stop_triggered_count == self.stop_count_limit:
                break
            
            #Check to see if the stop was hit last iteration and needs to cool off.
            if data['timestamp_utc'] < stop_cooloff_timestamp:
                continue

            #stop_price being falsy indicates no active trade, so trigger one.
            if not stop_price:
                #Bullish breakout above the opening range.
                if data['underlying'] > range_high:
                    trade_tracker.append(data['underlying'])
                    holding_period.append(data['timestamp_utc'])
                    trade_is_long = True
                    stop_price = data['underlying'] - self.stop_distance
                    limit_price = data['underlying'] + level_three_profit
                #Bearish breakout below the opening range.
                elif data['underlying'] < range_low:
                    trade_tracker.append(data['underlying'])
                    holding_period.append(data['timestamp_utc'])
                    trade_is_long = False
                    stop_price = data['underlying'] + self.stop_distance
                    limit_price = data['underlying'] - level_three_profit
            else:
                #Bullish breakout logic
                if trade_is_long:
                    #Profit taken
                    if data['underlying'] > limit_price or data == intraday_data[-1]:
                        trade_tracker[-1] = limit_price - trade_tracker[-1]
                        holding_period[-1] = data['timestamp_utc'] - holding_period[-1]
                        stop_price = 0
                        limit_price = 0
                        break
                    #Stop hit on the downside
                    elif data['underlying'] < stop_price:
                        trade_tracker[-1] = stop_price - trade_tracker[-1]
                        holding_period[-1] = data['timestamp_utc'] - holding_period[-1]
                        stop_price = 0
                        limit_price = 0
                        stop_triggered_count += 1
                        stop_cooloff_timestamp = data['timestamp_utc'] + self.stop_cooloff_period
                #Bearish breakout logic
                else:
                    #Profit taken
                    if data['underlying'] < limit_price or data == intraday_data[-1]:
                        trade_tracker[-1] = trade_tracker[-1] - limit_price
                        holding_period[-1] = data['timestamp_utc'] - holding_period[-1]
                        stop_price = 0
                        limit_price = 0
                        break
                    #Stop hit on the upside
                    elif data['underlying'] > stop_price:
                        trade_tracker[-1] = trade_tracker[-1] - stop_price
                        holding_period[-1] = data['timestamp_utc'] - holding_period[-1]
                        stop_price = 0
                        limit_price = 0
                        stop_triggered_count += 1
                        stop_cooloff_timestamp = data['timestamp_utc'] + self.stop_cooloff_period
                    
        
        return {
            'count_stops_triggered': stop_triggered_count,
            'count_trades_triggered': len(trade_tracker),
            'holding_period_data': holding_period,
            'average_holding_period_per_trade': fmean(holding_period),
            'trade_tracker': trade_tracker,
            'net_profit': sum(trade_tracker)
        }
