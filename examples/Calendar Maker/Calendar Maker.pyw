import http.server
import socket
import sys
import _thread
import webbrowser

def main():
    try:
        socket.socket().connect(('127.0.0.1', 80))
        webbrowser.open('http://127.0.0.1/cgi-bin/index.py')
    except:
        if len(sys.argv) > 1:
            sys.argv[1] = '80'
        else:
            sys.argv.append('80')
        server = http.server.HTTPServer(('', 80), http.server.CGIHTTPRequestHandler)
        _thread.start_new_thread(server.serve_forever, ())
        webbrowser.open('http://127.0.0.1/cgi-bin/index.py')
        s = socket.socket()
        s.bind(('', 8080))
        s.listen(1)
        s.accept()

if __name__ == '__main__':
    main()
