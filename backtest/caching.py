
__author__ = "Nathan Ward"

import pickle
import logging
from os import getcwd, path, environ
import asyncio
import ujson
import redis


_LOGGER = logging.getLogger()
_LOGGER.setLevel(logging.INFO)


class CachedData(object):
    def __init__(self, ticker:str):
        self.FILENAME = '{0}-opening-range-data.pkl'.format(ticker)
    
    def load(self) -> dict:
        """
        Load cached data and return object.
        """
        filepath = path.join(getcwd(), 'cached_data', self.FILENAME)
        if path.exists(filepath):
            with open(filepath, 'rb') as f:
                cache = pickle.load(f)
        else:
            cache = {}
        
        return cache
    
    def save(self, open_range_data: dict) -> None:
        """
        Save cached data to cached_data folder in hard disk.
        """
        filepath = path.join(getcwd(), 'cached_data', self.FILENAME)
        with open(filepath, 'wb') as f:
            pickle.dump(open_range_data, f)
        
        return


class StageRedis(object):
    def __init__(self, ticker_to_investigate:str):
        self.ticker = ticker_to_investigate
        self.redis_endpoint = environ['REDIS_ENDPOINT']
    
    async def upload_redis(self, date=str, data=dict, db_num=int):
        r = redis.asyncio.from_url("redis://{0}:6379".format(self.redis_endpoint), db=db_num, decode_responses=True)
        try:
            await r.set(
                date,
                ujson.dumps(data)
            )
        except Exception as e:
            _LOGGER.exception(f"action=upload_redis, status=fail, {e}")

    def batch(self, iterable, n=1):
        l = len(iterable)
        for ndx in range(0, l, n):
            yield iterable[ndx:min(ndx + n, l)]

    def stage_opening_ranges(self, opening_ranges_organized:dict):
        """
        Stage opening range data in db 1.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        tasks = []

        for k_ticker, v_date in opening_ranges_organized.items():
            if k_ticker == self.ticker:
                for k_date, v_data in v_date.items():
                    tasks.append(
                        self.upload_redis(
                            date = k_date,
                            data = v_data,
                            db_num = 1
                        )
                    )

        #Seems to freak out above 500 connections in the pool.
        for i in self.batch(tasks, 100):
            result = loop.run_until_complete(asyncio.gather(*i))

    def stage_price_data(self, cleaned_data: dict):
        """
        Stage intra-day price data for the security in db 2.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        tasks = []

        for k_date, v_data in cleaned_data.items():
            tasks.append(
                self.upload_redis(
                    date = k_date,
                    data = v_data,
                    db_num = 2
                )
            )

        for i in self.batch(tasks, 100):
            result = loop.run_until_complete(asyncio.gather(*i))
