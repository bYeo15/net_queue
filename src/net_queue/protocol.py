'''
    Definition of the protocol, plus utility functions for serialising/deserialising
    messages

    Messages are provided in the following format:

    Length : 4 byte integer
        The length (in bytes) of the entire message, excluding this field
    Type : 2 byte integer
        Must match one of the below message types. Identifies the message
    Data : See below
        Most messages come with attached data


    | Length | Type | Data ... |
'''

import struct
import json
from enum import Enum


class MsgTypes(Enum):
    '''
        Defines the protocol message types
    '''

    # CONN
    #   Signals client connection
    #   Returned by the server
    CONN = 1

    # DISCONN
    #   Signals client/server disconnect
    DISCONN = 2

    # STATUS <status>
    #   status : string serialised data (dynamic length)
    #       Describes the status of this node
    STATUS = 3

    # PING
    #   Health check message
    PING = 4

    # PONG
    #   Health check response
    PONG = 5

    # ENQUEUE <data>[\n<data>]*
    # data : string serialised data (dynamic length)
    #   "\n" separates data items
    ENQUEUE = 6


def create_msg(type: MsgTypes, *args) -> bytes:
    '''
        Creates a message of the given type
    '''
    creators = {
        MsgTypes.CONN: create_conn_msg,
        MsgTypes.DISCONN: create_disconn_msg,
        MsgTypes.STATUS: create_status_msg,
        MsgTypes.PING: create_ping_msg,
        MsgTypes.PONG: create_pong_msg,
        MsgTypes.ENQUEUE: create_enqueue_msg
    }

    return creators[type](*args)


def create_conn_msg() -> bytes:
    return struct.pack("!ih", 2, MsgTypes.CONN.value)

def create_disconn_msg() -> bytes:
    return struct.pack("!ih", 2, MsgTypes.DISCONN.value)

def create_status_msg(status) -> bytes:
    return struct.pack("!ih", 2 + len(status), MsgTypes.STATUS.value) + status.encode("utf_8")

def create_ping_msg() -> bytes:
    return struct.pack("!ih", 2, MsgTypes.PING.value)

def create_pong_msg() -> bytes:
    return struct.pack("!ih", 2, MsgTypes.PONG.value)


def create_enqueue_msg(*args) -> bytes:
    # 2 for Type + the length of each message + 1 per message past the first (separator)
    msg_len = 2 + sum([len(msg) for msg in args]) + len(args) - 1
    # Create message
    msg_entries = [msg.encode("utf_8") for msg in args]
    return struct.pack("!ih", msg_len, MsgTypes.ENQUEUE.value) + b'\n'.join(msg_entries)


def decode_msg(msg: bytes):
    '''
        Decodes a message, returning a tuple of (type, data)

        Assumes that the message is provided without the length header
    '''
    decoders = {
        MsgTypes.CONN: None,
        MsgTypes.DISCONN: None,
        MsgTypes.STATUS: get_status_data, 
        MsgTypes.PING: None,
        MsgTypes.PONG: None,
        MsgTypes.ENQUEUE: get_enqueued_data,
    }

    # Extract message type from the first 2 bytes
    msg_type = struct.unpack("!h", msg[:2])[0]

    msg_type = MsgTypes(msg_type)

    # Pass the rest to the appropriate decoder, if available
    if decoders[msg_type] is not None:
        return (msg_type, decoders[msg_type](msg[2:]))
    return (msg_type, None)


def get_status_data(msg_data):
    '''
        Extracts the data from a STATUS message
    '''
    return str(msg_data, "utf_8")


def get_enqueued_data(msg_data):
    '''
        Extracts the data from an ENQUEUE message
    '''
    return tuple(str(data, "utf_8") for data in msg_data.split(b'\n'))
