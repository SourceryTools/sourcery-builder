# Support calling Python code in another script.

# Copyright 2018-2019 Mentor Graphics Corporation.

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

"""Support calling Python code in another script."""

import os
import os.path
import signal
import socket
import socketserver
import sys
import time
import traceback

__all__ = ['send_message', 'RPCServer']


def _server_socket(tempdir):
    """Return the path to the server socket for the given directory."""
    return os.path.join(tempdir, 'server')


def send_message(tempdir, req_no):
    """Send a message to the server using a given temporary directory.

    Message 0 means to exit.  For other messages, an integer response
    is received and returned from this function.

    """
    server_socket = _server_socket(tempdir)
    client_socket = os.path.join(tempdir, str(req_no))
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
        sock.bind(client_socket)
        sock.sendto(str(req_no).encode(), server_socket)
        if req_no == 0:
            return 0
        else:
            data, dummy_addr = sock.recvfrom(1024)
            return int(data.decode())


def _write_exc_to_log(name):
    """Write an exception message to a log if possible."""
    try:
        with open(name, 'a', encoding='utf-8') as file:
            traceback.print_exc(file=file)
    except Exception:  # pylint: disable=broad-except
        # There is nothing useful we can do when writing the logs
        # fail, but we do not want outer exception handlers to run in
        # the child process.
        pass


class _RPCServerHandler(socketserver.BaseRequestHandler):
    """Process a message to run code in this script (implementation)."""

    def handle(self):
        data = self.request[0]
        req_socket = self.request[1]
        req_no = int(data.decode())
        if req_no == 0:
            # Request to exit; do not fork, and do not allow socket
            # server's exception handlers to catch this.
            os._exit(0)
        req_idx = req_no - 1
        rpc = self.server._sourcery_builder_rpc_server
        log = rpc._logs[req_idx]
        forking = rpc._forking[req_idx]
        if forking:
            pid = os.fork()
            run_func = pid == 0
        else:
            # Non-forking requests all run in the same process as the
            # server; for example, they may generate output which
            # should not be interleaved, or update state in the server
            # process.  They should be efficient because other
            # requests cannot start being processed while they are
            # being processed.
            run_func = True
        if run_func:
            status = 0
            try:
                rpc._funcs[req_idx](*rpc._args[req_idx])
            except Exception:  # pylint: disable=broad-except
                status = 1
                _write_exc_to_log(log)
            try:
                req_socket.sendto(str(status).encode(), self.client_address)
            except Exception:  # pylint: disable=broad-except
                _write_exc_to_log(log)
            if forking:
                os._exit(0)


class RPCServer:
    """An RPCServer represents a way to run code in this script.

    Clients send a message to the server, which forks a copy of itself
    to handle each request other than the one to exit and ones
    registered as non-forking.  Requests are integer values registered
    with the server before it is started, and result in a value 0
    (success) or 1 (failure) being returned, with any exception text
    going to a log file registered along with the request.

    This is the high-level class to be used by scripts requiring such
    a server, not an implementation class inheriting from socketserver
    classes.

    """

    def __init__(self, tempdir):
        """Initialize an RPCServer object.

        The specified tempdir (which must have been created by the
        caller) will be used to store sockets for communication.

        """
        self._tempdir = tempdir
        self._server_socket_path = _server_socket(tempdir)
        self._funcs = []
        self._args = []
        self._logs = []
        self._forking = []
        self._pid = None
        # A hook for testing purposes.
        self._sleep = 0

    def add_call(self, func, args, log, forking):
        """Add a call this server will accept."""
        self._funcs.append(func)
        self._args.append(args)
        self._logs.append(log)
        self._forking.append(forking)
        return len(self._funcs)

    def start(self):
        """Start the server in a subprocess."""
        # Set up a pipe to use for the child to signal once it is
        # listening.
        read_fd, write_fd = os.pipe()
        sys.stdout.flush()
        sys.stderr.flush()
        pid = os.fork()
        self._pid = pid
        if pid == 0:
            if self._sleep:
                time.sleep(self._sleep)
            # Ensure children handling requests are automatically
            # reaped.
            signal.signal(signal.SIGCHLD, signal.SIG_IGN)
            server = socketserver.UnixDatagramServer(self._server_socket_path,
                                                     _RPCServerHandler)
            # The server is now listening on the socket, so clients
            # can start sending messages to it.
            os.close(read_fd)
            os.close(write_fd)
            if self._sleep:
                time.sleep(self._sleep)
            # Make this RPCServer object available to the handler.
            server._sourcery_builder_rpc_server = self
            server.serve_forever()
        else:
            os.close(write_fd)
            # This will return once the pipe has been closed in the
            # child, once it is ready to receive messages.
            os.read(read_fd, 1)

    def stop(self):
        """Stop the server in a subprocess."""
        send_message(self._tempdir, 0)
        os.waitpid(self._pid, 0)
