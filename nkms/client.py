import sha3
import msgpack
from nacl import utils
from nkms.network import dummy
from nkms.crypto import (default_algorithm, pre_from_algorithm,
                         symmetric_from_algorithm)
from io import BytesIO


class Client(object):
    """
    Client which will be used by Python developers to interact with the
    decentralized KMS. For now, this is just the skeleton.


    We will support two capabilities: simple object encryption where a key for
    an object is given by its path, and attribute-based policy where there are
    multiple secrets corresponding to a path. Let's first describe API for
    simple object encryption.

    When doing simple object encryption, each path has a symmetric key encrypted
    with owner's public key (pub). Server works with encrypted symmetric key
    using low-level methods ending with _key, and client can do more high-level
    functions (such as decryption using this key or interaction with different
    storage backends).
    """
    KEY_LENGTH = 148
    network_client_factory = dummy.Client

    def __init__(self, conf=None):
        """
        :param str conf: Config file to load/save the key information from. If
            not given, a default one in the home directory is used
            or created
        """
        self._nclient = Client.network_client_factory()
        self._pre = pre_from_algorithm(default_algorithm)
        self._symm = symmetric_from_algorithm(default_algorithm)

        # TODO: Check for existing keypair before generation
        # TODO: Save newly generated keypair
        self._priv_key = self._pre.gen_priv(dtype='bytes')
        self._pub_key = self._pre.priv2pub(self._priv_key)

    def _derive_path_key(self, path, is_pub=True):
        """
        Derives a public key for the specific path.

        :param bytes path: Path to generate key for.
        :param bool is_pub: Is the derived key a public key?

        :return: Derived key
        :rtype: bytes
        """
        key = sha3.keccak_256(self._priv_key + path).digest()
        return self._pre.priv2pub(key) if is_pub else key

    def _split_path(self, path):
        """
        Splits the file path provided and provides subpaths to each directory.

        :param bytes path: Path to file

        :return: Subpath(s) from path
        :rtype: list of bytes
        """
        # Hacky workaround: b'/'.split(b'/') == [b'', b'']
        if path == b'/':
            return [b'']

        dirs = path.split(b'/')
        return [b'/'.join(dirs[:i + 1]) for i in range(len(dirs))]

    def _build_header(self, enc_keys, version=100):
        """
        Creates a NuCypher header for the encrypted file.

        :param enc_keys: List of encrypted keys in bytes
        :param version: Version number of Cryptographic API (default: 0.1.0.0)

        :return: Complete header msgpack encoded and length of raw header
        :rtype: Tuple of the header and the header length e.g: (<header>, 1200)
        """
        if version < 1000:
            vers_bytes = version.to_bytes(4, byteorder='big')
            num_keys_bytes = len(enc_keys).to_bytes(4, byteorder='big')
            keys = b''.join(enc_keys)
            header = msgpack.dumps(vers_bytes + num_keys_bytes + keys)
        return (header, len(header))

    def _read_header(self, header):
        """
        Reads a NuCypher header.

        :param header: Msgpack encoded header to read

        :return: Version number, and list of encrypted keys
        :rtype: Tuple of an int and a list e.g: (100, [...])
        """
        header = BytesIO(msgpack.loads(header))
        vers_bytes = header.read(4)
        version = int.from_bytes(vers_bytes, byteorder='big')

        # Handle pre-alpha versions
        if version < 1000:
            num_keys_bytes = header.read(4)
            num_keys = int.from_bytes(num_keys_bytes, byteorder='big')
            enc_keys = [header.read(Client.KEY_LENGTH) for _ in range(num_keys)]
        return (version, enc_keys)

    def encrypt_key(self, key, pubkey=None, path=None, algorithm=None):
        """
        Encrypt (symmetric) key material with our public key or the public key
        "pub" if given.

        If "path" is given, we encrypt "key" with derived private keys for each
        subpath and return msgpacked keys for all the subpaths. For example, a
        path could be:

        path = "/passwords/aws/mycoolwebsite.com"

        and for that, we have derived keys for "/", "/passwords",
        "/passwords/aws" and "/passwords/aws/mycoolwebsite.com". They all
        encrypt the same symmetric key "key".

        :param bytes key: Symmetric key to encrypt
        :param bytes pubkey: Public key to encrypt for
        :param bytes path: Path to the data (to be able to share
            sub-paths). If None, encrypted with just our pubkey.
        :param dict algorithm: Algorithm parameters (name, curve, re-encryption
            type, m/n etc). None if default

        :return: List of encrypted key(s)
        :rtype: bytes
        """
        if not pubkey:
            pubkey = self._pub_key

        if path is not None:
            enc_keys = []
            subpaths = self._split_path(path)
            for subpath in subpaths:
                path_pubkey = self._derive_path_key(subpath)
                enc_keys.append(self.encrypt_key(key, pubkey=path_pubkey))
            return enc_keys
        elif not path:
            return self._pre.encrypt(pubkey, key)

    def decrypt_key(self, enc_key, pubkey=None, path=None, owner=None):
        """
        Decrypt (symmetric) key material. Params similar to decrypt()

        :param bytes enc_key: Encrypted symmetric key to decrypt
        :param bytes path: Path of encrypted file

        :return: Decrypted key
        :rtype: bytes
        """
        if path is not None:
            priv_key = self._derive_path_key(path, is_pub=False)
        else:
            priv_key = self._priv_key
        return self._pre.decrypt(priv_key, enc_key)

    def grant(self, pubkey, path=None, policy=None):
        """
        Allow pubkey to read the data by path (or everything) by creating the
        re-encryption key and submitting it to the network.

        :param bytes pubkey: Public key of who we share the data with
        :param bytes path: Path which we share. If None - share everything
        :param dict policy: Policy for sharing. For now, can have start_time and
            stop_time (in Python datetime or unix time (int)). Also permissions
            to 'read' the key, 'remove' the rekey and 'grant' permissions to
            others. When policy is not set, it's only 'read'
        """
        # TODO Handle path
        # Create reencryption key
        reenc_key = self._pre.rekey(self._priv_key, pubkey)
        pass

    def revoke(self, pubkey, path=None):
        """
        Revoke a currently existing policy. Tells re-encryption nodes to remove
        the corresponding rekeys.

        :param bytes pubkey: Public key of who we shared the data with
        :param tuple(str) path: Path which we share. If None - revoke everything
        """
        pass

    def list_permissions(self, pubkey=None, path=None):
        pass

    def encrypt_bulk(self, data, key, algorithm=None):
        """
        Encrypt bulk of the data with a symmetric cipher

        :param bytes data: Data to encrypt
        :param bytes key: Symmetric key
        :param str algorithm: Algorithm to use or None for default

        :return: Encrypted data
        :rtype: bytes
        """
        # TODO Handle algorithm
        # Nonce is generated implicitly within cipher.encrypt as random data
        cipher = self._symm(key)
        return cipher.encrypt(data)

    def decrypt_bulk(self, edata, key, algorithm=None):
        """
        Decrypt bulk of the data with a symmetric cipher

        :param bytes edata: Data to decrypt
        :param bytes key: Symmetric key
        :param str algorithm: Algorithm to use or None for default

        :return: Plaintext data
        :rtype: bytes
        """
        # TODO Handle algorithm
        cipher = self._symm(key)
        return cipher.decrypt(edata)

    def open(self, pubkey=None, path=None, mode='rb', fd=None, algorithm=None):
        """
        The main interface through which Python API will work.

        One way is to open an encrypted file via the descriptor fd. Will
        internally use methods decrypt_key and decrypt_bulk.

        The other way is opening the actual file through backends and using the
        KMS to decrypt data (or create new keys). The path schema examples:

        s3://my_bucket/path/to/secret.txt
        ipfs://0x1242542346/path/file.txt
        file://home/ubuntu/my/secret/file.txt

        The mode will be in agreement to the granted permissions.

        If pubkey is not set, we're working on our own files.
        """
        file_path = fd or path
        try:
            with open(file_path, mode=mode) as f:
                enc_data = f.read()
        except Exception as E:
            raise E
        return self.decrypt(enc_data, path=path)

    def remove(self, pubkey=None, path=None):
        """
        Remove the file and all the rekeys associated with it. Similar to revoke
        but removing the actual files if the path is given with a schema.
        """
        pass

    def encrypt(self, data, path=None, algorithm=None):
        """
        Encrypts data in a form ready to ship to the storage layer.

        :param bytes data: Data to encrypt
        :param tuple(str) path: Path to the data (to be able to share
            sub-paths). If None, encrypted with just our pubkey.
            If contains only 1 element or is a string, this is just used as a
            unique identifier w/o granular encryption.
        :param dict algorithm: Algorithm parameters (name, curve, re-encryption
            type, m/n etc). None if default

        :return: Encrypted data
        :rtype: bytes
        """
        # Generate a secure key and encrypt the data
        data_key = utils.random(32)
        ciphertext = msgpack.dumps(self.encrypt_bulk(data, data_key))

        # Derive keys and encrypt them
        # TODO: https://github.com/nucypher/nucypher-kms/issues/33
        if path is not None:
            enc_keys = self.encrypt_key(data_key, path=path)
        else:
            enc_keys = [self.encrypt_key(data_key, path=path)]

        # Build the header
        header, header_length = self._build_header(enc_keys)

        # Format for storage
        header_length_bytes = header_length.to_bytes(4, byteorder='big')
        storage_data = header_length_bytes + header + ciphertext
        return storage_data

    def decrypt(self, edata, path=None, owner=None):
        """
        Decrypt data encrypted by its owner. If the owner != ourselves, a
        re-encryption request is automatically submitted. The function
        automatically splits out encrypted symmetric keys.

        :param bytes edata: Encrypted data
        :param tuple(str) path: Path to the data or its identifier
        :param bytes owner: If the path is None, owner can be used to identify
            the re-encryption key. The owner is specified by his pubkey

        :return: Unencrypted data
        :rtype: bytes
        """
        enc_file = BytesIO(edata)

        header_length = int.from_bytes(enc_file.read(4), byteorder='big')
        header = enc_file.read(header_length)
        version, enc_keys = self._read_header(header)

        ciphertext = msgpack.loads(enc_file.read())

        if version < 1000:
            valid_key = None
            for enc_key in enc_keys:
                dec_key = self.decrypt_key(enc_key, path=path)
                if len(dec_key) == 32:
                    valid_key = dec_key
                    break
            plaintext = self.decrypt_bulk(ciphertext, valid_key)
        return plaintext
