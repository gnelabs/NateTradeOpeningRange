# NateTradeOpeningRange
## Description
Backtesting engine & trading system for an intraday trend following strategy based on the opening range.

# Backtesting
## Staging database credentials as environmental variables.
``` python
from os import environ
#Access to natetrade data warehouse.
environ['SQL_USERNAME'] = 'your_username'
environ['SQL_PASSWORD'] = 'your_password'
environ['SQL_HOSTNAME'] = 'sql.natetrade.com'

#Redis and Mysql endpoints if in the cloud.
environ['REDIS_ENDPOINT'] = 'localhost'
environ['DB_ENDPOINT'] = 'localhost'
environ['DB_USERNAME'] = 'root'
environ['DB_PASSWORD'] = '34vFE3PxFJKCzTPZ'
environ['DB_NAME'] = 'results'
environ['DB_TABLE'] = 'results'
```

## Alternatively, you can create env.list file for local testing with docker containers.
``` bash
REDIS_ENDPOINT=172.17.0.2
DB_ENDPOINT=172.17.0.3
DB_USERNAME=root
DB_PASSWORD=34vFE3PxFJKCzTPZ
DB_NAME=results
DB_TABLE=results
```

## Starting test infrastructure in the cloud.
``` python
#Create redis database to cache results.
from backtest.redis_manager import RedisManager
meow = RedisManager()
meow.start_redis()

#Create load balancer to make redis publicly accessible.
from backtest.lb_manager import LBManager
caww = LBManager()
caww.start_lb()
caww.create_target_group()

#Create fleet of fargate virtual machines to run backtests.
from backtest.ecs_manager import TaskManager
woof = TaskManager()
woof.start_task(desired_task_count = 10, start_reason = 'testing17')
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

## Using cached data for a ticker to collect opening range information.
``` python
from backtest.data_collection import CollectOpeningRanges
from backtest.caching import CachedData
from backtest.engine import compress_time_series

collect_or_object = CollectOpeningRanges()
collect_or_object.opening_range_duration = 300

opening_ranges_all_securities = collect_or_object.get_opening_range_data(collect_or_object.epoch_date_ranges())
opening_ranges_organized = collect_or_object.organize_opening_range_data(
    range_data = opening_ranges_all_securities,
    range_duration_to_test = 30
)
del opening_ranges_all_securities

ticker_to_investigate = 'SPY'
cache_obj = CachedData(ticker_to_investigate)

#Load data from a cached file if present.
agg_data = cache_obj.load()

cleaned_data = compress_time_series(agg_data)
del agg_data
```

# Opening Range Breakout (ORB) strategy backtesting.
## Stage opening range data in Redis to be consumed by backtest workers.
``` python
#db = 0 for celery tasks and results
#db = 1 for opening_ranges_organized data for the specified ticker
#db = 2 for cleaned_data

from backtest.caching import StageRedis
stage_obj = StageRedis(ticker_to_investigate)
stage_obj.stage_opening_ranges(opening_ranges_organized)
stage_obj.stage_price_data(cleaned_data)
```

## Backtesting
backtest.startup can be modified to change test parameters.
``` python
from backtest.startup import seed_backtest_requests
seed_backtest_requests()
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

## Deploying to ECR
``` bash
aws ecr get-login-password --region us-east-2 | docker login --username AWS --password-stdin 919768616786.dkr.ecr.us-east-2.amazonaws.com
```

``` bash
docker tag natetradeopeningrange-worker:latest 919768616786.dkr.ecr.us-east-2.amazonaws.com/natetrade/opening_range:latest
```

``` bash
docker push 919768616786.dkr.ecr.us-east-2.amazonaws.com/natetrade/opening_range:latest
```