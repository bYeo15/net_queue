'''
    Minimal example of a root server (root in the queue tree)
'''

import random

from net_queue_server import NetQueueServer, ClientConn
from protocol import MsgTypes, create_msg

class RootServerQueue(NetQueueServer):
    def __init__(self, config_file: str = "./server_conf"):
        '''
            Trivial __init__ wrapper that automatically sets the correct client type
        '''
        super().__init__(client_type=ClientConn, config_file=config_file)
        self.bind(self.config["hostname"], self.config["port"])


    def load_config(self, config_file: str):
        '''
            Dummy load config, just sets values to default
        '''
        self.config["port"] = 8080
        self.config["hostname"] = "localhost"

    
    def choose_dispatch(self) -> ClientConn | None:
        '''
            Randomly selects a client to message
        '''
        if self.clients:
            return random.choice(self.clients)
        return None


    def main(self):
        '''
            Main function for single loop of server
        '''
        # If ready but without client, block until a client is available
        if self.state == "ready":
            self.accept_connections(block=True)
        # Otherwise, run main loop
        else:
            # Accept connections (non-blocking)
            self.accept_connections()

            # Enqueue message to single client
            self.put(create_msg(MsgTypes.ENQUEUE, "hello from server"))
            
            # Block until any message is received
            msg = self.get(block=True, timeout=None)

            print(msg)


if __name__ == "__main__":
    serv = RootServerQueue()

    while True:
        try:
            serv.main()
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(e)

    serv.close()
