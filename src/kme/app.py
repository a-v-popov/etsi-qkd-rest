import falcon
import redis,json
import secrets,math,uuid,base64
import logging
import configparser

def containerize(key_id,key):
    return {'key_ID':key_id,'key':key}

def list2dict(containers):
    return {'keys':containers}

class KeyStore():
    def __init__(self,size = None, number = None, host = None):
        if size is None:
            self.size = 256
        else:
            self.size = size
        if number is None:
            self.number = 1
        else:
            self.number = number
        
        if host is None:
            self.keys={}
        else:
            self.keys = redis.Redis(host=host)

    # in future key might be selected by key_ID and key_ID_extension

    # return a ETSI defined(6.3) list of key containers in a 'keys' dict
    def create(self, master, slave, size = None, number = None):
        if size is None:
            size = self.size
        if number is None:
            number = self.number
        
        # technically in ETSI standard keys are at least per master
        # but since key_ID is random uuid ignore this fact for now
        containers = []
        for i in range(number):
            key_id = str(uuid.uuid4())
            key = base64.b64encode(secrets.token_bytes((math.ceil(size/8)))).decode()
            self.keys[key_id] = json.dumps({'key':key,'acl':[slave,master],'master':master})
            containers.append(containerize(key_id,key))
        return containers


    # get ETSI defined(6.4) list of dict [{'key_ID':'uuid'}]
    # presense of future key_ID_extension is treated as unknown key
    # return a ETSI defined(6.3) list of key containers
    def get(self, master, slave, keys):
        containers = []
        for key in keys:
            # key_ID_extension is not used
            if 'key_ID_extension' in key:
                return None
            key_id = key['key_ID']
            
            kd = json.loads(self.keys[key_id])
            
            if kd['master'] != master:
                raise KeyError

            if slave not in kd['acl']:
                raise KeyNotAuthorized
            
            containers.append(containerize(key_id,kd['key']))
        return containers

class KeyNotFound(Exception):
    pass

class KeyNotAuthorized(Exception):
    pass

class KeyManagementEntity():
    def __init__(self,kme_id, redis_host = None, size = None, number = 1 ):
        self.sae = {}
        self.kme_id = kme_id
        self.ks = KeyStore(size = size, host = redis_host)

    def on_get(self, req, resp, sae_id, method):
        # header should have been populated by TLS proxy/server
        req_sae_id = req.headers['X-CERT-CN']
        self.sae[req_sae_id] = self.kme_id 
        
        # check if you know sae_ID
        # if not sae_id in self.sae:
        #    resp.media = { 'message': 'SAE ID not found' }
        #    raise falcon.HTTPNotFound()

        # ETSI decided to have its own "methods" on top of HTTP methods
        if method == 'status':
            self.sae[req_sae_id] = self.kme_id 

            resp.media = { 'source_KME_ID': self.kme_id, 
                            'target_KME_ID': 0, #self.sae[sae_id],
                            'master_SAE_ID': req_sae_id,
                            'slave_SAE_ID': sae_id,
                            'key_size': 256,
                            'stored_key_count': 25000,
                            'max_key_count': 100000,
                            'max_key_per_request': 128,
                            'max_key_size': 1024,
                            'min_key_size': 64,
                            'max_SAE_ID_count': 0 }

        elif method == 'enc_keys':
            # Only size and/or number are allowed in GET request
            try:
                size = req.params.pop('size',None)
                if not size is None:
                    size = int(size)
                number = req.params.pop('number',None)
                if not number is None:
                    number = int(number)
                if len(req.params) != 0:
                    raise ValueError
            except ValueError:
                resp.media = { 'message': 'Bad request format' }
                raise falcon.HTTPBadRequest()
                
            resp.media = list2dict(self.ks.create(req_sae_id, sae_id, size, number))

        elif method == 'dec_keys':
            if not 'key_ID' in req.params:
                resp.media = { 'message': 'missing key_ID' }
                raise falcon.HTTPBadRequest()
            key_id = req.params['key_ID']
            resp.media = list2dict(self.ks.get(sae_id,req_sae_id,[{'key_ID':key_id}]))

        else:
            resp.media = { 'message': 'ETSI API method not supported' }
            raise falcon.HTTPBadRequest()

    def on_post(self, req, resp, sae_id, method):
        req_sae_id = req.headers['X-CERT-CN']

        if method == 'enc_keys':
            number = req.media.pop('number',None)
            size = req.media.pop('size',None)
            resp.media = list2dict(self.ks.create(req_sae_id, sae_id, size, number))
        elif method == 'dec_keys':
            resp.media = list2dict(self.ks.get(sae_id, req_sae_id, req.media['key_IDs']))
        else:
            resp.media = { 'message': 'ETSI API method not supported' }
            raise falcon.HTTPBadRequest()

def key_error_handler(ex,req,resp,params):
    resp.media = {'message': 'Key ID Not Found' }
    raise falcon.HTTPNotFound()

class LoggerMiddleware():
    def process_resource(self,req,resp,resource,params):
        log.info('Recieved {} from {} for "{}" method "{}"'.format( req.method,
                                                                    req.headers['X-CERT-CN'],
                                                                    params['sae_id'],
                                                                    params['method']))
        log.debug('Headers: {}'.format(req.headers))
        if req.params:
            log.info('Params: {}'.format(req.params))
        if req.method == 'POST':
            log.info('Media: {}'.format(req.media))

def load_app(cfg_file):
    config = configparser.ConfigParser()
    config.read(cfg_file)
    cfg = config['kme']
    log.info('Starting KME as ' + cfg.get('id'))

    kme = KeyManagementEntity(kme_id=cfg.get('id'),redis_host=cfg.get('redis_host'))
    app = falcon.API(middleware = [LoggerMiddleware()])

    app.add_route('/api/v1/keys/{sae_id}/{method}', kme)

    app.add_error_handler(KeyNotFound,key_error_handler)
    return app

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


