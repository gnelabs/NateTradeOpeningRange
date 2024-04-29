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

opening_ranges_all_securities = collect_or_object.get_opening_range_data(collect_or_object.epoch_date_ranges())
opening_ranges_organized = collect_or_object.organize_opening_range_data(opening_ranges_all_securities)

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
    agg_data[k] = backtester.pull_intraday_market_data(
        ticker = ticker_to_investigate,
        starting_epoch_range = v['trading_start']
    )

cache_obj.save(agg_data)
```

## Simple backtest
``` python
profit_tracker = {}
for k, v in agg_data.items():
    result = backtester.backtest(
      open_price = opening_ranges_organized[ticker_to_investigate][k]['open_price'],
      range_high = opening_ranges_organized[ticker_to_investigate][k]['high'],
      range_low = opening_ranges_organized[ticker_to_investigate][k]['low'],
      intraday_data = v
    )
    profit_tracker[k] = result['net_profit']

print('Net profit: ', sum(profit_tracker.values()))
```