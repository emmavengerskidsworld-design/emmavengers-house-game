"""Static server with shared-bandwidth throttle (slow 4G ~1.6 Mbps down, 150 ms RTT)."""
import http.server,functools,threading,time,sys
RATE=float(sys.argv[3]) if len(sys.argv)>3 else 200_000  # bytes/s
LAT=0.15
lock=threading.Lock();state={'t':time.time(),'tok':0.0}
import os
def take(n):
    try: R=float(open('/tmp/emma-lat-rate').read())
    except Exception: R=RATE
    if R<=0: return
    while True:
        with lock:
            now=time.time();state['tok']=min(R*0.2,state['tok']+(now-state['t'])*R);state['t']=now
            if state['tok']>=n: state['tok']-=n;return
        time.sleep(0.01)
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a):pass
    def end_headers(self):
        self.send_header('Cache-Control','max-age=600');super().end_headers()
    def copyfile(self,src,dst):
        try: L=float(open('/tmp/emma-lat-rate').read())
        except Exception: L=1
        if L>0: time.sleep(LAT)
        while True:
            b=src.read(8192)
            if not b:break
            take(len(b));dst.write(b)
    def handle(self):
        try:super().handle()
        except Exception:pass
srv=http.server.ThreadingHTTPServer(('127.0.0.1',int(sys.argv[2])),functools.partial(H,directory=sys.argv[1]))
srv.daemon_threads=True;srv.serve_forever()
