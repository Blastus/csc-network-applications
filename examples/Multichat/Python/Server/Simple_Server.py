#! /usr/bin/env python3
import socket, select

def main():
    a = [socket.socket(socket.AF_INET, socket.SOCK_STREAM)]     # socket array
    a[0].bind(('', 8989))
    a[0].listen(5)
    while True:
        for b in select.select(a, [], [])[0]:                   # ready socket
            if b is a[0]:
                a.append(b.accept()[0])
            else:
                try:
                    c = b.recv(1 << 12)                         # sent message
                except socket.error:
                    b.shutdown(socket.SHUT_RDWR)
                    b.close()
                    a.remove(b)
                else:
                    for d in (d for d in a[1:] if d is not b):  # message sink
                        d.sendall(c)

if __name__ == '__main__':
    main()
