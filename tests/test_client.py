import unittest
import msgpack
from nacl.utils import random
from nkms.client import Client
from nkms.crypto import (default_algorithm, pre_from_algorithm,
                         symmetric_from_algorithm)


class TestClient(unittest.TestCase):
    def setUp(self):
        self.pre = pre_from_algorithm(default_algorithm)
        self.symm = symmetric_from_algorithm(default_algorithm)
        self.priv_key = self.pre.gen_priv(dtype='bytes')
        self.pub_key = self.pre.priv2pub(self.priv_key)

        self.client = Client()

    def test_derive_path_key(self):
        path = b'/foo/bar'
        pub_path_key = self.client._derive_path_key(path, is_pub=True)
        self.assertEqual(bytes, type(pub_path_key))

        priv_path_key = self.client._derive_path_key(path, is_pub=False)
        self.assertEqual(bytes, type(priv_path_key))

        self.assertNotEqual(pub_path_key, priv_path_key)

    def test_split_path_with_path(self):
        path = b'/foo/bar/test.jpg'
        subdirs = self.client._split_path(path)

        self.assertEqual(4, len(subdirs))
        self.assertEqual(subdirs[0], b'')
        self.assertEqual(subdirs[1], b'/foo')
        self.assertEqual(subdirs[2], b'/foo/bar')
        self.assertEqual(subdirs[3], b'/foo/bar/test.jpg')

    def test_build_header_prealpha(self):
        enc_keys = [random(148), random(148), random(148)]
        version = 100
        header, length = self.client._build_header(enc_keys, version=version)

        self.assertEqual(len(header), length)
        try:
            msgpack.loads(header)
        except Exception as E:
            self.fail("Failed to unpack header:\n{}".format(E))

        self.assertIn((3).to_bytes(4, byteorder='big'), header)
        for key in enc_keys:
            self.assertIn(key, header)

        self.assertIn(version.to_bytes(4, byteorder='big'), header)

    def test_read_header_prealpha(self):
        enc_keys = [random(148), random(148), random(148)]
        version = 100
        header, length = self.client._build_header(enc_keys, version=version)

        self.assertEqual(len(header), length)
        try:
            msgpack.loads(header)
        except Exception as E:
            self.fail("Failed to unpack header: {}".format(E))

        for key in enc_keys:
            self.assertIn(key, header)

        self.assertIn(version.to_bytes(4, byteorder='big'), header)

        header = self.client._read_header(header)
        self.assertEqual(int, type(header[0]))
        self.assertEqual(100, header[0])
        self.assertEqual(list, type(header[1]))
        self.assertEqual(3, len(header[1]))

        for key in header[1]:
            self.assertIn(key, enc_keys)

    def test_encrypt_key_with_path_tuple(self):
        key = random(32)
        path = b'/foo/bar'

        enc_keys = self.client.encrypt_key(key, path=path)
        self.assertEqual(3, len(enc_keys))
        self.assertTrue(key not in enc_keys)

    def test_encrypt_key_with_path_string(self):
        key = random(32)
        path = b'foobar'

        enc_key = self.client.encrypt_key(key, path=path)
        self.assertNotEqual(key, enc_key)

    def test_encrypt_key_no_path(self):
        key = random(32)

        # Use client's pubkey (implict)
        enc_key_1 = self.client.encrypt_key(key)
        self.assertNotEqual(key, enc_key_1)

        # Use provided pubkey (explicit)
        enc_key_2 = self.client.encrypt_key(key, pubkey=self.pub_key)
        self.assertNotEqual(key, enc_key_2)
        self.assertNotEqual(enc_key_1, enc_key_2)

    def test_decrypt_key_with_path(self):
        key = random(32)
        path = b'/foo/bar'

        enc_keys = self.client.encrypt_key(key, path=path)
        self.assertEqual(3, len(enc_keys))
        self.assertTrue(key not in enc_keys)

        subpaths = self.client._split_path(path)
        self.assertEqual(3, len(subpaths))

        # Check each path key works for decryption
        for idx, enc_key in enumerate(enc_keys):
            dec_key = self.client.decrypt_key(enc_key, path=subpaths[idx])
            self.assertEqual(key, dec_key)

    def test_decrypt_key_no_path(self):
        key = random(32)

        enc_key = self.client.encrypt_key(key)
        self.assertNotEqual(key, enc_key)

        dec_key = self.client.decrypt_key(enc_key)
        self.assertEqual(key, dec_key)

    def test_encrypt_bulk(self):
        test_data = b'hello world!'
        key = random(32)

        enc_data = self.client.encrypt_bulk(test_data, key)
        self.assertNotEqual(test_data, enc_data)

    def test_decrypt_bulk(self):
        test_data = b'hello world!'
        nonce_size_bytes = 24
        key = random(32)

        enc_data = self.client.encrypt_bulk(test_data, key)
        self.assertNotEqual(test_data, enc_data)
        # Test that the ciphertext is >24 bytes for nonce
        self.assertTrue(len(enc_data) > nonce_size_bytes)

        dec_data = self.client.decrypt_bulk(enc_data, key)
        self.assertEqual(test_data, dec_data)
