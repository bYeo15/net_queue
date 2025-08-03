'''
    Minimal example of a client (leaf in the queue tree)
'''

import random
import sys

from net_queue_client import NetQueueClient
from protocol import MsgTypes, create_msg

class ClientQueue(NetQueueClient):
    def __init__(self, port: int, config_file: str = "./client_conf"):
        '''
            Trivial __init__ wrapper that allows selecting a port
        '''
        super().__init__(config_file=config_file)
        self.client_id = random.randint(0, 1000)
        self.config["port"] = port
        self.connect(self.config["hostname"], self.config["port"])

    def load_config(self, config_file: str):
        '''
            Dummy load config, just sets values to default
        '''
        self.config["hostname"] = "localhost"

    def main(self):
        '''
            Main function for single loop of client
        '''
        # Get new message from parent (blocking)
        msg = self.get()

        print(msg)

        # Enqueue response
        self.put(create_msg(MsgTypes.ENQUEUE, f"Client {self.client_id} got msg")) 


if __name__ == "__main__":
    args = sys.argv[1:]

    try:
        client = ClientQueue(int(args[0]))

        while True:
            try: 
                client.main()
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(e)

        client.close()
    except Exception as e:
        print("Usage: <port [int]>")

