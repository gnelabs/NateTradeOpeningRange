
__author__ = "Nathan Ward"

import logging
import string
from random import choice
from os import environ
from sys import stdout
from collections import defaultdict
from statistics import fmean
import redis
import ujson
from celery_worker import app

_LOGGER = logging.getLogger()
_LOGGER.setLevel(logging.INFO)

def compress_time_series(agg_data_raw:dict) -> dict:
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


def key_gen() -> str:
    """
    Generate random strings to represent a unique backtest from a single time series.
    """
    #Good for 900 million unique combinations.
    key_len = 5

    base_str = string.ascii_letters + string.digits

    keylist = [choice(base_str) for i in range(key_len)]
    return (''.join(keylist))


def get_available_dates() -> list:
    """
    Once data is pre-staged in Redis, get a list of available dates to processes.
    """
    available_dates = []

    r = redis.Redis(host=environ['REDIS_ENDPOINT'], port=6379, db=2, decode_responses=True)

    for item in r.scan_iter():
        available_dates.append(item)

    return available_dates


@app.task(bind=True)
def backtest_redux(
    self,
    stop_distance = 0.25,
    stop_count_limit = 4,
    stop_cooloff_period = 30,
    limit_distance = 5
) -> dict:
    """
    Using opening range information and intraday price data, perform a backtest.

    Redux: Re-wrote this logic to make it clearer.
    """
    backtest_stats = defaultdict(dict)

    #Grab keys of available dates in both caches.
    date_list = get_available_dates()

    #Opening ranges staged data.
    r_opening_ranges = redis.Redis(host=environ['REDIS_ENDPOINT'], port=6379, db=1, decode_responses=True)
    opening_range_info = {}
    for count, data in enumerate(r_opening_ranges.mget(date_list)):
        opening_range_info[date_list[count]] = ujson.loads(data)

    #Time series data.
    r_time_series_agg = redis.Redis(host=environ['REDIS_ENDPOINT'], port=6379, db=2, decode_responses=True)
    compressed_agg_data = {}
    for count, data in enumerate(r_time_series_agg.mget(date_list)):
        compressed_agg_data[date_list[count]] = ujson.loads(data)

    for date in date_list:
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
        range_high = opening_range_info[date]['high']
        range_low = opening_range_info[date]['low']
        day_open_price = opening_range_info[date]['open_price']

        #End of the trading day.
        end_of_trading_day_timestamp = int(list(compressed_agg_data[date].keys())[-1])

        #Map key
        #top = trade open price
        #to = timestamp opened
        #d = direction
        #tcp = trade close price
        #p = profit
        #hp = holding period
        #tc = timestamp closed

        for k_timestamp_str, v_price in compressed_agg_data[date].items():
            #JSON keys get converted to strings during transit,
            #convert back to an int correct data type for comparison.
            k_timestamp = int(k_timestamp_str)

            #Check to see if the stop has reached the risk limit.
            #Skip further processing for the day if that is the case.
            if stop_triggered_count == stop_count_limit:
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
                    stop_price = v_price - stop_distance
                    limit_price = v_price + limit_distance
                    trade_initiated_count += 1
                    trade_stats[trade_initiated_count] = {
                        'top': v_price,
                        'to': k_timestamp,
                        'd': 'long'
                    }
                #Bearish breakdown below the opening range.
                elif v_price < range_low:
                    active_position_short = True
                    stop_price = v_price + stop_distance
                    limit_price = v_price - limit_distance
                    trade_initiated_count += 1
                    trade_stats[trade_initiated_count] = {
                        'top': v_price,
                        'to': k_timestamp,
                        'd': 'short'
                    }
            #There is an active position.
            else:
                if active_position_long:
                    if v_price >= limit_price or k_timestamp == end_of_trading_day_timestamp:
                        #Reached the limit or end of day, take profit and close the position.
                        trade_stats[trade_initiated_count].update({
                            'tcp': v_price,
                            'p': v_price - trade_stats[trade_initiated_count]['top'],
                            'hp': k_timestamp - trade_stats[trade_initiated_count]['to'],
                            'tc': k_timestamp
                        })
                        #Since this is a trend following strategy, once profit has been achieved, no 
                        #further trading for the day.
                        break
                    elif v_price <= stop_price:
                        #Stopped out, take the loss and start a cooldown period.
                        stop_cooloff_timestamp = k_timestamp + stop_cooloff_period
                        stop_triggered_count += 1
                        trade_stats[trade_initiated_count].update({
                            'tcp': v_price,
                            'p': v_price - trade_stats[trade_initiated_count]['top'],
                            'hp': k_timestamp - trade_stats[trade_initiated_count]['to'],
                            'tc': k_timestamp
                        })
                        stop_price = 0
                        limit_price = 0
                        active_position_long = False
                elif active_position_short:
                    if v_price <= limit_price or k_timestamp == end_of_trading_day_timestamp:
                        #Reached the limit or end of the day, take profit and close the position.
                        trade_stats[trade_initiated_count].update({
                            'tcp': v_price,
                            'p':  v_price - trade_stats[trade_initiated_count]['top'],
                            'hp': k_timestamp - trade_stats[trade_initiated_count]['to'],
                            'tc': k_timestamp
                        })
                        #Since this is a trend following strategy, once profit has been achieved, no 
                        #further trading for the day.
                        break
                    elif v_price >= stop_price:
                        #Stopped out, take the loss and start a cooldown period.
                        stop_cooloff_timestamp = k_timestamp + stop_cooloff_period
                        stop_triggered_count += 1
                        trade_stats[trade_initiated_count].update({
                            'tcp': v_price,
                            'p': trade_stats[trade_initiated_count]['top'] - v_price,
                            'hp': k_timestamp - trade_stats[trade_initiated_count]['to'],
                            'tc': k_timestamp
                        })
                        stop_price = 0
                        limit_price = 0
                        active_position_short = False

        #Map key
        #st = stops triggered
        #tt = trades triggered
        #ahp = average holding period
        #snp = sum of net profit

        additional_stats = {}
        additional_stats['st'] = stop_triggered_count
        additional_stats['tt'] = trade_initiated_count
        additional_stats['ahp'] = fmean(k['hp'] for k in trade_stats.values())
        additional_stats['snp'] = sum(k['p'] for k in trade_stats.values())

        backtest_stats[date] = trade_stats | additional_stats

    profit_results = []
    holding_period = []
    win_rate = []

    for value in backtest_stats.values():
        profit_results.append(value['snp'])
        if value['snp'] > 0:
            win_rate.append(True)
        else:
            win_rate.append(False)
        holding_period.append(value['ahp'])

    return {
        'backtest_profit': round(sum(profit_results), 2),
        'average_holding_period': fmean(holding_period),
        'win_rate_percent': round((win_rate.count(True) / len(win_rate) * 100)),
        'stop_distance': stop_distance,
        'stop_count_limit': stop_count_limit,
        'stop_cooloff_period': stop_cooloff_period,
        'limit_distance': limit_distance,
        'backtest_id': key_gen(),
        'trade_stats': backtest_stats
    }

