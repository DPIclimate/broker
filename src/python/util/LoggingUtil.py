import inspect, json, logging, logging.config, os.path, uuid
import BrokerConstants

_mod_src_file = os.path.abspath(inspect.getsourcefile(lambda:0))
_mod_dir = os.path.dirname(_mod_src_file)
_config_file = os.path.join(_mod_dir, 'logging.json')
_config = None

def _config_logging():
    print(_config)
    logging.config.dictConfig(_config)

if os.path.isfile(_config_file):
    with open(_config_file, 'r') as f:
        _config = json.load(f)
        _config_logging()

NO_CID={BrokerConstants.CORRELATION_ID_KEY: uuid.UUID('{00000000-0000-0000-0000-000000000000}')}

cid_logger = logging.getLogger('with_cid')
