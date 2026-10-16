"""Self-hosted Studio: static UltraBox + authenticated, revisioned song saves."""
import hmac, json, os, re, sqlite3, threading, time
from contextlib import closing
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
SITE = Path(os.environ.get("STUDIO_SITE", "/app/site"))
DB = Path(os.environ.get("STUDIO_DB", "/data/studio.sqlite3"))
TOKEN = os.environ.get("STUDIO_API_TOKEN", "")
LOCK = threading.Lock()

def database():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=15)
    con.execute("PRAGMA busy_timeout=15000")
    con.execute("CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL UNIQUE,song TEXT NOT NULL,revision INTEGER NOT NULL,updated INTEGER NOT NULL)")
    con.commit()
    return con

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,directory=str(SITE),**kwargs)

    def end_headers(self):
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("Referrer-Policy","no-referrer")
        super().end_headers()

    def send_json(self,status,data):
        raw=json.dumps(data,separators=(",",":")).encode()
        self.send_response(status)
        self.send_header("Content-Type","application/json")
        self.send_header("Cache-Control","no-store")
        self.send_header("Content-Length",str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def authorized(self):
        return bool(TOKEN) and hmac.compare_digest(self.headers.get("Authorization",""),"Bearer "+TOKEN)

    def guard(self):
        if self.authorized(): return True
        self.send_json(401,{"error":"Studio project token required"})
        return False

    def do_GET(self):
        path=urlsplit(self.path).path
        if path=="/api/health":
            return self.send_json(200,{"ok":True,"service":"studio"})
        if path.startswith("/api/"):
            if not self.guard(): return
            if path=="/api/projects":
                with closing(database()) as db:
                    rows=db.execute("SELECT id,name,revision,updated FROM projects ORDER BY updated DESC").fetchall()
                return self.send_json(200,{"projects":[dict(id=r[0],name=r[1],revision=r[2],updated=r[3]) for r in rows]})
            match=re.fullmatch(r"/api/projects/([1-9][0-9]{0,10})",path)
            if match:
                with closing(database()) as db:
                    row=db.execute("SELECT id,name,song,revision,updated FROM projects WHERE id=?",(int(match[1]),)).fetchone()
                if row: return self.send_json(200,dict(id=row[0],name=row[1],song=row[2],revision=row[3],updated=row[4]))
            return self.send_json(404,{"error":"Project not found"})
        if path.endswith((".env",".sqlite3",".py",".ts")):
            return self.send_error(404)
        return super().do_GET()

    def do_POST(self):
        if urlsplit(self.path).path!="/api/projects": return self.send_json(404,{"error":"Not found"})
        if not self.guard(): return
        try: size=int(self.headers.get("Content-Length","0"))
        except ValueError: return self.send_json(400,{"error":"Invalid length"})
        if size<1 or size>512000: return self.send_json(413,{"error":"Project too large"})
        try:
            data=json.loads(self.rfile.read(size))
            name=data["name"];song=data["song"]; rev=data.get("revision",0);pid=data.get("id")
            if not isinstance(name,str) or not 1<=len(name.strip())<=72: raise ValueError("Invalid name")
            if not isinstance(song,str) or not 1<=len(song)<=400000 or not re.fullmatch(r"[a-zA-Z0-9_+=/\-]+",song): raise ValueError("Invalid song data")
            if not isinstance(rev,int) or isinstance(rev,bool) or rev<0: raise ValueError("Invalid revision")
            if pid is not None and (not isinstance(pid,int) or isinstance(pid,bool) or pid<1): raise ValueError("Invalid ID")
        except (ValueError,TypeError,KeyError,json.JSONDecodeError) as e:
            return self.send_json(400,{"error":str(e)})
        with LOCK, closing(database()) as db:
            stamp=int(time.time())
            if pid is None:
                if rev!=0:return self.send_json(409,{"error":"New projects need revision 0"})
                try:
                    cur=db.execute("INSERT INTO projects(name,song,revision,updated) VALUES(?,?,1,?)",(name.strip(),song,stamp))
                except sqlite3.IntegrityError: return self.send_json(409,{"error":"Project name exists"})
                pid,rev=cur.lastrowid,1
            else:
                try:
                    cur=db.execute("UPDATE projects SET name=?,song=?,revision=revision+1,updated=? WHERE id=? AND revision=?",(name.strip(),song,stamp,pid,rev))
                except sqlite3.IntegrityError:return self.send_json(409,{"error":"Project name exists"})
                if cur.rowcount!=1:return self.send_json(409,{"error":"Conflict: reload or Save As to preserve both versions"})
                rev+=1
            db.commit()
        self.send_json(200,{"id":pid,"name":name.strip(),"revision":rev,"updated":stamp})

    def do_PUT(self): self.send_json(405,{"error":"Use POST"})
    def do_DELETE(self): self.send_json(405,{"error":"Not supported"})

if __name__=="__main__":
    if len(TOKEN)<32 or TOKEN.startswith("REPLACE_"): raise SystemExit("Set a random STUDIO_API_TOKEN >=32 characters")
    database().close()
    host=os.environ.get("STUDIO_BIND","0.0.0.0")
    port=int(os.environ.get("STUDIO_PORT","8080"))
    print("Studio ready at "+host+":"+str(port),flush=True)
    ThreadingHTTPServer((host,port),Handler).serve_forever()
