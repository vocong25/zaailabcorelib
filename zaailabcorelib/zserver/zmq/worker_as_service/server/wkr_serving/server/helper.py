import argparse
import logging
from logging.handlers import RotatingFileHandler
import os
import sys
import time
from datetime import datetime
import uuid
import warnings

import zmq
from termcolor import colored

__all__ = ['set_logger', 'get_args_parser',
           'check_tf_version', 'auto_bind', 'import_tf', 'import_torch']

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
        file_name = os.path.join(logger_dir, 'WKRServer_{:%Y-%m-%d}.log'.format(datetime.now()))
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

def check_max_seq_len(value):
    if value is None or value.lower() == 'none':
        return None
    try:
        ivalue = int(value)
        if ivalue <= 3:
            raise argparse.ArgumentTypeError("%s is an invalid int value must be >3 "
                                             "or NONE" % value)
    except TypeError:
        raise argparse.ArgumentTypeError("%s is an invalid int value" % value)
    return ivalue

def check_batch_size(value):
    if value is None or value.lower() == 'none':
        return None

    try:
        ivalue = int(value)

        if ivalue < 1:
            raise argparse.ArgumentTypeError("%s is an invalid int value must be >3 "
                                             "or NONE" % value)
    except TypeError:
        raise argparse.ArgumentTypeError("%s is an invalid int value" % value)

    return ivalue

def check_protocol(value):

    if value is None or value.lower() == 'none':
        raise argparse.ArgumentTypeError("%s is an invalid transfer protocol, must be 'obj' or 'numpy'" % value)

    try:
        ivalue = str(value).lower()
        if ivalue in ['obj', 'numpy']:
            return ivalue
        else:
            raise argparse.ArgumentTypeError("%s is an invalid transfer protocol, must be 'obj' or 'numpy'" % value)

    except TypeError:
        raise argparse.ArgumentTypeError("%s is an invalid transfer protocol, must be 'obj' or 'numpy'" % value)

def get_args_parser():
    from . import __version__

    parser = argparse.ArgumentParser(description='Start a WKRServer for serving')

    group1 = parser.add_argument_group('File Paths',
                                       'config the path, checkpoint and filename of a TTS model')

    group1.add_argument('-model_dir', type=str, required=True,
                        help='directory of models')
    group1.add_argument('-model_name', type=str, default=None,
                        help='filename of the main worker model.')
    group1.add_argument('-tmp_folder', type=str, default='tmp_wkr',
                        help='name of the main worker temporary folder.')

    groupwa = parser.add_argument_group('Main Worker Parameters',
                                       'config how main model work')
    groupwa.add_argument('-gpu_memory_fraction', type=float, default=0.2,
                        help='determine the fraction of the overall amount of memory \
                        that each visible GPU should be allocated per Waveglow worker. \
                        Should be in range [0.0, 1.0]')
    groupwa.add_argument('-num_worker', type=int, default=1,
                        help='number of server instances')
    groupwa.add_argument('-batch_size', type=int, default=10,
                        help='maximum number of sequences handled by each worker')
    groupwa.add_argument('-batch_group_timeout', type=int, default=1,
                        help='maximum time(ms) for wait for a new request, we all need waveglow to fix input shape, so need to wait a much longer')
    groupwa.add_argument('-cpu', action='store_true', default=False,
                        help='running on CPU (default on GPU)')
    groupwa.add_argument('-device_map', type=int, nargs='+', default=[],
                        help='specify the list of GPU device ids that will be used (id starts from 0). \
                        If num_worker > len(device_map), then device will be reused; \
                        if num_worker < len(device_map), then device_map[:num_worker] will be used')

    group3 = parser.add_argument_group('Serving Configs',
                                       'config how server utilizes GPU/CPU resources')
    group3.add_argument('-protocol', type=check_protocol, default='obj',
                        help='server-client tranfer protocol')
    group3.add_argument('-port', '-port_in', '-port_data', type=int, default=5555,
                        help='server port for receiving data from client')
    group3.add_argument('-port_out', '-port_result', type=int, default=5556,
                        help='server port for sending result to client')
    group3.add_argument('-http_port', type=int, default=None,
                        help='server port for receiving HTTP requests')
    group3.add_argument('-http_max_connect', type=int, default=20,
                        help='maximum number of concurrent HTTP connections')
    group3.add_argument('-http_stat_dashboard', type=str, default='none',
                        help='dashboard template')
    group3.add_argument('-cors', type=str, default='*',
                        help='setting "Access-Control-Allow-Origin" for HTTP requests')
    
    parser.add_argument('-verbose', action='store_true', default=False,
                        help='turn on tensorflow logging for debug')
    parser.add_argument('-version', action='version', version='%(prog)s ' + __version__)
    
    parser.add_argument('-log_dir', type=str, default=None,
                        help='directory for logging')

    return parser

def check_tf_version():
    import tensorflow as tf
    tf_ver = tf.__version__.split('.')
    if int(tf_ver[0]) <= 1 and int(tf_ver[1]) < 8:
        raise ModuleNotFoundError('Tensorflow >=1.8 (one-point-eight) is required!')
    elif int(tf_ver[0]) > 1:
        warnings.warn('Tensorflow %s is not tested! It may or may not work. '
                      'Feel free to submit an issue at https://github.com/hanxiao/bert-as-service/issues/' % tf.__version__)
    return tf_ver

def import_tf(device_id=-1, verbose=False, use_fp16=False):
    os.environ['CUDA_VISIBLE_DEVICES'] = '-1' if device_id < 0 else str(device_id)
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '0' if verbose else '3'
    os.environ['TF_FP16_MATMUL_USE_FP32_COMPUTE'] = '0' if use_fp16 else '1'
    os.environ['TF_FP16_CONV_USE_FP32_COMPUTE'] = '0' if use_fp16 else '1'
    import tensorflow as tf
    tf.logging.set_verbosity(tf.logging.DEBUG if verbose else tf.logging.ERROR)
    return tf


def import_torch(device_id=-1, verbose=False, use_fp16=False):
    assert device_id >= 0, 'WaveGlow can only on GPU'
    os.environ['CUDA_VISIBLE_DEVICES'] = str(device_id)
    import torch
    torch.backends.cudnn.benchmark = True
    return torch

def import_mxnet(device_id=-1, verbose=False, use_fp16=False):
    assert device_id >= 0, 'MXNet can only on GPU'
    os.environ['CUDA_VISIBLE_DEVICES'] = str(device_id)
    import mxnet
    return mxnet


def auto_bind(socket):
    if os.name == 'nt':  # for Windows
        socket.bind_to_random_port('tcp://127.0.0.1')
    else:
        # Get the location for tmp file for sockets
        try:
            tmp_dir = os.environ['ZEROMQ_SOCK_TMP_DIR']
            if not os.path.exists(tmp_dir):
                raise ValueError('This directory for sockets ({}) does not seems to exist.'.format(tmp_dir))
            tmp_dir = os.path.join(tmp_dir, str(uuid.uuid1())[:8])
        except KeyError:
            tmp_dir = '*'
        socket.bind('ipc://{}'.format(tmp_dir))
    return socket.getsockopt(zmq.LAST_ENDPOINT).decode('ascii')


def get_run_args(parser_fn=get_args_parser, printed=True):
    args = parser_fn().parse_args()
    if printed:
        param_str = '\n'.join(['%20s = %s' % (k, v) for k, v in sorted(vars(args).items())])
        print('usage: %s\n%20s   %s\n%s\n%s\n' % (' '.join(sys.argv), 'ARG', 'VALUE', '_' * 50, param_str))
    return args


def get_benchmark_parser():
    parser = get_args_parser()
    parser.description = 'Benchmark WKRServer locally'

    parser.set_defaults(num_client=1, client_batch_size=4096)

    group = parser.add_argument_group('Benchmark parameters', 'config the experiments of the benchmark')

    group.add_argument('-test_client_batch_size', type=int, nargs='*', default=[1, 16, 256, 4096])
    group.add_argument('-test_max_batch_size', type=int, nargs='*', default=[8, 32, 128, 512])
    group.add_argument('-test_max_seq_len', type=int, nargs='*', default=[32, 64, 128, 256])
    group.add_argument('-test_num_client', type=int, nargs='*', default=[1, 4, 16, 64])
    group.add_argument('-test_pooling_layer', type=int, nargs='*', default=[[-j] for j in range(1, 13)])

    group.add_argument('-wait_till_ready', type=int, default=30,
                       help='seconds to wait until server is ready to serve')
    group.add_argument('-client_vocab_file', type=str, default='README.md',
                       help='file path for building client vocabulary')
    group.add_argument('-num_repeat', type=int, default=10,
                       help='number of repeats per experiment (must >2), '
                            'as the first two results are omitted for warm-up effect')
    return parser


def get_shutdown_parser():
    parser = argparse.ArgumentParser()
    parser.description = 'Shutting down a WKRServer instance running on a specific port'

    parser.add_argument('-ip', type=str, default='localhost',
                        help='the ip address that a WKRServer is running on')
    parser.add_argument('-port', '-port_in', '-port_data', type=int, required=True,
                        help='the port that a WKRServer is running on')
    parser.add_argument('-timeout', type=int, default=5000,
                        help='timeout (ms) for connecting to a server')
    return parser


class TimeContext:
    def __init__(self, msg):
        self._msg = msg

    def __enter__(self):
        self.start = time.perf_counter()
        print(self._msg, end=' ...\t', flush=True)

    def __exit__(self, typ, value, traceback):
        self.duration = time.perf_counter() - self.start
        print(colored('    [%3.3f secs]' % self.duration, 'green'), flush=True)
