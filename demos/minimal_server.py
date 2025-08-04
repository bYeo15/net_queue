'''
    Minimal example of a root server (root in the queue tree)
'''

import random

from net_queue_server import NetQueueServer

def main(serv):
    '''
        Main function for single loop of server
    '''
    # If ready but without client, block until a client is available
    if serv.state is NetQueueServer.READY:
        serv.accept_connections(block=True)
    # Otherwise, run main loop
    else:
        # Accept connections (non-blocking)
        serv.accept_connections()

        # Enqueue message to single client
        rand = random.randint(0, 1000)
        serv.put(f"Hello from server : {rand}")
        
        # Block until any message is received
        msg = serv.get(block=True, timeout=None)

        print(msg)


if __name__ == "__main__":
    serv = NetQueueServer()
    serv.bind("localhost", 8080)

    while True:
        try:
            main(serv) 
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(e)

    serv.close()
