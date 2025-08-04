'''
    Minimal example of a dispatch node (internal node in the queue tree,
    consists of a client and server)
'''

import sys

from net_queue_client import NetQueueClient
from net_queue_server import NetQueueServer

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
        if self.server.state is NetQueueServer.READY:
            self.server.accept_connections(block=True)
        else:
            self.server.accept_connections()

            # Get a message from parent server
            # Non-blocking (1s wait), no error on failure
            msg = self.client.get(block=True, timeout=1, allow_none=True)

            # Forward message to clients
            if msg is not None:
                print(msg)
                self.server.put(msg[0])
            
            # Get responses from clients
            resps = self.server.get_all()

            # Forward responses back to parent
            for resp in resps:
                print(resp)
                self.client.put(resp[0])


    def close(self):
        self.server.close()
        self.client.close()


if __name__ == "__main__":
    args = sys.argv[1:]

    if len(args) != 2:
        print("Usage : <parent port [int]> <dispatch port [int]>")
        exit(1)
    
    client = NetQueueClient()
    client.connect("localhost", int(args[0]))

    serv = NetQueueServer()
    serv.bind("localhost", int(args[1]))

    dispatch = DispatchNode(client, serv)

    while True:
        try:
            dispatch.main()
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(e)

    dispatch.close()
