#!/usr/bin/env python

# Han Xiao <artex.xh@gmail.com> <https://hanxiao.github.io>
import multiprocessing
import os
import random
import sys
import threading
import time
from collections import defaultdict
from datetime import datetime
from itertools import chain
from multiprocessing import Process
from multiprocessing.pool import Pool

import numpy as np
import zmq
import zmq.decorators as zmqd
from termcolor import colored
from zmq.utils import jsonapi

from .helper import *
from .protocol import *
from .http import BertHTTPProxy
from .zmq_decor import multi_socket



class ServerStatistic:
    def __init__(self):
        self._hist_client = defaultdict(int)
        self._client_last_active_time = defaultdict(float)
        self._num_data_req = 0
        self._num_sys_req = 0
        self._num_total_seq = 0
        self._last_req_time = time.time()
        self._last_two_req_interval = []
        self._num_last_two_req = 200
        self._ignored_first = False

    def update(self, request, ignore_first=False):

        if ignore_first == False and self._ignored_first == False:
            self._ignored_first = True
        else:
            client, msg, req_id, msg_len = request
            self._hist_client[client] += 1
            if ServerCmd.is_valid(msg):
                self._num_sys_req += 1
                # do not count for system request, as they are mainly for heartbeats
            else:
                self._num_total_seq += 1
                self._num_data_req += 1
                tmp = time.time()
                self._client_last_active_time[client] = tmp
                self._last_two_req_interval.append(tmp - self._last_req_time)
                if len(self._last_two_req_interval) > self._num_last_two_req:
                    self._last_two_req_interval.pop(0)

                self._last_req_time = tmp

    @property
    def value(self):
        def get_min_max_avg(name, stat):
            if len(stat) > 0:
                return {
                    'avg_%s' % name: sum(stat)/len(stat),
                    'min_%s' % name: min(stat),
                    'max_%s' % name: max(stat),
                    'num_min_%s' % name: sum(v == min(stat) for v in stat),
                    'num_max_%s' % name: sum(v == max(stat) for v in stat),
                }
            else:
                return {}

        def get_min_max_avg2(name, stat):
            if len(stat) > 0:
                return {
                    'avg_%s' % name: int(np.median(stat)),
                    'min_%s' % name: int(np.min(stat)),
                    'max_%s' % name: int(np.max(stat)),
                }
            else:
                return {}

        def get_num_active_client(interval=180):
            # we count a client active when its last request is within 3 min.
            now = time.perf_counter()
            return sum(1 for v in self._client_last_active_time.values() if (now - v) < interval)

        parts = [{
            'num_data_request': self._num_data_req,
            'num_total_seq': self._num_total_seq,
            'num_sys_request': self._num_sys_req,
            'num_total_request': self._num_data_req + self._num_sys_req,
            'num_total_client': len(self._hist_client),
            'num_active_client': get_num_active_client()},
            get_min_max_avg('request_per_client', self._hist_client.values()),
            get_min_max_avg2('last_two_interval', self._last_two_req_interval),
            get_min_max_avg2('request_per_second', [1. / v for v in self._last_two_req_interval]),
        ]

        return {k: v for d in parts for k, v in d.items()}
