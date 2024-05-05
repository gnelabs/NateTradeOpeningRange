
__author__ = "Nathan Ward"

import logging
from sys import stdout
from collections import defaultdict
from statistics import fmean

_LOGGER = logging.getLogger()
_LOGGER.setLevel(logging.INFO)


class ProcessOpeningRanges(object):
    def __init__(self):
        #Adjustable stop distance for trading.
        self.stop_distance = 0.25

        #Adjustable count of times stop loss is hit.
        self.stop_count_limit = 4

        #Adjustable cooloff period in seconds between the stop getting hit before the next trade can commence.
        self.stop_cooloff_period = 30

        #Adjustable take profit distance.
        self.limit_distance = 5
    
    def compress_time_series(self, agg_data_raw:dict) -> dict:
        """
        Take raw intra-second time series data from the database and compress it by 
        removing duplicates and sort it by price. Although the raw data is more 
        visually appearing because it can be charted, it is not optimized for minimal 
        processing iterations. This takes data that looks like:

        {'2023-04-24': [
                {'timestamp_utc': 1682343030, 'underlying': 411.99},
                {'timestamp_utc': 1682343030, 'underlying': 411.99},
                {'timestamp_utc': 1682343031, 'underlying': 411.99},
                {'timestamp_utc': 1682343032, 'underlying': 411.98},
            ]
        }

        To this:

        {'2023-04-24': {
                1682343030: 411.99,
                1682343032: 411.98
            }
        }
        """
        last_timestamp = 0
        last_price_entered = 0
        compressed_data = defaultdict(dict)

        for k_date, v_intraday_data_raw in agg_data_raw.items():
            for item in v_intraday_data_raw:
                if not last_timestamp:
                    last_timestamp = item['timestamp_utc']
                    last_price_entered = item['underlying']
                    compressed_data[k_date][item['timestamp_utc']] = item['underlying']
                else:
                    #These are ints, so increment by at least one second.
                    if item['timestamp_utc'] >= last_timestamp:
                        if item['underlying'] != last_price_entered:
                            compressed_data[k_date][item['timestamp_utc']] = item['underlying']
                            last_price_entered = item['underlying']
                            last_timestamp = item['timestamp_utc']
        
        return compressed_data

    def backtest_redux(self, opening_range_info:dict, compressed_agg_data:dict) -> dict:
        """
        Using opening range information and intraday price data, perform a backtest.

        Redux: Re-wrote this logic to make it clearer.
        """
        #Per-trade information. Things like holding period, p&l, cost basis.
        trade_stats = defaultdict(dict)

        #Holding object for stop price.
        stop_price = 0

        #Holding object for limit price.
        limit_price = 0

        #Count of how many times the stop was hit.
        stop_triggered_count = 0

        #Count of times trade has initiated.
        trade_initiated_count = 0

        #Stop cooloff timestamp, used to time the cooloff period.
        stop_cooloff_timestamp = 0

        #Indicate if there is an active position on or not.
        active_position_long = False
        active_position_short = False

        #Opening range information.
        range_high = opening_range_info['high']
        range_low = opening_range_info['low']
        day_open_price = opening_range_info['open_price']

        #End of the trading day.
        end_of_trading_day_timestamp = list(compressed_agg_data.keys())[-1]

        for k_timestamp, v_price in compressed_agg_data.items():
            #Check to see if the stop has reached the risk limit.
            #Skip further processing for the day if that is the case.
            if stop_triggered_count == self.stop_count_limit:
                break

            #Check to see if the stop was hit last iteration and needs to cool off.
            #If the cooldown period is active, skip processing this timestamp.
            if k_timestamp < stop_cooloff_timestamp:
                continue

            #No position, check ranges.
            if not active_position_long and not active_position_short:
                #Bullish breakout above the opening range.
                if v_price > range_high:
                    active_position_long = True
                    stop_price = v_price - self.stop_distance
                    limit_price = v_price + self.limit_distance
                    trade_initiated_count += 1
                    trade_stats[trade_initiated_count] = {
                        'trade_open_price': v_price,
                        'timestamp_opened': k_timestamp,
                        'direction': 'long'
                    }
                #Bearish breakdown below the opening range.
                elif v_price < range_low:
                    active_position_short = True
                    stop_price = v_price + self.stop_distance
                    limit_price = v_price - self.limit_distance
                    trade_initiated_count += 1
                    trade_stats[trade_initiated_count] = {
                        'trade_open_price': v_price,
                        'timestamp_opened': k_timestamp,
                        'direction': 'short'
                    }
            #There is an active position.
            else:
                if active_position_long:
                    if v_price >= limit_price or k_timestamp == end_of_trading_day_timestamp:
                        #Reached the limit or end of day, take profit and close the position.
                        trade_stats[trade_initiated_count].update({
                            'trade_close_price': v_price,
                            'profit': v_price - trade_stats[trade_initiated_count]['trade_open_price'],
                            'holding_period': k_timestamp - trade_stats[trade_initiated_count]['timestamp_opened'],
                            'timestamp_closed': k_timestamp
                        })
                        #Since this is a trend following strategy, once profit has been achieved, no 
                        #further trading for the day.
                        break
                    elif v_price <= stop_price:
                        #Stopped out, take the loss and start a cooldown period.
                        stop_cooloff_timestamp = k_timestamp + self.stop_cooloff_period
                        stop_triggered_count += 1
                        trade_stats[trade_initiated_count].update({
                            'trade_close_price': v_price,
                            'profit': v_price - trade_stats[trade_initiated_count]['trade_open_price'],
                            'holding_period': k_timestamp - trade_stats[trade_initiated_count]['timestamp_opened'],
                            'timestamp_closed': k_timestamp
                        })
                        stop_price = 0
                        limit_price = 0
                        active_position_long = False
                elif active_position_short:
                    if v_price <= limit_price or k_timestamp == end_of_trading_day_timestamp:
                        #Reached the limit or end of the day, take profit and close the position.
                        trade_stats[trade_initiated_count].update({
                            'trade_close_price': v_price,
                            'profit':  v_price - trade_stats[trade_initiated_count]['trade_open_price'],
                            'holding_period': k_timestamp - trade_stats[trade_initiated_count]['timestamp_opened'],
                            'timestamp_closed': k_timestamp
                        })
                        #Since this is a trend following strategy, once profit has been achieved, no 
                        #further trading for the day.
                        break
                    elif v_price >= stop_price:
                        #Stopped out, take the loss and start a cooldown period.
                        stop_cooloff_timestamp = k_timestamp + self.stop_cooloff_period
                        stop_triggered_count += 1
                        trade_stats[trade_initiated_count].update({
                            'trade_close_price': v_price,
                            'profit': trade_stats[trade_initiated_count]['trade_open_price'] - v_price,
                            'holding_period': k_timestamp - trade_stats[trade_initiated_count]['timestamp_opened'],
                            'timestamp_closed': k_timestamp
                        })
                        stop_price = 0
                        limit_price = 0
                        active_position_short = False

        return {
            'stops_triggered': stop_triggered_count,
            'trades_triggered': trade_initiated_count,
            'average_holding_period': fmean(k['holding_period'] for k in trade_stats.values()),
            'net_profit': sum(k['profit'] for k in trade_stats.values()),
            'trade_stats': trade_stats
        }
