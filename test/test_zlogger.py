from zlogger import Zlogger
log1 = Zlogger(config_dir='conf1')
log1._config_dir

log2 = Zlogger.get_logger()
log2._config_dir

log3 = Zlogger.get_logger()
log3._config_dir