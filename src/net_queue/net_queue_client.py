'''
    Client end of a networked queue

    Handles a connection to a single server
'''


import socket
import time
import selectors
import struct

from queue import Empty
from collections.abc import Sequence

from protocol import MsgTypes, decode_msg, create_msg
from errors import QueueStateMismatch


class NetQueueClient():
    '''
        Client end for the network queue
    '''

    # [object] - state singletons
    INACTIVE = object()     # Yet to be connected
    CONNECTED = object()    # Connected to server
    CLOSED = object()       # Closed - cannot be reused

    def __init__(self):
        # [List<str>] - local backlog of received messages
        self.local_queue = []

        # [socket] - client connection socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # [DefaultSelector] - selector on server connection
        self.server_sel = selectors.DefaultSelector()

        # [object] - state of the client (see above)
        self.state = NetQueueClient.INACTIVE 


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
        if self.state is not NetQueueClient.INACTIVE:
            raise QueueStateMismatch("Cannot connect an already connected client")

        self.sock.settimeout(10)
        self.sock.connect((addr, port))
        self.sock.setblocking(False)
        self.server_sel.register(self.sock, selectors.EVENT_READ, self.handle_sv_msg)
        self.state = NetQueueClient.CONNECTED

        self.put(create_msg(MsgTypes.CONN))


    def poll(self, block: bool = False, timeout: int | float | None = None):
        '''
            Polls the client's connection
        '''
        if self.state is not NetQueueClient.CONNECTED:
            raise QueueStateMismatch("Cannot poll a client until it is connected")

        server_events = self.server_sel.select(timeout=0 if not block else timeout)
        for key, mask in server_events:
            callback = key.data
            callback(key.fileobj)

    
    def get(self, block: bool = True, timeout: int | None = None, allow_none: bool = False):
        '''
            Attempts to retrieve an enqueued value from the client's connection
        '''
        if self.state is not NetQueueClient.CONNECTED:
            raise QueueStateMismatch("Cannot get from a client until it is connected")

        if not block:
            self.poll(block=False)
            if self.local_queue:
                return self.local_queue.pop(0)
            if allow_none:
                return None
            raise Empty("Queue has no available items, and blocking is disabled")

        timeout_remaining = timeout

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
            Retrieves all currently available messages
        '''
        if self.state is not NetQueueClient.CONNECTED:
            raise QueueStateMismatch("Cannot get from a client until it is connected")
        
        self.poll(block=False)
        res = self.local_queue
        self.local_queue = []
        return res


    def put(self, msg):
        '''
            Sends a message to the connected server

            Attempts simple data serialisation for msg
        '''
        if self.state is not NetQueueClient.CONNECTED:
            raise QueueStateMismatch("Cannot put to a client until it is connected")

        bmsg = msg

        if not isinstance(msg, bytes):
            if not isinstance(msg, str) and isinstance(msg, Sequence):
                # Try to unpack Sequence-style data
                bmsg = create_msg(MsgTypes.ENQUEUE, *msg)
            else:
                # Otherwise, assume data is a string
                bmsg = create_msg(MsgTypes.ENQUEUE, msg)


        self.sock.sendall(bmsg)


    def close(self, signal_disconn: bool = True):
        '''
            Closes the client and cleans up open resources
            Signals server that this client is disconnecting
        '''
        if signal_disconn:
            self.put(create_msg(MsgTypes.DISCONN))
        
        self.server_sel.close()

        self.sock.close()

        self.state = NetQueueClient.CLOSED


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
            frag = sock.recv(min(4096, msg_len))
            if frag:
                msg_len -= len(frag)
                msg_fragments.append(frag)
            else:
                raise ConnectionResetError(f"Lost connection during recv of total length {msg_len}, got partial msg {msg_fragments}")

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
        self.state = NetQueueClient.CONNECTED
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
