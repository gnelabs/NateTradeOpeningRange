
__author__ = "Nathan Ward"

import logging
from os import environ
from boto3 import client

_LOGGER = logging.getLogger()
_LOGGER.setLevel(logging.INFO)


class ElastiCacheError(Exception):
    """
    Generic exception class if there is an error talking to Elasticache.
    """
    pass


class Redis(object):
    def __init__(self):
        #Definition of redis database sizes.
        self.cluster_config = {
            'backteststorage': 'cache.t4g.medium'
        }
        
        self.elasticache_client = client('elasticache')
    
    def start_redis(self) -> None:
        """
        Start Elasticache Redis clusters.
        """
        for cluster_name, instance_size in self.cluster_config.items():
            try:
                response = self.elasticache_client.create_cache_cluster(
                    CacheClusterId = cluster_name,
                    AZMode = 'single-az',
                    NumCacheNodes = 1,
                    CacheNodeType = instance_size,
                    Engine = 'redis',
                    CacheSubnetGroupName = environ['REDIS_SUBNET_GROUP_NAME'],
                    SecurityGroupIds = [
                        environ['REDIS_SECURITY_GROUP_ID']
                    ],
                    PreferredMaintenanceWindow = 'sat:01:00-sat:03:00',
                    Port = 6379
                )
            except Exception as e:
                _LOGGER.exception('Unable to start Redis cluster. {0}'.format(e))
                raise ElastiCacheError('Unable to start Redis cluster. {0}'.format(e))
    
    def stop_redis(self) -> None:
        """
        Stop Elasticache Redis clusters.
        """
        for cluster_name in self.cluster_config.keys():
            try:
                response = self.elasticache_client.delete_cache_cluster(
                    CacheClusterId = cluster_name
                )
            except Exception as e:
                _LOGGER.exception('Unable to stop Redis cluster. {0}'.format(e))
                raise ElastiCacheError('Unable to stop Redis cluster. {0}'.format(e))
    
    def describe_cluster(self) -> dict:
        """
        Get running Redis database endpoints.
        """
        cluster_info = {}
        
        try:
            response = self.elasticache_client.describe_cache_clusters(ShowCacheNodeInfo = True)
        except Exception as e:
            _LOGGER.exception('Problem listing Redis clusters. {0}'.format(e))
            raise ElastiCacheError('Problem listing Redis clusters. {0}'.format(e))
        
        _LOGGER.info(response)
        for cluster in response['CacheClusters']:
            try:
                cache_node_raw = cluster['CacheNodes']
                for node in cache_node_raw:
                    if node['CacheNodeStatus'] == 'available':
                        cluster_info[cluster['CacheClusterId']] = node['Endpoint']['Address']
            except KeyError:
                cluster_info = {}
                break
        
        return cluster_info
    
    def get_backtest_redis_endpoint(self) -> str:
        """
        Using cluster info, grab the endpoint for general storage.
        """
        _LOGGER.info('4 started get_general_storage_endpoint')
        try:
            return self.describe_cluster()['backteststorage']
        except KeyError:
            _LOGGER.exception('Unable to determine endpoint for Redis general storage.')
            raise ElastiCacheError('Unable to determine endpoint for Redis general storage.')
        except Exception as e:
            _LOGGER.exception('Problem determining Redis endpoint. {0}'.format(e))
            raise ElastiCacheError('Problem determining Redis endpoint. {0}'.format(e))

