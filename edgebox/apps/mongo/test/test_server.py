import socket
import selectors


class TestSocket:
    def __init__(self):
        self.selectors = selectors.DefaultSelector()
        self.socket_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket_server.setblocking(False)
        self.bind_ip = "0.0.0.0"
        self.bind_port = 4999
        server_tuple = (self.bind_ip, self.bind_port)
        self.socket_server.bind(server_tuple)
        self.socket_server.listen(10)
        print("创建socket服务端，bind信息: {}:{}".format(self.bind_ip, self.bind_port))
        self.selectors.register(self.socket_server, selectors.EVENT_READ, self.listen_client_socket)

    @staticmethod
    def bytes_to_hex_data(byte_list):
        hex_list = list()
        for byte_num in byte_list:
            hex_str = hex(byte_num)[2:].zfill(2).upper()
            hex_list.append(hex_str)

        return " ".join(hex_list)

    def listen_client_socket(self, client_socket):
        print("处理客户端连接请求")
        conn, client_addr = client_socket.accept()
        conn.setblocking(False)
        print("接收到客户端连接请求: {} {}".format(conn, client_addr))
        self.selectors.register(conn, selectors.EVENT_READ, self.start_handle_client_command)

    def start_handle_client_command(self, client_socket):
        try:
            recv_data = client_socket.recv(64)
            radar_client_ip = client_socket.getpeername()[0]
            radar_client_port = int(client_socket.getpeername()[1])
            if not recv_data:
                print("客户端{}已经断开连接。".format(client_socket))
                self.selectors.unregister(client_socket)
                client_socket.close()
            else:
                recv_data_hex = self.bytes_to_hex_data(recv_data)
                print("接收到客户端{}消息:{},长度:{}".format(radar_client_ip,
                                                             recv_data_hex,
                                                             len(recv_data)))
        except ConnectionResetError as e:
            print("连接被重置: {}".format(e))
            self.selectors.unregister(client_socket)
            client_socket.close()

    def start_listen_selectors(self):
        try:
            while True:
                events = self.selectors.select()
                for key, mask in events:
                    callback = key.data
                    callback(key.fileobj)
        except KeyboardInterrupt as e:
            print("stop server。")
        finally:
            self.socket_server.close()


if __name__ == '__main__':
    TestSocket().start_listen_selectors()
