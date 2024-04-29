
__author__ = "Nathan Ward"

import pickle
from os import getcwd, path


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