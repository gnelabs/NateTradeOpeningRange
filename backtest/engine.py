
__author__ = "Nathan Ward"

import logging
from statistics import fmean

_LOGGER = logging.getLogger()
_LOGGER.setLevel(logging.INFO)


class ProcessOpeningRanges(object):
    def __init__(self):
        #Adjustable stop distance for trading. To-do: Research this
        self.stop_distance = 0.25

        #Adjustable count of times stop loss is hit. To-do: Research this
        self.stop_count_limit = 4

        #Adjustable cooloff period in seconds between the stop getting hit before the next trade can commence.
        self.stop_cooloff_period = 30

        #Adjustable take profit distance. To-do: Research this
        self.limit_distance = 5
    
    def backtest(self, open_price:float, range_high:float, range_low:float, intraday_data:list) -> dict:
        """
        Using intraday data collected for each day, perform analysis based on breakouts from the
        opening range as provided.
        """
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
                    limit_price = data['underlying'] + self.limit_distance
                #Bearish breakout below the opening range.
                elif data['underlying'] < range_low:
                    trade_tracker.append(data['underlying'])
                    holding_period.append(data['timestamp_utc'])
                    trade_is_long = False
                    stop_price = data['underlying'] + self.stop_distance
                    limit_price = data['underlying'] - self.limit_distance
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
                    elif data['underlying'] < stop_price or data == intraday_data[-1]:
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
                    elif data['underlying'] > stop_price or data == intraday_data[-1]:
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