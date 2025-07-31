'''
    Client end of a networked queue

    Handles a connection to a single server

    PUT: Send response upward to parent
    GET: Retrieve job from parent
'''


import socket
import time
import selectors
import struct
from queue import Empty, Full

from abc import ABC, abstractmethod

from protocol import MsgTypes, decode_msg, create_msg


class NetQueueClient(ABC):
    '''
        Abstract client end for the network queue

        Users must provide "load_config" method
        Users should replace "get_status" "handle_sv_status" 
        and "handle_sv_enqueue" to suit their needs
        
        TODO : Use state to handle errors/prevent premature usage
    '''

    def __init__(self, config_file: str= "./client_conf"):
        # [List<str>] - local backlog of received messages
        self.local_queue = []

        # [socket] - client connection socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # [DefaultSelector] - selector on server connection
        self.server_sel = selectors.DefaultSelector()

        # [str] - state of the client
        #   "inactive" : yet to connect
        #   "connected" : connected to server
        self.state = "inactive"

        # [Dict<str><*>] - dictionary of config values
        #   Comes with some default values (see below)
        self.config = {
            # [int] - maximum number of bytes to be recv'd at once
            "max_recv_size": 4096,
            
        }

        self.load_config(config_file)


    @abstractmethod
    def load_config(self, config_file: str):
        '''
            Handles loading the configuration for the client
            into the "config" dict
        '''
        return NotImplemented


    def get_status(self) -> str | None:
        '''
            Returns a string describing the status of this client
            Alternatively, can return None to prevent sending statuses
        '''
        return None


    def connect(self, addr: str, port: int):
        '''
            Connects the client to a given server
            Sends a connection message that broadcasts the number of workers
        '''
        self.sock.connect((addr, port))
        self.sock.setblocking(False)
        self.server_sel.register(self.sock, selectors.EVENT_READ, self.handle_sv_msg)

        self.put(create_msg(MsgTypes.CONN))


    def poll(self, block: bool = False, timeout: int | float | None = None):
        '''
            Polls the client's connection
        '''
        server_events = self.server_sel.select(timeout=0 if not block else timeout)
        for key, mask in server_events:
            callback = key.data
            callback(key.fileobj)

    
    def get(self, block: bool = True, timeout: int | None = None):
        '''
            Attempts to retrieve an enqueued value from the client's connection
        '''
        if not block:
            self.poll(block=False)
            if self.local_queue:
                return self.local_queue.pop(0)
            raise Empty("Queue has no available items, and blocking is disabled")

        timeout_remaining = timeout

        while not self.local_queue and (timeout_remaining is None or timeout_remaining > 0.0):
            poll_time = time.time()

            self.poll(block=True, timeout=timeout_remaining)

            if timeout_remaining is not None:
                timeout_remaining -= (time.time() - poll_time)

        if self.local_queue:
            return self.local_queue.pop(0)
        raise Empty(f"Queue failed to retrieve an item within timeout {timeout}s")


    def get_all(self):
        '''
            Retrieves all currently available messages
        '''
        self.poll(block=False)
        res = self.local_queue
        self.local_queue = []
        return res


    def put(self, msg: bytes):
        '''
            Sends a message to the connected server
        '''
        self.sock.sendall(msg)


    def close(self, signal_disconn: bool = True):
        '''
            Closes the client and cleans up open resources
            Signals server that this client is disconnecting
        '''
        if signal_disconn:
            self.put(create_msg(MsgTypes.DISCONN))
        
        self.server_sel.close()

        self.sock.close()


    def handle_sv_msg(self, sock):
        msg_handlers = {
            MsgTypes.CONN: self.handle_sv_conn,
            MsgTypes.DISCONN: self.handle_sv_disconn,
            MsgTypes.STATUS: self.handle_sv_status,
            MsgTypes.PING: self.handle_sv_ping,
            MsgTypes.PONG: self.handle_sv_pong,
            MsgTypes.ENQUEUE: self.handle_sv_enqueue,
        }

        # Get message length
        msg_len = struct.unpack("!i", sock.recv(4))[0]
        
        # Receive full message
        msg_fragments = []

        while msg_len > 0:
            frag = sock.recv(min(self.config["max_recv_size"], msg_len))
            if frag:
                msg_len -= len(frag)
                msg_fragments.append(frag)

        msg = b''.join(msg_fragments)

        msg_type, msg_data = decode_msg(msg)

        if msg_type in msg_handlers:
            msg_handlers[msg_type](msg_data)
        else:
            print("[ ERROR ] : Server sent invalid message")


    def handle_sv_conn(self, data):
        '''
            CONN : Note connected state and send initial status
        '''
        self.state = "connected"
        status = self.get_status()
        if status is not None:
            self.put(create_msg(MsgTypes.STATUS, status))

    def handle_sv_disconn(self, data):
        '''
            DISCONN : Close client
        '''
        self.close(signal_disconn=False)


    def handle_sv_status(self, data):
        '''
            STATUS : Defaults to a no-op
        '''
        pass

    
    def handle_sv_ping(self, data):
        '''
            PING : Respond with PONG
        '''
        self.sock.sendall(create_msg(MsgTypes.PONG))


    def handle_sv_pong(self, data):
        '''
            PONG : Report PONG received
        '''
        print("Got PONG from server")

    
    def handle_sv_enqueue(self, data):
        '''
            ENQUEUE : Defaults to just enqueuing data locally
        '''
        self.local_queue.append(data)
