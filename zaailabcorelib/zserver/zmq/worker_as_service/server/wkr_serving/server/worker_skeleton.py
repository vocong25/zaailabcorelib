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


class WKRWorkerSkeleton(Process):
    def __init__(self, id, args, worker_address_list, sink_address, device_id, gpu_fraction, model_name, batch_size, batch_timeout, tmp_dir, name='WORKER', color='yellow'):
        super().__init__()
        self.name = name
        self.color = color
        self.worker_id = id
        self.device_id = device_id
        self.transfer_proto = args.protocol

        self.daemon = True
        self.exit_flag = multiprocessing.Event()
        self.worker_address = worker_address_list
        self.num_concurrent_socket = len(self.worker_address)
        self.sink_address = sink_address

        self.gpu_memory_fraction = gpu_fraction
        self.model_dir = args.model_dir
        self.verbose = args.verbose

        self.model_name = model_name
        self.tmp_folder = os.path.join(self.model_dir, tmp_dir)
        # if not os.path.exists(self.tmp_folder):
        #     os.makedirs(self.tmp_folder)

        self.batch_size = batch_size
        self.batch_group_timeout = batch_timeout

        # self.use_fp16 = args.fp16
        self.is_ready = multiprocessing.Event()

        self.logdir = args.log_dir
        self.logger = set_logger(colored('%s-%d' % (self.name, self.worker_id), self.color), logger_dir=self.logdir, verbose=self.verbose)

    def close(self):
        self.logger.info('shutting down...')
        self.exit_flag.set()
        self.is_ready.clear()
        self.terminate()
        self.join()
        self.logger.info('terminated!')

    def get_env(self, device_id, tmp_dir):
        return []

    def get_model(self, envs, model_dir, model_name, tmp_dir):
        return []

    def get_preprocess(self, envs):
        def preprocessing(input):
            return input
        return preprocessing

    def get_postprocess(self, envs):
        def post_process(output):
            return output
        return post_process

    def predict(self, model, input):
        return input

    def batching(self, list_input):
        if self.transfer_proto == 'obj':
            return list_input
        else:
            processed = [np.expand_dims(a, axis=0) for a in list_input]
            return np.vstack(processed)
            
    def load_raw_msg(self, sock):
        client, req_id, msg, msg_info = recv_from_prev(self.transfer_proto, sock)
        return client, req_id, msg

    def run(self):
        self._run()

    @zmqd.socket(zmq.PUSH)
    @multi_socket(zmq.PULL, num_socket='num_concurrent_socket')
    def _run(self, sink_embed, *receivers):
        # Windows does not support logger in MP environment, thus get a new logger
        # inside the process for better compatibility
        logger = set_logger(colored('%s-%d' % (self.name, self.worker_id), self.color), logger_dir=self.logdir, verbose=self.verbose)

        logger.info('use device %s, load graph from %s/%s' %
                    ('cpu' if self.device_id < 0 else ('gpu: %d' % self.device_id), self.model_dir, self.model_name))

        envs = self.get_env(self.device_id, self.tmp_folder)
        input_preprocessor = self.get_preprocess(envs)
        output_postprocessor = self.get_postprocess(envs)
        model = self.get_model(envs, self.model_dir, self.model_name, self.tmp_folder)

        for sock, addr in zip(receivers, self.worker_address):
            sock.connect(addr)
        sink_embed.connect(self.sink_address)

        generator = self.input_fn_builder(receivers, input_preprocessor)
        for msg in generator():
            try:
                
                client_ids, input_data = msg['client_ids'], msg['input_data']
                logger.warning("Number of client ID: {}".format(len(client_ids)))
                outputs = self.predict(model, input_data)

                if len(outputs) != len(input_data):
                    logger.warning("output after process by predict func not match. input: {}, output: {}".format(input_data, outputs))

                outputs = output_postprocessor(outputs)
                for client_id, output in zip(client_ids, outputs):
                    cliend, req_id = client_id.split('#')
                    send_to_next(self.transfer_proto, cliend, req_id, output, sink_embed)

            except Exception as e:
                import traceback
                tb=traceback.format_exc()
                logger.error('{}\n{}'.format(e, tb))

    def input_fn_builder(self, socks, input_preprocessor):
        def gen():
            # Windows does not support logger in MP environment, thus get a new logger
            # inside the process for better compatibility
            logger = set_logger(colored('%s-%d' % (self.name, self.worker_id), self.color), logger_dir=self.logdir, verbose=self.verbose)

            poller = zmq.Poller()
            for sock in socks:
                poller.register(sock, zmq.POLLIN)

            logger.info('ready and listening!')
            self.is_ready.set()

            def get_single_data(timeout=20):
                events = dict(poller.poll(timeout=timeout))
                if events:
                    for sock_idx, sock in enumerate(socks):
                        if sock in events:
                            client, req_id, msg = self.load_raw_msg(sock)
                            logger.info('new job\tsocket: {}\tclient: {}#{}'.format(sock_idx, client, req_id))
                            return {
                                'client_id': client+'#'+req_id,
                                'client_msg': msg
                            }
                return None

            while not self.exit_flag.is_set():
                try:
                    datas = []
                    for _ in range(self.batch_size):
                        d = get_single_data(timeout=self.batch_group_timeout)
                        if d is not None:
                            datas.append(d)
                    if len(datas) > 0:
                        
                        client_ids = [d['client_id'] for d in datas]
                        batch_raw = [d['client_msg'] for d in datas]
                        batch = self.batching(batch_raw)
                        batch_processed = input_preprocessor(batch)
                        yield {
                            'client_ids': client_ids,
                            'input_data': batch_processed
                        }
                except Exception as e:
                    import traceback
                    tb=traceback.format_exc()
                    logger.error('{}\n{}'.format(e, tb))

        return gen