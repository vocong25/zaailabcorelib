import os

from multiprocessing import Process, Event
from termcolor import colored
from .helper import set_logger

class BertHTTPProxy(Process):
    def __init__(self, args):
        super().__init__()
        self.args = args
        self.is_ready = Event()

    def create_flask_app(self):
        try:
            from flask import Flask, request, jsonify, render_template, send_from_directory
            from flask_compress import Compress
            from flask_cors import CORS
            from flask_json import FlaskJSON, as_json, JsonError
            from wkr_serving.client import ConcurrentWKRClient
        except ImportError:
            raise ImportError('WKRClient or Flask or its dependencies are not fully installed, '
                              'they are required for serving HTTP requests.'
                              'Please use "pip install -U bert-serving-server[http]" to install it.')

        print("A")

        # support up to 10 concurrent HTTP requests
        bc = ConcurrentWKRClient(max_concurrency=self.args.http_max_connect,
                                  port=self.args.port, port_out=self.args.port_out,
                                  protocol='obj', ignore_all_checks=True)

        print("B")

        logger = set_logger(colored('PROXY', 'red'))

        if os.path.isdir(self.args.http_stat_dashboard):
            app = Flask(__name__, template_folder=self.args.http_stat_dashboard, static_folder=self.args.http_stat_dashboard)
            @app.route('/stat', methods=['GET'])
            def get_server_status_ui():
                return render_template('index.html', tt_text='{{tt.text}}', tt_value='{{tt.value}}')
            @app.route('/static/<filename>', methods=['GET'])
            def get_static_file(filename):
                return send_from_directory(self.args.http_stat_dashboard, filename)
        else:
            app = Flask(__name__)

        print("C")

        @app.route('/status/server', methods=['GET'])
        # @as_json
        def get_server_status():
            return jsonify(bc.server_status)

        @app.route('/status/client', methods=['GET'])
        # @as_json
        def get_client_status():
            return jsonify(bc.status)

        CORS(app, origins=self.args.cors)
        FlaskJSON(app)
        Compress().init_app(app)

        return app

    def run(self):
        app = self.create_flask_app()
        self.is_ready.set()
        app.run(port=self.args.http_port, threaded=True, host='0.0.0.0')
