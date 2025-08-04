'''
    Minimal example of a client (leaf in the queue tree)
'''

import random
import sys

from net_queue_client import NetQueueClient

def main(client, cl_id):
    '''
        Main function for single loop of client
    '''
    # Get new message from parent (blocking)
    msg = client.get()

    print(msg)

    # Enqueue response
    client.put(f"Client {cl_id} got msg") 


if __name__ == "__main__":
    args = sys.argv[1:]

    if len(args) != 1:
        print("Usage: <parent port [int]>")

    client = NetQueueClient()
    cl_id = random.randint(0, 100)
    client.connect("localhost", int(args[0]))

    while True:
        try: 
            main(client, cl_id) 
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(e)

    client.close()

