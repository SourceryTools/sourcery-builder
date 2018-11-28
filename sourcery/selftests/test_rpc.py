# Test sourcery.rpc.

# Copyright 2018 Mentor Graphics Corporation.

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as
# published by the Free Software Foundation; either version 2.1 of the
# License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.

# You should have received a copy of the GNU Lesser General Public
# License along with this program; if not, see
# <https://www.gnu.org/licenses/>.

"""Test sourcery.rpc."""

import os
import os.path
import tempfile
import unittest

from sourcery.rpc import send_message, RPCServer

__all__ = ['RPCTestCase']


class RPCTestCase(unittest.TestCase):

    """Test the RPC mechanism."""

    def setUp(self):
        """Set up an RPC test."""
        self.sockdir_td = tempfile.TemporaryDirectory()
        self.sockdir = self.sockdir_td.name
        self.testdir_td = tempfile.TemporaryDirectory()
        self.testdir = self.testdir_td.name
        self.server_running = False
        self.server = RPCServer(self.sockdir)
        self.rpc_test_var = 0
        self.clean_fds = set()

    def temp_file(self, name):
        """Return the name of a temporary file for this test."""
        return os.path.join(self.testdir, name)

    def temp_file_write(self, name, contents):
        """Write to a temporary file for this test."""
        with open(self.temp_file(name), 'w', encoding='utf-8') as file:
            file.write(contents)

    def temp_file_read(self, name):
        """Read a temporary file for this test."""
        with open(self.temp_file(name), 'r', encoding='utf-8') as file:
            return file.read()

    def temp_file_exists(self, name):
        """Return whether a temporary file exists for this test."""
        return os.access(self.temp_file(name), os.F_OK)

    def tearDown(self):
        """Tear down an RPC test."""
        for fd_no in self.clean_fds:
            os.close(fd_no)
        if self.server_running:
            self.server.stop()
        self.sockdir_td.cleanup()
        self.testdir_td.cleanup()

    def test_start_stop(self):
        """Test starting and stopping a server."""
        # Set up a pipe to use to make sure server really has stopped.
        read_fd, write_fd = os.pipe()
        os.close(write_fd)
        self.clean_fds.add(read_fd)
        self.server.start()
        self.server_running = True
        self.server.stop()
        self.server_running = False
        os.read(read_fd, 1)

    def test_handlers(self):
        """Test running message handlers."""

        def handler_1(self, arg):
            """Test handler."""
            self.temp_file_write('out1', str(self.rpc_test_var))
            self.rpc_test_var = arg

        def handler_2(self, arg1, arg2):
            """Test handler."""
            self.temp_file_write('out2', str(self.rpc_test_var))
            self.rpc_test_var = arg1 - arg2

        def handler_3(self, arg):
            """Test handler."""
            self.temp_file_write('out3', str(self.rpc_test_var))
            self.rpc_test_var = arg

        req1 = self.server.add_call(handler_1, [self, 1],
                                    self.temp_file('log1'), False)
        req2 = self.server.add_call(handler_2, [self, 5, 20],
                                    self.temp_file('log2'), True)
        req3 = self.server.add_call(handler_3, [self, 4],
                                    self.temp_file('log3'), False)
        self.server.start()
        self.server_running = True
        self.assertFalse(self.temp_file_exists('out1'))
        self.assertFalse(self.temp_file_exists('out2'))
        self.assertFalse(self.temp_file_exists('out3'))
        self.assertFalse(self.temp_file_exists('log1'))
        self.assertFalse(self.temp_file_exists('log2'))
        self.assertFalse(self.temp_file_exists('log3'))
        ret = send_message(self.sockdir, req1)
        self.assertEqual(ret, 0)
        self.assertTrue(self.temp_file_exists('out1'))
        self.assertEqual(self.temp_file_read('out1'), '0')
        self.assertFalse(self.temp_file_exists('out2'))
        self.assertFalse(self.temp_file_exists('out3'))
        self.assertFalse(self.temp_file_exists('log1'))
        self.assertFalse(self.temp_file_exists('log2'))
        self.assertFalse(self.temp_file_exists('log3'))
        ret = send_message(self.sockdir, req2)
        self.assertEqual(ret, 0)
        self.assertTrue(self.temp_file_exists('out1'))
        self.assertEqual(self.temp_file_read('out1'), '0')
        self.assertTrue(self.temp_file_exists('out2'))
        self.assertEqual(self.temp_file_read('out2'), '1')
        self.assertFalse(self.temp_file_exists('out3'))
        self.assertFalse(self.temp_file_exists('log1'))
        self.assertFalse(self.temp_file_exists('log2'))
        self.assertFalse(self.temp_file_exists('log3'))
        ret = send_message(self.sockdir, req3)
        self.assertEqual(ret, 0)
        self.assertTrue(self.temp_file_exists('out1'))
        self.assertEqual(self.temp_file_read('out1'), '0')
        self.assertTrue(self.temp_file_exists('out2'))
        self.assertEqual(self.temp_file_read('out2'), '1')
        self.assertTrue(self.temp_file_exists('out3'))
        self.assertEqual(self.temp_file_read('out3'), '1')
        self.assertFalse(self.temp_file_exists('log1'))
        self.assertFalse(self.temp_file_exists('log2'))
        self.assertFalse(self.temp_file_exists('log3'))
        self.server.stop()
        self.server_running = False

    def test_handler_exceptions(self):
        """Test exceptions in message handlers."""

        def handler_1():
            """Test handler."""
            raise ValueError('test exception from handler')

        def handler_2():
            """Test handler."""
            raise ValueError('other exception from handler')

        req1 = self.server.add_call(handler_1, [],
                                    self.temp_file('log1'), False)
        req2 = self.server.add_call(handler_2, [],
                                    self.temp_file('log2'), True)
        self.server.start()
        self.server_running = True
        self.assertFalse(self.temp_file_exists('log1'))
        self.assertFalse(self.temp_file_exists('log2'))
        ret = send_message(self.sockdir, req1)
        self.assertEqual(ret, 1)
        self.assertTrue(self.temp_file_exists('log1'))
        self.assertFalse(self.temp_file_exists('log2'))
        self.assertRegex(self.temp_file_read('log1'),
                         'ValueError.*test exception')
        ret = send_message(self.sockdir, req2)
        self.assertEqual(ret, 1)
        self.assertTrue(self.temp_file_exists('log1'))
        self.assertTrue(self.temp_file_exists('log2'))
        self.assertRegex(self.temp_file_read('log2'),
                         'ValueError.*other exception')

    def test_startup(self):
        """Test start method only returns when server ready."""

        def handler(self):
            """Test handler."""
            self.temp_file_write('out', 'run')

        req = self.server.add_call(handler, [self],
                                   self.temp_file('log'), False)
        self.server._sleep = 0.5
        self.server.start()
        self.server_running = True
        self.assertFalse(self.temp_file_exists('out'))
        self.assertFalse(self.temp_file_exists('log'))
        ret = send_message(self.sockdir, req)
        self.assertEqual(ret, 0)
        self.assertTrue(self.temp_file_exists('out'))
        self.assertEqual(self.temp_file_read('out'), 'run')
        self.assertFalse(self.temp_file_exists('log'))
        self.server.stop()
        self.server_running = False
