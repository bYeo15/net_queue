'''
    Network queue server end

    Handles a group of connected clients

    PUT: Dispatch a message down to a client (can be set to dispatch to all or just one)
    GET: Retrieves enqueued responses
'''

import socket
import time
import selectors
import struct
from queue import Empty, Full

from typing import Any
from abc import ABC, abstractmethod

from protocol import MsgTypes, decode_msg, create_msg 


class ClientConn():
    '''
        Wrapper on a client's socket, intended to be subclassed to include
        status data

        Expects an init that;
            - Accepts a socket as it's only argument and passes this up to
              super().__init()
            - Loads default values for status information 
              (to be updated by a STATUS message)
    '''
    def __init__(self, sock: socket.socket):
        # [socket] - the socket associated with this client connection
        self.sock = sock

    def sendall(self, data):
        self.sock.sendall(data)

    def recv(self, n_bytes: int):
        return self.sock.recv(n_bytes)

    def close(self):
        self.sock.close()


class NetQueueServer(ABC):
    '''
        Abstract server end for the network queue

        Users must provide "load_config" and "choose_dispatch" methods
        Users should replace "get_status", "handle_cl_status"
        and "handle_cl_enqueue" to suit their needs

        TODO: Use state to handle events/prevent premature usage
        TODO: Local put waiting queue
    '''
    
    def __init__(self, client_type: type, config_file: str = "./server_conf"):
        # [List<*>] - local backlog of received messages
        self.local_queue = []

        # [socket] - server socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # [DefaultSelector] - selector on connection attempts
        self.conn_sel = selectors.DefaultSelector()

        # [List<ClientConn>] - list of connected clients
        self.clients = []

        # [DefaultSelector] - selector on connected clients
        self.client_sel = selectors.DefaultSelector()

        # [str] - state of the server
        #   "inactive" : yet to be bound
        #   "ready" : bound with no clients
        #   "connected" : bound with clients
        self.state = "inactive"

        # [type] - the type of client object to use
        self.client_type = client_type

        # [Dict<str><*>] - dictionary of config values
        #   Comes with some default values (see below)
        self.config : dict[str, Any] = {
            # [int] - maximum number of bytes to be recv'd at once
            "max_recv_size": 4096,
        }

        self.load_config(config_file)


    @abstractmethod
    def load_config(self, config_file: str): 
        '''
            Handles loading the configuration for the server
            into the "config" dict
        '''
        raise NotImplementedError()


    @abstractmethod
    def choose_dispatch(self) -> ClientConn | None:
        '''
            Handles the selection of a client from self.clients to
            send a message to

            Returns None if no clients are available
        '''
        raise NotImplementedError()


    def get_status(self) -> str | None:
        '''
            Returns a string describing the status of this client
            Alternatively, can return None to prevent sending statuses
        '''
        return None


    def bind(self, addr: str, port: int):
        '''
            Binds the server to a given port and address
        '''
        self.sock.bind((addr, port))
        self.sock.listen(5)
        self.sock.setblocking(False)
        self.conn_sel.register(self.sock, selectors.EVENT_READ)
        self.state = "ready"


    def poll(self, block: bool = False, timeout: int | float | None = None):
        '''
            Polls the server's connection(s) for new messages
        '''
        client_events = self.client_sel.select(timeout=0 if not block else timeout)
        for key, mask in client_events:
            self.handle_cl_msg(key.data)


    def accept_connections(self, block: bool = False, timeout: int | None = None):
        '''
            Polls the server for new connections
        '''
        conn_events = self.conn_sel.select(timeout=0 if not block else timeout)
        for key, mask in conn_events:
            self.conn_accept()


    def conn_accept(self):
        '''
            Accepts a connection from a client
        '''
        # TODO - accept timeout
        conn, addr = self.sock.accept()
        conn.setblocking(False)
        client = ClientConn(conn)
        self.clients.append(client)
        self.client_sel.register(conn, selectors.EVENT_READ, client)

    
    def get(self, block: bool = True, timeout: int | None = None, allow_none: bool = True):
        '''
            Tries to retrieve an item from the queue

            If block is False, will only handle immediately available network messages
            If block is True, and timeout is a positive integer, will wait up to timeout seconds
            to enqueue an item
            If block is True, and timeout is None, will wait indefinitely until an item is enqueued

            If allow_none is True, will return None rather than throwing an error for an empty queue
        '''
        # Always perform an initial non-blocking poll
        self.poll(block=False)

        if not block:
            if self.local_queue:
                return self.local_queue.pop(0)
            if allow_none:
                return None
            raise Empty("Queue has no available items, and blocking is disabled")

        timeout_remaining = timeout

        # Loop until either an item has been enqueued, or the timeout is elapsed
        while not self.local_queue and (timeout_remaining is None or timeout_remaining > 0.0):
            poll_time = time.time()
            
            self.poll(block=True, timeout=timeout_remaining)

            if timeout_remaining is not None:
                timeout_remaining -= (time.time() - poll_time)

        if self.local_queue:
            return self.local_queue.pop(0)
        if allow_none:
            return None
        raise Empty(f"Queue failed to retrieve an item within timeout {timeout}s")


    def get_all(self):
        '''
            Retrieves all currently available items
        '''
        self.poll(block=False)
        res = self.local_queue
        self.local_queue = []
        return res


    def put(self, msg, block: bool = False, timeout: int | None = None, send_all: bool = False):
        '''
            Dispatches a message, either to a single client (default)
            or to all clients

            If sending to a single client, decrements its available workers

            If block is False, will fail if no clients are available
            If block is True, and timeout is a positive integer, will wait up to timeout seconds
            for a client to become available
            If block is True, and timeout is None, will wait indefinitely until a client is available

            Note that the queue will poll while waiting - this can result in new data being enqueued
            locally
        '''
        if send_all:
            for client in self.clients:
                client.sendall(msg)
        else:
            timeout_remaining = timeout
            while not self.clients or self.clients[0].avail_workers <= 0:
                if not block or (timeout_remaining is not None and timeout_remaining <= 0.0):
                    raise Full("No available clients to put message to")
                poll_start = time.time()

                self.poll(block=True, timeout=timeout_remaining)

                if timeout_remaining is not None:
                    timeout_remaining -= (time.time() - poll_start)

            target = self.choose_dispatch()
            if target: 
                target.sendall(msg)
            else:
                raise Full("No available clients to put message to")


    def close(self):
        '''
            Closes the server and cleans up open resources
            Signals all connected clients that the server is disconnecting
        '''
        # Signal all clients to tell them the server is closing
        self.put(create_msg(MsgTypes.DISCONN), send_all=True)
    
        # Close selectors
        self.conn_sel.close()
        self.client_sel.close()

        # Close client connections
        for client in self.clients:
            client.close()

        self.clients = []

        self.sock.close()


    def handle_cl_msg(self, client):
        msg_handlers = {
            MsgTypes.CONN: self.handle_cl_conn,
            MsgTypes.DISCONN: self.handle_cl_disconn,
            MsgTypes.STATUS: self.handle_cl_status,
            MsgTypes.PING: self.handle_cl_ping,
            MsgTypes.PONG: self.handle_cl_pong,
            MsgTypes.ENQUEUE: self.handle_cl_enqueue,
        }

        # Get message length
        msg_len_b = client.recv(4)
        msg_len = struct.unpack("!i", msg_len_b)[0]
        
        # Receive full message
        msg_fragments = []

        while msg_len > 0:
            frag = client.recv(min(self.config["max_recv_size"], msg_len))
            if frag:
                msg_len -= len(frag)
                msg_fragments.append(frag)

        msg = b''.join(msg_fragments)

        msg_type, msg_data = decode_msg(msg)

        if msg_type in msg_handlers:
            msg_handlers[msg_type](client, msg_data)
        else:
            print("[ ERROR ] : Client sent invalid message")


    def handle_cl_conn(self, client, data):
        '''
            CONN : Respond with CONN 
        '''
        client.sendall(create_msg(MsgTypes.CONN))


    def handle_cl_disconn(self, client, data):
        '''
            DISCONN : Remove client and resort worker pool
        '''
        self.clients.remove(client)
        client.close()


    def handle_cl_status(self, client, data):
        '''
            STATUS : Defaults to a no-op
        '''
        pass

    
    def handle_cl_ping(self, client, data):
        '''
            PING : Respond with PONG
        '''
        client.sendall(create_msg(MsgTypes.PONG))


    def handle_cl_pong(self, client, data):
        '''
            PONG : Report PONG received
        '''
        print(f"Got PONG from client {client}")

    
    def handle_cl_enqueue(self, client, data):
        '''
            ENQUEUE : Defaults to just enqueuing data locally
        '''
        self.local_queue.append(data)

