
__author__ = "Nathan Ward"

import logging
from boto3 import client, resource
from backtest.redis_manager import RedisManager

_LOGGER = logging.getLogger()
_LOGGER.setLevel(logging.INFO)


class ECSError(Exception):
    """
    Generic exception class if there is an error talking to ECS.
    """
    pass


class ElastiCacheError(Exception):
    """
    Generic exception class if there is an error talking to Elasticache.
    """
    pass


class TaskManager(object):
    def __init__(self):
        self.ecs_client = client('ecs', region_name='us-east-2')
        self.cf_client = client('cloudformation', region_name='us-east-2')
        self.cf_stackname = 'NateTradeOpeningRange'

        self.cluster_name = 'arn:aws:ecs:us-east-2:919768616786:cluster/NateTradeOpeningRange'
        self.task_def_arn = 'arn:aws:ecs:us-east-2:919768616786:task-definition/NateTradeOpeningRangeOpeningRange'
        
        #Settings for how many tasks to run.
        self.desired_tasks = {
            'arn:aws:ecs:us-east-2:919768616786:task-definition/NateTradeOpeningRangeOpeningRange': 1
        }
        
        #Container override naming.
        self.container_override_names = {
            'arn:aws:ecs:us-east-2:919768616786:task-definition/NateTradeOpeningRangeOpeningRange': 'NateTradeOpeningRangeOpeningRange'
        }

        self.redis_manager_obj = RedisManager()
    
    def get_cloudformation_outputs(self) -> dict:
        """
        Get outputs from the NateTradeOpeningRange to use when creating the ECS containers.
        """
        response = self.cf_client.describe_stacks(StackName=self.cf_stackname)
        output = {}

        for item in response['Stacks'][0]['Outputs']:
            output[item['OutputKey']] = item['OutputValue']

        return output

    def list_running_tasks(self) -> list:
        """
        Get a list of running tasks in the cluster. 
        Returns a list of task ARNs.
        """
        try:
            response = self.ecs_client.list_tasks(cluster=self.cluster_name)
            return response['taskArns']
        except Exception as e:
            _LOGGER.exception('Problem listing running tasks. {0}'.format(e))
            raise ECSError('Problem listing running tasks. {0}'.format(e))
    
    def get_task_details(self, task_arn_list: list) -> dict:
        """
        Get details about the running tasks.
        """
        try:
            response = self.ecs_client.describe_tasks(
                cluster = self.cluster_name,
                tasks = task_arn_list
            )
            return response['tasks']
        except Exception as e:
            _LOGGER.exception('Problem describing tasks. {0}'.format(e))
            raise ECSError('Problem describing tasks. {0}'.format(e))
    
    def start_task(self, desired_task_count: int, start_reason: str) -> None:
        """Start a task."""
        #Populate redis endpoints as environment variables.
        task_env_vars = []

        redis_endpoint = self.redis_manager_obj.get_backtest_redis_endpoint()

        cf_outputs = self.get_cloudformation_outputs()

        task_env_vars.append({
            'name': 'REDIS_ENDPOINT',
            'value': redis_endpoint
        })
        
        try:
            response = self.ecs_client.run_task(
                cluster = self.cluster_name,
                count = desired_task_count,
                capacityProviderStrategy = [
                    {
                        'capacityProvider': 'FARGATE',
                        'weight': 1
                    },
                    {
                        'capacityProvider': 'FARGATE_SPOT',
                        'weight': 10
                    },
                ],
                startedBy = start_reason,
                networkConfiguration = {
                    'awsvpcConfiguration': {
                        'subnets': [
                            cf_outputs['VPCSubnetIDOne'],
                            cf_outputs['VPCSubnetIDTwo']
                        ],
                        'securityGroups': [
                            cf_outputs['RedisSecurityGroupId']
                        ],
                        'assignPublicIp': 'ENABLED'
                    }
                },
                overrides = {
                    'containerOverrides': [
                        {
                            'name': self.container_override_names[self.task_def_arn],
                            'environment': task_env_vars
                        }
                    ]
                },
                taskDefinition = self.task_def_arn
            )
        except Exception as e:
            _LOGGER.exception('Problem starting task {0}. Start reason: {1}. Error: {2}'.format(self.task_def_arn, start_reason, e))
            raise ECSError('Problem starting task {0}. Start reason: {1}. Error: {2}'.format(self.task_def_arn, start_reason, e))
    
    def stop_task(self, task_arn: str, end_reason: str) -> None:
        """Stop a task."""
        try:
            response = self.ecs_client.stop_task(
                cluster = self.cluster_name,
                task = task_arn,
                reason = end_reason
            )
        except Exception as e:
            _LOGGER.exception('Problem stopping task {0}. Start reason: {1}. Error: {2}'.format(task_arn, end_reason, e))
            raise ECSError('Problem stopping task {0}. Start reason: {1}. Error: {2}'.format(task_arn, end_reason, e))
        
