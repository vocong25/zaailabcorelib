import argparse
import logging
from logging.handlers import RotatingFileHandler
import os
import sys
import time
from datetime import datetime
import uuid
import warnings
import json

import zmq
from termcolor import colored
from zmq.utils import jsonapi

__all__ = ['set_logger', 'get_args_parser', 'get_status_parser', 'get_switch_parser', 'get_shutdown_parser']

def set_logger(context, logger_dir=None, verbose=False):
    if os.name == 'nt':  # for Windows
        return NTLogger(context, verbose)

    logger = logging.getLogger(context)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    if verbose:
        formatter = logging.Formatter(
        '[%(asctime)s]: %(levelname)-.1s:' + context + ':[%(filename).3s:%(funcName).3s:%(lineno)3d]: %(message)s', datefmt=
        '%y-%m-%d %H:%M:%S')
    else:
        formatter = logging.Formatter(
        '[%(asctime)s]: %(levelname)-.1s:' + context + ': %(message)s', datefmt=
        '%y-%m-%d %H:%M:%S')
    
    if logger_dir:
        file_name = os.path.join(logger_dir, 'WKRClient_{:%Y-%m-%d}.log'.format(datetime.now()))
        handler = RotatingFileHandler(file_name, mode='a', maxBytes=10*1024*1024, backupCount=10, encoding=None, delay=0)
    else:
        handler = logging.StreamHandler()

    handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    handler.setFormatter(formatter)
    logger.handlers = []
    logger.addHandler(handler)
    return logger


class NTLogger:
    def __init__(self, context, verbose):
        self.context = context
        self.verbose = verbose

    def info(self, msg, **kwargs):
        print('I:%s:%s' % (self.context, msg), flush=True)

    def debug(self, msg, **kwargs):
        if self.verbose:
            print('D:%s:%s' % (self.context, msg), flush=True)

    def error(self, msg, **kwargs):
        print('E:%s:%s' % (self.context, msg), flush=True)

    def warning(self, msg, **kwargs):
        print('W:%s:%s' % (self.context, msg), flush=True)

def check_remote_server_config(value):
    if value is None or value.lower() == 'none':
        return None
    
    def raise_err():
        sample_err_str = "%s is an invalid str value of array of remote servers: [<ip_addr>, <port_in>, <port_out>], ex: [['localhost', 8888, 8889], ['10.40.34.15', 9888, 9889]]" % value
        raise argparse.ArgumentTypeError(sample_err_str)

    try:
        raw = str(value)
        ivalue_list = json.loads(raw)

        if not isinstance(ivalue_list, list):
            raise_err()

        if len(ivalue_list) == 0:
            raise_err()

        if any([not isinstance(v, list) for v in ivalue_list]):
            raise_err()

        if any([len(v) != 3 for v in ivalue_list]):
            raise_err()

        def remote_condition(config):
            conditions = []
            conditions.append(isinstance(config[0], str))
            conditions.append(isinstance(config[1], int))
            conditions.append(isinstance(config[2], int))
            return all(conditions)

        if any([not remote_condition(v) for v in ivalue_list]):
            raise_err()

    except TypeError:
        raise_err()

    return ivalue_list

def get_args_parser():

    parser = argparse.ArgumentParser()
    parser.description = 'Startting a WKRDecentralizeCentral instance on a specific port'

    parser.add_argument('-ip', type=str, default='localhost',
                        help='the ip address that a WKRDecentralizeCentral is running on')
    parser.add_argument('-port', '-port_in', '-port_data', type=int, required=True,
                        help='the port that a WKRDecentralizeCentral is running on')
    parser.add_argument('-port_out', '-port_pull', type=int, required=True,
                        help='the port_out that a WKRDecentralizeCentral is running on')
    parser.add_argument('-num_client', type=int, default=24,
                        help='Number of worker for each remote server')
    parser.add_argument('-remote_servers', type=check_remote_server_config, required=True,
                        help="str value of array of remote servers: [<ip_addr>, <port_in>, <port_out>], ex: [['localhost', 8888, 8889], ['10.40.34.15', 9888, 9889]]")
    parser.add_argument('-log_dir', type=str, default=None,
                        help='directory for logging')
    parser.add_argument('-timeout', type=int, default=5000,
                        help='timeout (ms) for connecting to a server')
    return parser

def get_switch_parser():

    parser = argparse.ArgumentParser()
    parser.description = 'Switching WKRDecentralizeCentral config'

    parser.add_argument('-ip', type=str, default='localhost',
                        help='the ip address that a WKRDecentralizeCentral is running on')
    parser.add_argument('-port', '-port_in', '-port_data', type=int, required=True,
                        help='the port that a WKRDecentralizeCentral is running on')
    parser.add_argument('-port_out', '-port_pull', type=int, required=True,
                        help='the port_out that a WKRDecentralizeCentral is running on')
    parser.add_argument('-num_client', type=int, default=0,
                        help='Number of worker for each remote server')
    parser.add_argument('-remote_servers', type=check_remote_server_config, required=True,
                        help="str value of array of remote servers: [<ip_addr>, <port_in>, <port_out>], ex: [['localhost', 8888, 8889], ['10.40.34.15', 9888, 9889]]")
    parser.add_argument('-timeout', type=int, default=5000,
                        help='timeout (ms) for connecting to a server')
    return parser

def get_status_parser():

    parser = argparse.ArgumentParser()
    parser.description = 'Get WKRDecentralizeCentral status'

    parser.add_argument('-ip', type=str, default='localhost',
                        help='the ip address that a WKRDecentralizeCentral is running on')
    parser.add_argument('-port', '-port_in', '-port_data', type=int, required=True,
                        help='the port that a WKRDecentralizeCentral is running on')
    parser.add_argument('-port_out', '-port_pull', type=int, required=True,
                        help='the port_out that a WKRDecentralizeCentral is running on')
    parser.add_argument('-timeout', type=int, default=5000,
                        help='timeout (ms) for connecting to a server')

    return parser

def get_shutdown_parser():

    parser = argparse.ArgumentParser()
    parser.description = 'Shutdown WKRDecentralizeCentral instance running on a specific port'

    parser.add_argument('-ip', type=str, default='localhost',
                        help='the ip address that a WKRDecentralizeCentral is running on')
    parser.add_argument('-port', '-port_in', '-port_data', type=int, required=True,
                        help='the port that a WKRDecentralizeCentral is running on')
    parser.add_argument('-timeout', type=int, default=5000,
                        help='timeout (ms) for connecting to a server')

    return parser

def get_run_args(parser_fn=get_args_parser, printed=True):
    args = parser_fn().parse_args()
    if printed:
        param_str = '\n'.join(['%20s = %s' % (k, v) for k, v in sorted(vars(args).items())])
        print('usage: %s\n%20s   %s\n%s\n%s\n' % (' '.join(sys.argv), 'ARG', 'VALUE', '_' * 50, param_str))
    return args