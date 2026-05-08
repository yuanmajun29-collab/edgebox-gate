import os
import time
import socket
import threading


def connect_server():
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect(('192.168.5.198', 4999))
    while True:
        send_hex = "00 EE FF AA BB CC DD 99"
        send_bytes = bytes.fromhex(send_hex)
        client_socket.send(send_bytes)
        time.sleep(5)

if __name__ == '__main__':
    connect_server()
    # targets = list()
    # for i in range(5):
    #     t = threading.Thread(target=connect_server)
    #     targets.append(t)
    #
    # for target in targets:
    #     target.start()
    #
    # for target in targets:
    #     target.join()