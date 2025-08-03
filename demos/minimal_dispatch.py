'''
    Minimal example of a dispatch node (internal node in the queue tree,
    consists of a client and server)
'''

import random
import sys

from net_queue_client import NetQueueClient
from net_queue_server import NetQueueServer, ClientConn
from protocol import MsgTypes, create_msg

class DispatchClientQueue(NetQueueClient):
    def __init__(self, port: int, config_file: str = "./client_conf"):
        '''
            Trivial __init__ wrapper that allows selecting a port
        '''
        super().__init__(config_file=config_file)
        self.client_id = random.randint(1000, 2000)
        self.config["port"] = port
        self.connect(self.config["hostname"], self.config["port"])


    def load_config(self, config_file: str):
        '''
            Dummy load config, just sets values to default
        '''
        self.config["hostname"] = "localhost"
        

class DispatchServerQueue(NetQueueServer):
    def __init__(self, port: int, config_file: str = "./server_conf"):
        '''
            Trivial __init__ wrapper that automatically sets the correct client type
            and allows selecting a port
        '''
        super().__init__(client_type=ClientConn, config_file=config_file)
        self.config["port"] = port
        self.bind(self.config["hostname"], self.config["port"])


    def load_config(self, config_file: str):
        '''
            Dummy load config, just sets values to default
        '''
        self.config["hostname"] = "localhost"


    def choose_dispatch(self) -> ClientConn | None:
        '''
            Randomly selects a client to message
        '''
        if self.clients:
            return random.choice(self.clients)
        return None


class DispatchNode():
    '''
        Wrapper on a client, server pair for a dispatch node
    '''
    def __init__(self, client: NetQueueClient, server: NetQueueServer):
        self.server = server
        self.client = client


    def main(self):
        '''
            Main function for single loop of dispatch
        '''
        # Accept new client connections (block if no client yet)
        if self.server.state == "ready":
            self.server.accept_connections(block=True)
        else:
            self.server.accept_connections()

            # Get a message from parent server
            # Non-blocking (1s wait), no error on failure
            msg = self.client.get(block=True, timeout=1, allow_none=True)

            # Forward message to clients
            if msg is not None:
                print(msg)
                self.server.put(create_msg(MsgTypes.ENQUEUE, msg[0]))
            
            # Get responses from clients
            resps = self.server.get_all()

            # Forward responses back to parent
            for resp in resps:
                print(resp)
                self.client.put(create_msg(MsgTypes.ENQUEUE, resp[0]))


    def close(self):
        self.server.close()
        self.client.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    
    client = DispatchClientQueue(int(args[0]))
    serv = DispatchServerQueue(int(args[1]))
    dispatch = DispatchNode(client, serv)

    while True:
        try:
            dispatch.main()
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(e)

    dispatch.close()
