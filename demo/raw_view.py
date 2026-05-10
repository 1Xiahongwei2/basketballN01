# raw_view.py — 裸数据观察，用来标定阈值
import socket, json, time
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", 8888))
while True:
    buf, _ = sock.recvfrom(1024)
    print(json.loads(buf.decode()))