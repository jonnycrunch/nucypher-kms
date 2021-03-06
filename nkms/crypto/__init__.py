import importlib
from nacl.utils import random  # noqa

# 'Random' parameter g here is derived from Bitcoin's hashMerkleRoot of
# its genesis block:
# bbs98.ec.serialize(
#    bbs98.ec.hashEC(
#       pre.ecgroup,
#       base64.decodebytes(b'4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b')
#       bbs98.ec.G)) = b'1:A78WgHh03I38RcZO/FQe9SbmPVzQg+oehzR8QsGXOeqz'
default_algorithm = dict(
        symmetric=dict(
            cipher='nacl'),
        pre=dict(
            cipher='bbs98',     # BBS98 is only temporary here, for development
            curve=714,          # secp256k1 in OpenSSL
            g=b'1:A78WgHh03I38RcZO/FQe9SbmPVzQg+oehzR8QsGXOeqz',
            m=None, n=None))


def symmetric_from_algorithm(algorithm):
    module = importlib.import_module(
            'nkms.crypto.block.' + algorithm['symmetric']['cipher'])
    # TODO need to cache this
    return module.Cipher


def pre_from_algorithm(algorithm):
    kw = {k: v for k, v in algorithm['pre'].items()
          if k != 'cipher' and v is not None}
    module = importlib.import_module(
            'nkms.crypto.pre.' + algorithm['pre']['cipher'])
    # TODO need to cache this
    return module.PRE(**kw)
