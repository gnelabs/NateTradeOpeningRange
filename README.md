# NateTradeOpeningRange
## Description
Backtesting engine built for large-scale parallel backtests. Includes an opening-range breakout trend following strategy.

## Features

* Uses high-resolution intraday price data from the NateTrade data warehouse.
* High performance backtesting engine with simple comparator logic that takes advantage of L3 cache on the CPU.
* Can be run in native Python, in Docker containers, or in the AWS cloud.
* Includes several helper modules to create and delete pre-configured AWS cloud resources that are cost-optimized.
* Can scale to hundreds of parallel workers and millions of backtests.
* Includes the ability to lifecycle backtest result data out of Redis into persistable MySQL to keep costs low.
* Initial ORB trading strategy includes several tunable parameters to control risk.
* Includes basic plotting module to visualize test results.

## Architecture
Redis is used as a general cache between the workers. It runs three tables:

* db = 0 For worker task management through celery, and to maintain task consistency. 
* db = 1 For opening_ranges_organized data for the specified ticker. 
* db = 2 For cleaned_data staging.

The workers process any available tasks, and return test result data back to Redis as the celery task result.
The reaper is a seperate task that runs on the same workers, that lifecycles data out of Redis and into MySQL.
This is done to preserve available memory, and to make results easier to analyze.

There are two queues stored in Redis to control job demand, both are strongly consistent:

* worker_main - General-purpose low priority work, i.e. backtests. 
* worker_priority - High priority FIFO queue, i.e. data lifecycling, garbage collection, monitoring.

![Example usage](https://github.com/gnelabs/NateTradeOpeningRange/blob/main/or_arch.jpg?raw=true)

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

## Staging credentials for local testing.
Create an env.list file in the main directory to specify settings for local docker testing.
``` bash
REDIS_ENDPOINT=172.17.0.2
DB_ENDPOINT=172.17.0.3
DB_USERNAME=root
DB_PASSWORD=34vFE3PxFJKCzTPZ
DB_NAME=results
DB_TABLE=results
```

## Starting test infrastructure in the cloud.
Access credentials are passed to the cloud from the environemt variables specified earlier.

Redis is run in an insecure mode, do not store sensitive data in it.
``` python
#Create redis database to cache results. Takes about five minutes to spin up.
from backtest.redis_manager import RedisManager
meow = RedisManager()
meow.start_redis()

#Create load balancer to make redis publicly accessible. Takes about two minutes to spin up.
from backtest.lb_manager import LBManager
caww = LBManager()
caww.start_lb()
#Will output the ARNs for the resources created.
lb_resources = caww.create_target_group()

#Create fleet of fargate virtual machines to run backtests. Takes about a minute to spin up, will show up in the ECS tasks dashboard.
from backtest.ecs_manager import TaskManager
woof = TaskManager()
#Limited by ECS service quotas.
woof.start_task(desired_task_count = 10, start_reason = 'testing17')
```

## Stopping cloud test infrastructure.

``` python
#Stopping ECS virtual machine(s)
from backtest.ecs_manager import TaskManager
woof = TaskManager()
for task_arn in woof.list_running_tasks():
    woof.stop_task(task_arn, 'demo')

#Stopping load balancer after starting it
from backtest.lb_manager import LBManager
caww = LBManager()
caww.stop_lb(
    lb_arn = lb_resources['load_balancer_arn'],
    tg_arn = lb_resources['target_group_arn'],
    ls_arn = lb_resources['listener_arn']
)

#Delete redis database
from backtest.redis_manager import RedisManager
meow = RedisManager()
meow.stop_redis()
```

## Caching, download and save data for a ticker.
This will collect a years worth of high-resolution intraday prices.
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

Example output during gather information of a security:
``` bash
>>> opening_ranges_all_securities = collect_or_object.get_opening_range_data(collect_or_object.epoch_date_ranges())
Returned 1267633 rows of data in 18.55 seconds.
```

# Opening Range Breakout (ORB) strategy backtesting.
## Stage opening range data in Redis to be consumed by backtest workers.
``` python
from backtest.caching import StageRedis
stage_obj = StageRedis(ticker_to_investigate)
stage_obj.stage_opening_ranges(opening_ranges_organized)
stage_obj.stage_price_data(cleaned_data)
```

## Running backtests.
backtest.startup can be modified to change test parameters.
Running 9747 backtests took ~22 minutes with two local workers.
``` python
from backtest.startup import seed_backtest_requests
seed_backtest_requests()
```

This will generate a result like:
``` bash
>>> seed_backtest_requests()
Sending 9747 backtest tasks to be processed.
sent 1000 tasks to redis
sent 2000 tasks to redis
sent 3000 tasks to redis
sent 4000 tasks to redis
sent 5000 tasks to redis
sent 6000 tasks to redis
sent 7000 tasks to redis
sent 8000 tasks to redis
sent 9000 tasks to redis
```

## Create results table in MySQL.
This creates a place for lifecycled data to be persisted.
``` sql
CREATE TABLE `results` (
    `backtest_id` VARCHAR(5) NOT NULL DEFAULT '0' COLLATE 'utf8mb4_general_ci',
    `backtest_profit` FLOAT NOT NULL DEFAULT '0',
    `average_holding_period` FLOAT NOT NULL DEFAULT '0',
    `win_rate_percent` INT(3) NOT NULL DEFAULT '0',
    `stop_distance` FLOAT NOT NULL DEFAULT '0',
    `stop_count_limit` INT(11) NOT NULL DEFAULT '0',
    `stop_cooloff_period` INT(11) NOT NULL DEFAULT '0',
    `limit_distance` FLOAT NOT NULL DEFAULT '0',
    `trade_stats` JSON,
    PRIMARY KEY (backtest_id),
    INDEX `ProfitIndex` (`backtest_profit`) USING BTREE
)
COMMENT='Stores backtest results for trades.'
COLLATE='utf8mb4_general_ci'
ENGINE=InnoDB
;
```

## Monitoring computation progress and lifecycling data to MySQL.

Since both Redis and MySQL are directly accessible

``` python
from time import sleep
from backtest.reaper import lifecycle_result_data

for i in range(1,300):
    lifecycle_result_data()
    sleep(20)
```

Example output during monitoring/reaping:
``` bash
>>> for i in range(1,300):
...     lifecycle_result_data()
...     sleep(20)
...
{'status': 'SUCCESS', 'message': 'Reaper successfully lifecycled 1114 rows to MySQL. 33 completed tasks still need to be lifecycled. 7820 tasks are queued but have not been executed yet.', 'duration': 3.838}
{'status': 'SUCCESS', 'message': 'Reaper successfully lifecycled 150 rows to MySQL. 10 completed tasks still need to be lifecycled. 7693 tasks are queued but have not been executed yet.', 'duration': 0.503}
{'status': 'SUCCESS', 'message': 'Reaper successfully lifecycled 123 rows to MySQL. 11 completed tasks still need to be lifecycled. 7569 tasks are queued but have not been executed yet.', 'duration': 0.522}
```

# Analysis after backtesting
## Viewing results in MySQL.
``` sql
SELECT
  ((stop_distance / backtest_profit) * stop_count_limit) AS risk_adjusted_win_rate,
  backtest_id,
  backtest_profit,
  average_holding_period,
  win_rate_percent,
  stop_distance,
  stop_count_limit,
  stop_cooloff_period,
  limit_distance
FROM results.results
ORDER BY risk_adjusted_win_rate
DESC
```

This should give you results that look like this:
![Example usage](https://github.com/gnelabs/NateTradeOpeningRange/blob/main/example_analysis.jpg?raw=true)

## Plotting results
A helper plotting library is included if you want to visualize performance. May require additional dependencies.
``` python
from displayplot import display, pull_data
display(backtest_id = 'hp9BT', table_name = 'results')
```

Displaying the plot will open a browser window with the image:
![Example usage](https://github.com/gnelabs/NateTradeOpeningRange/blob/main/example_plot.jpg?raw=true)

# Development
## Building docker container.
``` bash
docker-compose build
```

## Local testing, run a worker container.

It is recommended to have 32gb of memory on your development machine in order to run a full ecosystem of containers.

``` bash
docker run -t -i --env-file ./env.list natetradeopeningrange-worker
```

## Local testing, run a local instance of Redis server.
``` bash
docker run -e REDIS_ARGS="--maxclients 65000 --appendonly no --save """ -d --name redis-server-no-persistence --ip 172.17.0.2 -p 6379:6379 redis/redis-stack-server:latest
```

## Local testing, run a local instance of MySQL.
``` bash
docker run --name mysql-local --ip 172.17.0.3 -p 3306:3306 -e MYSQL_ROOT_PASSWORD=34vFE3PxFJKCzTPZ -d mysql:latest
```

# Deploying to AWS Cloud
## Deploying Cloudformation template and VPC skeleton

The AWS CLI must be installed and configured with access credentials to your account. SAM CLI must be installed.

``` bash
# Resolve dependencies and create a .aws-sam/build/ directory.
$ sam build --use-container
```

Deploy to cloudformation. Use --guided for the initial install to setup your S3 bucket and what not. 
Information about the stack will be returned as output values.

``` bash
# Deploy the application. Use the guided method so you can fill in information about your S3 bucket and region.
$ sam deploy --guided
```

## Deploying Docker containers to ECR

The container must be uploaded to your elastic container repo to be usable in AWS.
The repository URI can be obtained from RepositoryURI output parameter from the Cloudformation stack.

``` bash
aws ecr get-login-password --region us-east-2 | docker login --username AWS --password-stdin 919768616786.dkr.ecr.us-east-2.amazonaws.com
```

``` bash
docker tag natetradeopeningrange-worker:latest 919768616786.dkr.ecr.us-east-2.amazonaws.com/natetrade/opening_range:latest
```

``` bash
docker push 919768616786.dkr.ecr.us-east-2.amazonaws.com/natetrade/opening_range:latest
```