import re
import sys
import time
import random
import socket
import threading


def byte_to_hex(byte):
    return hex(byte)[2:].zfill(2)


class LightSocket:
    def __init__(self, server_ip, server_port, color):
        self.server_ip = server_ip
        self.server_port = server_port
        self.color = color
        self.client_sock = None

    def send_init_message(self):
        if self.client_sock:
            print("设置1-3路为普通模式。")
            if self.color.startswith("fy") or self.color.startswith("sy"):
                hex_data = "01 06 00 97 00 03 78 27"
            else:
                hex_data = "01 10 00 96 00 03 06 00 00 00 00 00 00 00 E2"
            send_data = bytes.fromhex(hex_data)
            print("发送消息：", hex_data)
            self.client_sock.send(send_data)
            time.sleep(1)
            print("设置关闭所有")
            hex_data = "01 06 00 34 00 00 C8 04"
            send_data = bytes.fromhex(hex_data)
            print("发送消息：", hex_data)
            self.client_sock.send(send_data)

    def send_light_color(self):
        if self.client_sock:
            if self.color.startswith("c"):
                light_cmd = "01 06 00 34 00 00 C8 04"
            elif self.color.startswith("r"):
                light_cmd = "01 06 00 00 00 15 48 05"
            elif self.color.startswith("sy"):
                light_cmd = "01 06 00 01 00 97 99 A4"
            elif self.color.startswith("fy"):
                light_cmd = "01 06 00 01 00 15 19 C5"
            elif self.color.startswith("y"):
                light_cmd = "01 06 00 01 00 15 19 C5"
            else:
                light_cmd = "01 06 00 02 00 01 E9 CA"
            send_data = bytes.fromhex(light_cmd)
            print("发送消息：", light_cmd)
            self.client_sock.send(send_data)
            self.close_socket()
            # 发送完毕后关闭sock连接

    def connect_server(self):
        self.client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_sock.connect((self.server_ip, self.server_port))
        print("连接socket服务{}:{}成功。".format(self.server_ip, self.server_port))

    def send_random_data(self):
        for i in range(1):
            # random_message = str(random.randint(0, 100))
            self.client_sock.send(bytes.fromhex('535A30337AB6249301010A00640000000000000000003C0000012D0101D3'))
            time.sleep(.5)
        self.client_sock.close()

    def read_server_data(self):
        while self.client_sock:
            recv_data = self.client_sock.recv(1024)
            print("接收到红绿灯消息：", recv_data)
            hex_list = [byte_to_hex(recv_i) for recv_i in recv_data]
            print("转化成16进制消息：", ' '.join(hex_list))

    def start_thread_task(self):
        print("开始执行")
        # 1.启动socket客户端进行连接
        self.connect_server()
        # 2.开始发送数据
        self.send_random_data()

    def close_socket(self):
        self.client_sock.close()
        self.client_sock = None

    def run(self):
        self.connect_server()
        thread = threading.Thread(target=self.read_server_data)
        thread.start()
        self.send_init_message()
        time.sleep(1)
        self.send_light_color()
        thread.join()


if __name__ == "__main__":
    cmd_args = sys.argv
    print(cmd_args)
    light_server = {
        "1": ("192.168.5.116", 1030),
        "2": ("192.168.5.120", 1030),
        "3": ("192.168.5.126", 1030),
        "4": ("192.168.5.127", 1030)
    }
    print("=================")
    server_index = cmd_args[-2]
    light_color = cmd_args[-1]
    server_tuple = light_server[server_index]
    light_socket = LightSocket(server_tuple[0], server_tuple[1], light_color)
    light_socket.run()

