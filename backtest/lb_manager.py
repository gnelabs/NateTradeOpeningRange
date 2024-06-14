
__author__ = "Nathan Ward"

import logging
from socket import gethostbyname
from boto3 import client, resource
from backtest.redis_manager import Redis
from backtest.ecs_manager import TaskManager

_LOGGER = logging.getLogger()
_LOGGER.setLevel(logging.INFO)


class LBError(Exception):
    """
    Generic exception class if there is an error talking to NLB.
    """
    pass


class LBManager(object):
    def __init__(self):
        self.lb_client = client('elbv2', region_name='us-east-2')
        self.load_balancer_name = 'RedisPublicNLB'

        self.redis_manager_obj = Redis()
        self.cf_output = TaskManager().get_cloudformation_outputs()
    
    def start_lb(self):
        """
        Start the network load balancer in front of Redis.
        """
        try:
            self.lb_client.create_load_balancer(
                Name = self.load_balancer_name,
                Subnets = [
                    self.cf_output['VPCSubnetIDOne'],
                    self.cf_output['VPCSubnetIDTwo']
                ],
                SecurityGroups = [self.cf_output['LBSecurityGroupId']],
                Scheme = 'internet-facing',
                Type = 'network',
                IpAddressType = 'ipv4',

            )
        except Exception as e:
            _LOGGER.exception('Problem starting load balancer {0}.'.format(e))
            raise LBError('Problem starting load balancer {0}.'.format(e))

    def get_lb_details(self) -> dict:
        """Get the details about the lb."""
        try:
            result = self.lb_client.describe_load_balancers()

            details = {}

            for item in result['LoadBalancers']:
                if item['LoadBalancerName'] == self.load_balancer_name:
                    details['hostname'] = item['DNSName']
                    details['arn'] = item['LoadBalancerArn']
        except Exception as e:
            _LOGGER.exception('Problem getting load balancer information {0}.'.format(e))
            raise LBError('Problem getting load balancer information {0}.'.format(e))

        return details

    def stop_lb(self, lb_arn=str, tg_arn=str, ls_arn=str):
        """
        Stop the running load balancer to avoid hourly charges.
        """
        try:
            self.lb_client.delete_listener(
                ListenerArn = ls_arn
            )

            self.lb_client.delete_target_group(
                TargetGroupArn = tg_arn
            )

            self.lb_client.delete_load_balancer(
                LoadBalancerArn = lb_arn
            )
        except Exception as e:
            _LOGGER.exception('Problem stopping load balancer {0}.'.format(e))
            raise LBError('Problem stopping load balancer {0}.'.format(e))

    def create_target_group(self) -> dict:
        """
        Create a target group to point to the Redis database within the VPC.
        """
        redis_hostname = self.redis_manager_obj.get_backtest_redis_endpoint()
        redis_ip = gethostbyname(redis_hostname)
        load_balancer_info = self.get_lb_details()

        try:
            tg_result = self.lb_client.create_target_group(
                Name = ''.join(['redistarget-', redis_ip.replace('.', '-')]),
                Protocol = 'TCP',
                Port = 6379,
                VpcId = self.cf_output['VPCId'],
                HealthCheckProtocol = 'TCP',
                HealthCheckPort = '6379',
                HealthCheckEnabled = True,
                TargetType = 'ip',
                IpAddressType = 'ipv4'
            )

            target_group_arn = tg_result['TargetGroups'][0]['TargetGroupArn']

            self.lb_client.register_targets(
                TargetGroupArn = target_group_arn,
                Targets = [
                    {
                        'Id': redis_ip,
                        'Port': 6379
                    }
                ]
            )

            ls_result = self.lb_client.create_listener(
                LoadBalancerArn = load_balancer_info['arn'],
                Protocol = 'TCP',
                Port = 6379,
                DefaultActions = [
                    {
                        'Type': 'forward',
                        'TargetGroupArn': target_group_arn
                    }
                ]
            )

            listener_arn = ls_result['Listeners'][0]['ListenerArn']

            return {
                'load_balancer_arn': load_balancer_info['arn'],
                'target_group_arn': target_group_arn,
                'listener_arn': listener_arn
            }
        except Exception as e:
            _LOGGER.exception('Problem creating target group. {0}.'.format(e))
            raise LBError('Problem creating target group. {0}.'.format(e))
