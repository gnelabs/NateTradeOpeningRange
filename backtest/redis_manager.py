
__author__ = "Nathan Ward"

import logging
from boto3 import client

_LOGGER = logging.getLogger()
_LOGGER.setLevel(logging.INFO)


class ElastiCacheError(Exception):
    """
    Generic exception class if there is an error talking to Elasticache.
    """
    pass


class RedisManager(object):
    def __init__(self):
        #Definition of redis database sizes.
        self.cluster_config = {
            'backteststorage': 'cache.t4g.medium'
        }

        #Cloudformation stack name.
        self.cf_stack_name = 'NateTradeOpeningRange'
        
        self.elasticache_client = client('elasticache', region_name='us-east-2')
        self.cf_client = client('cloudformation', region_name='us-east-2')
    
    def get_cf_outputs(self) -> dict:
        """
        Grab output values from the cloudformation stack to know where to put
        the redis database.
        """
        stack_info = self.cf_client.describe_stacks(StackName=self.cf_stack_name)
        data = {}

        for item in stack_info['Stacks'][0]['Outputs']:
            try:
                data[item['OutputKey']] = item['OutputValue']
            except KeyError:
                _LOGGER.exception('Unable to collect outputs from cloudformation stack. {0}'.format(e))
                raise ElastiCacheError('Unable to collect outputs from cloudformation stack. {0}'.format(e))
        
        return data
    
    def start_redis(self) -> None:
        """
        Start Elasticache Redis clusters.
        """
        cf_info = self.get_cf_outputs()

        for cluster_name, instance_size in self.cluster_config.items():
            try:
                response = self.elasticache_client.create_cache_cluster(
                    CacheClusterId = cluster_name,
                    AZMode = 'single-az',
                    NumCacheNodes = 1,
                    CacheNodeType = instance_size,
                    Engine = 'redis',
                    CacheSubnetGroupName = cf_info['RedisSubnetGroupName'],
                    SecurityGroupIds = [
                        cf_info['RedisSecurityGroupId']
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
        try:
            return self.describe_cluster()['backteststorage']
        except KeyError:
            _LOGGER.exception('Unable to determine endpoint for Redis general storage.')
            raise ElastiCacheError('Unable to determine endpoint for Redis general storage.')
        except Exception as e:
            _LOGGER.exception('Problem determining Redis endpoint. {0}'.format(e))
            raise ElastiCacheError('Problem determining Redis endpoint. {0}'.format(e))

