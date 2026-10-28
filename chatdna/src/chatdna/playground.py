from http.server import BaseHTTPRequestHandler,HTTPServer
import json
from pathlib import Path
import secrets
from urllib.parse import urlparse
from .inference import LocalModels

def origin_allowed(origin,port):
    if not origin:
        return True
    parsed=urlparse(origin)
    return parsed.scheme=='http' and parsed.hostname in {'127.0.0.1','localhost'} and parsed.port==port

def serve(registry,port=8765):
    models=LocalModels(registry)
    token=secrets.token_urlsafe(32)
    page=(Path(__file__).with_name('playground.html')).read_text(encoding='utf-8').replace('__LOCAL_TOKEN__',token)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):
            pass
        def send(self,status,data,content_type='application/json'):
            raw=data.encode('utf-8') if isinstance(data,str) else json.dumps(data).encode()
            self.send_response(status)
            self.send_header('Content-Type',content_type+'; charset=utf-8')
            self.send_header('Content-Length',str(len(raw)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'")
            try:
                self.end_headers(); self.wfile.write(raw)
            except (BrokenPipeError,ConnectionAbortedError,ConnectionResetError):
                # A closed browser request must not echo payloads or raise again.
                return
        def permitted(self):
            host=self.headers.get('Host','').split(':')[0]
            return host in {'127.0.0.1','localhost'} and origin_allowed(self.headers.get('Origin'),port)
        def do_GET(self):
            if not self.permitted():
                return self.send(403,{'error':'Local origin required'})
            if self.path=='/':
                return self.send(200,page,'text/html')
            if self.path=='/api/models':
                return self.send(200,{'models':models.listing(),'device':models.device,'identity':'experimental model'})
            self.send(404,{'error':'Not found'})
        def do_POST(self):
            if not self.permitted() or self.headers.get('X-Local-Token')!=token:
                return self.send(403,{'error':'Local session token required'})
            if self.path!='/api/generate':
                return self.send(404,{'error':'Not found'})
            try:
                length=int(self.headers.get('Content-Length','0'))
            except ValueError:
                return self.send(400,{'error':'Invalid request size'})
            if not 0<length<=16384:
                return self.send(400,{'error':'Invalid request size'})
            try:
                data=json.loads(self.rfile.read(length))
                result=models.generate(data['model'],data['prompt'],data.get('temperature',.7),data.get('max_new_tokens',64))
                self.send(200,result)
            except Exception as error:
                models.unload()
                self.send(503,{'error':'Local inference could not run: '+type(error).__name__+'. Check checkpoint availability and free device memory.'})
    server=HTTPServer(('127.0.0.1',port),Handler)
    print(f'ChatDNA local playground: http://127.0.0.1:{port}',flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close(); models.unload()
