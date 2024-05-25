# NateTradeOpeningRange
## Description
Backtesting engine & trading system for an intraday trend following strategy based on the opening range.

# Backtesting
## Staging database credentials as environmental variables.
``` python
from os import environ
environ['SQL_USERNAME'] = 'your_username'
environ['SQL_PASSWORD'] = 'your_password'
environ['SQL_HOSTNAME'] = 'sql.natetrade.com'
```

## Staging modules and collecting data.
``` python
from backtest.data_collection import CollectOpeningRanges
from backtest.caching import CachedData
from backtest.engine import ProcessOpeningRanges

collect_or_object = CollectOpeningRanges()
backtester = ProcessOpeningRanges()

collect_or_object.opening_range_duration = 30
opening_ranges_all_securities = collect_or_object.get_opening_range_data(collect_or_object.epoch_date_ranges())
opening_ranges_organized = collect_or_object.organize_opening_range_data(
    range_data = opening_ranges_all_securities,
    range_duration_to_test = 30
)

ticker_to_investigate = 'SPY'
cache_obj = CachedData(ticker_to_investigate)

#Load data from a cached file if present.
agg_data = cache_obj.load()
```

## Caching, download and save data for a ticker.
Note, there must be a cached_data folder present in the main code directory. Some securities can take up to 20 minutes to download.
``` python
ticker_to_investigate = 'SPY'
cache_obj = CachedData(ticker_to_investigate)

agg_data = {}
for k, v in opening_ranges_organized[ticker_to_investigate].items():
    agg_data[k] = collect_or_object.pull_intraday_market_data(
        ticker = ticker_to_investigate,
        starting_epoch_range = v['trading_start']
    )

cache_obj.save(agg_data)
```

## Backtest example, test a combination of stop iterations, cooloff periods, stop ranges and limit ranges.
``` python
cleaned_data = backtester.compress_time_series(agg_data)

def test():
    for stopiteration in range(1, 4):
        for cooloff in range(10, 300, 120):
            for stop in range(50, 250, 25):
                for limit in range(1, 10):
                    profit_tracker = {}
                    for k_date, v_cleaned_data in cleaned_data.items():
                        #stop distance, in basis points relative to the open price
                        backtester.stop_distance = (opening_ranges_organized[ticker_to_investigate][k_date]['open_price'] * 0.0001) * stop
                        #limit distance, in percentage terms relative to the open price
                        backtester.limit_distance = (opening_ranges_organized[ticker_to_investigate][k_date]['open_price'] * 0.01) * limit
                        #cooloff period
                        backtester.stop_cooloff_period = cooloff
                        #number of Stops
                        backtester.stop_count_limit = stopiteration
                        result = backtester.backtest_redux(
                            opening_range_info = opening_ranges_organized[ticker_to_investigate][k_date],
                            compressed_agg_data = v_cleaned_data
                        )
                        profit_tracker[k_date] = result['net_profit']
                    win_rate = []
                    for v in profit_tracker.values():
                        if v > 0:
                            win_rate.append(True)
                        else:
                            win_rate.append(False)
                    if sum(profit_tracker.values()) > 0:
                        print(
                            'Stops: ',
                            stopiteration,
                            ' Cooloff: ',
                            cooloff,
                            ' Stop dis: ',
                            stop,
                            'bp',
                            ' Limit dis: ',
                            limit,
                            '%',
                            ' Net profit: ',
                            round(sum(profit_tracker.values()), 2),
                            ' Win rate: ',
                            round((win_rate.count(True) / len(win_rate) * 100)),
                            '%'
                        )
```

# Development
## Building docker container.
``` bash
docker-compose build
```

## Running locally to test dockerfile. Stock configuration should start a celery worker instance.
``` bash
docker run -t -i --env-file ./env.list natetradeopeningrange-worker
```