import configparser
import logging.config
import os
import ast
from logging.handlers import TimedRotatingFileHandler

from zaailabcorelib.zlogger.constant import DEV_FILENAME, PROD_FILENAME, STAG_FILENAME
import traceback
import warnings

class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if len(cls._instances) != 0:
            warnings.warn("This instance is already created so re-use initialized parameters!")
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Zlogger(metaclass=Singleton):
    @classmethod
    def get_logger(cls,  *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

    def __init__(self, project_name=None, config_dir='./conf'):
        self._config_dir = config_dir
        self._getConfigDirectory()
        try:
            env = os.environ['SERVICE_ENV_SETTING']
            assert env in ["DEVELOPMENT", "PRODUCTION", "STAGING"]
        except:
            raise ValueError(
                "The environment param `SERVICE_ENV_SETTING` need to be assigned as: DEVELOPMENT | PRODUCTION | STAGING")

        if env == 'DEVELOPMENT':
            self.conf = self._development()
        elif env == 'STAGING':
            self.conf = self._staging()
        elif env == 'PRODUCTION':
            self.conf = self._production()

        if project_name is None:
            self.project_name = os.environ['NAME']
        else:
            self.project_name = project_name

        cfg_path = None
        if self.conf.has_section('logger'):
            cfg_path = self.conf['logger']

        if cfg_path is not None and self.conf.get('logger', 'log_dir') is not None:
            self.log_dir = self.conf['logger'].get(
                'log_dir', '/data/log/' + self.project_name)
        else:
            self.log_dir = '/data/log/' + self.project_name

        if self.log_dir == "":
            raise ValueError('Error: `log_dir` is expected to be NOT EMPTY')
        
        self.log_dir = str(self.log_dir)  # convert it to str
        if not os.path.exists(self.log_dir):
            os.mkdir(self.log_dir)

        self.CONF_FNAME = 'logging.conf'
        # Load logger config
        log_config_fname = os.path.join(self._config_dir, self.CONF_FNAME)
        if not os.path.isfile(log_config_fname):
            package_dir = os.path.split(__file__)[0]
            log_config_fname = os.path.join(*[package_dir, self.CONF_FNAME])
        logging.config.fileConfig(log_config_fname)

        # Load logger
        self.info_logger = self._get_logger('info')
        self.debug_logger = self._get_logger('debug')
        self.error_logger = self._get_logger('error')

    def _get_logger(self, logger_name):
        logger_handler = TimedRotatingFileHandler(
            filename=self.log_dir + '/{}_'.format(logger_name) + self.project_name + '.log', when='midnight', interval=1,
            backupCount=10)
        logger = logging.getLogger('MainLogger_{}'.format(logger_name))
        logger.propagate = False
        formatter = logging.Formatter('%(asctime)s | %(levelname)-8s | %(filename)s-%(funcName)s-%(lineno)04d | %(message)s')
        logger_handler.setFormatter(formatter)
        logger.addHandler(logger_handler)
        return logger

    def _development(self):
        configParser = configparser.ConfigParser()
        configParser.read(self._dev_config_paths)
        return configParser

    def _staging(self):
        configParser = configparser.ConfigParser()
        configParser.read(self._stag_config_paths)
        return configParser

    def _production(self):
        configParser = configparser.ConfigParser()
        configParser.read(self._prod_config_paths)
        return configParser

    def _getConfigDirectory(self):
        self._dev_config_paths = os.path.join(self._config_dir, DEV_FILENAME)
        self._prod_config_paths = os.path.join(self._config_dir, PROD_FILENAME)
        self._stag_config_paths = os.path.join(self._config_dir, STAG_FILENAME)
        for f in [self._dev_config_paths, self._prod_config_paths, self._stag_config_paths]:
            if not os.path.exists(f):
                raise FileNotFoundError("File not found: {}".format(f))

    def info(self, msg):
        self.info_logger.info(msg)

    def error(self, msg):
        self.error_logger.error(msg)

    def debug(self, msg):
        self.debug_logger.info(msg)

    def exception(self, msg):
        self.error_logger.exception(msg)
