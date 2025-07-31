# Net Queue

Provides a simple network-based queue system, where messages are sent though a tree of nodes.

Both queues are abstract, requiring a small layer on top of the existing code to handle user-specific details.

The queues are designed to be integrated into existing code, and thus do not provide their own main loop.


<TODO : Client/Server state>


## Protocol

The protocol uses a very simple packet structure:
```
| Length < 4 byte integer > | Type < 2 byte integer > | Data <...> |
```

`Length` should be the length of the packet, excluding the `Length` field.
`Type` should be the integer associated with one of the below message types.
`Data` should be the per-message-type data.

The message types can be accessed from `protocol.MsgTypes.<type>`.

### Message Types:
- `CONN` - Connection signal
- `DISCONN` - Disconnection signal
- `STATUS <status>` - Status information, sends arbitrary data in `<status>`
- `PING` - Health check request
- `PONG` - Health check response
- `ENQUEUE <data>[\n<data>]*` - Sends a group of data to be enqueued. By default, distinct pieces of data (ie. strings to be separated) are separated with newlines.

Messages can be created with `protocol.create_msg(type: MsgTypes, *args)`, where `args` provides any data to be attached to the message.



## Net Queue Client

The client connects to a single parent server.

A client is passed a config file path in its initialiser (ie. `<YourClientClass>(config_file="<path here>")`). The path defaults to `./client_conf`.

### Exposed Methods:
- `connect(addr: str, port: int)` - Attempts to connect to the given address and port.
- `poll(block: bool = False, timeout: int | float | None = None)` - Polls the client's connection. If `block` is `False`, will only handle immediately available messages. If `block` is `True`, will wait up to `timeout` seconds (indefinitely if `timeout` is `None`) until at least one message is available. Nothing occurs if the timeout is elapsed. Note that the message received may not be an `ENQUEUE` message. `poll` is wrapped by other functions, and typically does not have to be called on its own.
- `get(block: bool = True, timeout: int | None = None)` - Retrieves an enqueued piece of data from the client. Uses the same blocking logic as `poll`, with the caveat that it WILL block until something is enqueued. Raises `Empty` if no data is available.
- `get_all()` - Retrieves all immediately available messages.
- `put(msg: bytes)` - Sends the given message to the server the client is connected to.
- `close(signal_disconn: bool = True)` - Closes the client. If `signal_disconn` is `True`, sends a `DISCONN` message to the server first. Otherwise, does not (useful in cases where the server is already disconnected).

### User-Defined Methods:
- `load_config(self, config_file: str)` - **REQUIRED**, should load config data from the given file into the `self.config` dictionary. Note that this dictionary uses some pre-defined values (see Config section).
- `get_status(self) -> str | None` - Defaults to returning `None`. Should either return `None` (in which case no status messages are sent) or a string representing the status of this client.
- `handle_sv_status(self, data)` - Defaults to a no-op. Should handle the server's status data (received as a string) to control the client's behaviour.
- `handle_sv_enqueue(self, data)` - Defaults to just loading the data (as a string) into the local queue. Can be extended to (for example) update client status or deserialise the data. Should make use of the `self.local_queue` list whenever something is being enqueued to the client (which is used by `get`, `get_all`, etc.).



## Net Queue Server

The server manages a pool of clients to which it can dispatch messages.

A server is passed a client type and a config file path in its initialiser (ie. `<YourServerClass>(client_type=<YourClientClass>, config_file="<path_here>")`). The path defaults to `./server_conf`.

Associated with the server is the "`ClientConn`" class, which is a simple wrapper on a socket that stores status related data. Any subclass of `ClientConn` should provide an `__init__` function that accepts a socket object (the socket associated with that client) and loads default status values. Its status can later be loaded from a `STATUS` message.
If no status data is required, the `ClientConn` class can be used as-is.

### Exposed Methods:
- `bind(addr: str, port: int)` - Binds the server to the provided port and address. 
- `poll(self, block: bool = False, timeout: int | float | None = None)` - Polls the server's connetions to its client for new messages. Uses the same blocking logic as the client (see above). As with the client, this is wrapped by other methods, and typically does not have to be called on its own.
- `accept_connections(block: bool = False, timeout: int | None = None)` - Polls the server's socket for connection attempts. Uses the same blocking logic as `poll`.
- `get(block: bool = True, timeout: int | None = None, allow_none: bool = True)` - Retrieves an enqueued piece of data from the server. Uses the same blocking logic as the client (see above). If `allow_none` is `True`, returns `None` if no data is available. Otherwise, raises `Empty`.
- `get_all()` - Retrieves all immediately available messages.
- `put(msg: bytes, block: bool = False, timeout: int | None = None, send_all: bool = False)` - Sends the given message. If `send_all` is `True`, the message is sent to all clients. If `send_all` if `False`, uses `choose_dispatch` (see below) to select one connected client and send the message to that client. If `block` is `False`, will raise `Full` if no clients are available. If `block` is `True`, will wait up to `timeout` seconds (indefinitely if `timeout` is `None`) for a client to become available (during this time, the server will `poll`, but will not accept new connections). If the timeout is elapsed, will raise `Full`.
- `close()` - Closes the server. Signals all connected clients with `DISCONN`.

### User-Defined Methods:
- `load_config(self, config_file: str)` - **REQUIRED**, should load config data from the given file into the `self.config` dictionary. Note that this dictionary uses some pre-defined values (see Config section).
- `choose_dispatch(self)` - **REQUIRED**, should select and return a client object from among `self.clients` to dispatch a message to. May also update that client's status to reflect this dispatch. If no clients are available, returns `None`.
- `get_status(self) -> str | None` - Defaults to returning `None`. Should either return `None` (in which case no status messages are sent) or a string representing the status of this server. By default, server status is never used.
- `handle_cl_status(self, client, data)` - Defaults to a no-op. Should handle the client's status data (received as a string), updating the provided `client` object (an instance of the chose `client_type`).
- `handle_cl_enqueue(self, client, data)` - Defaults to just loading the data (as a string) into the local queue. Can be extended to (for example) update client status or deserialise the data. Should make use of the `self.local_queue` list whenever something is being enqueued to the server (which is used by `get`, `get_all`, etc.).


## Config

<TODO>
