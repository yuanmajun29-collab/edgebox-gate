import socket


def listen_alg_message():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_tuple = ("0.0.0.0", 6667)
    server_socket.bind(server_tuple)
    print("Listening... port: {}".format(server_tuple[1]))
    server_socket.listen(10)
    conn, client_addr = server_socket.accept()
    print("Connected by", client_addr)
    while True:
        receive_data = conn.recv(1024)
        if not receive_data:
            print("Connection closed")
            break
        receive_data = receive_data.decode()
        if "#!" in receive_data:
            index_head = receive_data.index("#!")
            print("receive_data:", receive_data[index_head:index_head + 55])


if __name__ == '__main__':
    listen_alg_message()
