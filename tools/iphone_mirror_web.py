"""Private browser viewer and input bridge for the existing iPhone media session.

The caller owns DisplayService and feeds this bridge the same Annex-B HEVC
access units it would feed to a local player. Frames and input live in memory
only; this module deliberately has no access or input logging.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import TimeoutError as FutureTimeout
from io import BytesIO
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import queue
import secrets
import subprocess
import threading
import time
from typing import Any
from urllib.parse import urlsplit


_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>iPhone Mirror</title><style>
:root{color-scheme:dark;font:15px system-ui,sans-serif;background:#101114;color:#eee}
*{box-sizing:border-box}body{margin:0;min-height:100vh;display:flex;justify-content:center}
main{width:min(100%,520px);padding:16px 12px 30px}header{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:12px}
h1{font-size:19px;margin:0}#status{font-size:13px;color:#b5bdc9}.screen{position:relative;margin:auto;width:min(100%,430px);aspect-ratio:9/19.5;background:#202228;border:1px solid #41444d;border-radius:18px;overflow:hidden;touch-action:none;outline:none}
.screen img{display:block;width:100%;height:100%;object-fit:contain;user-select:none;-webkit-user-drag:none}.screen:focus-visible{outline:3px solid #77b2ff}
.targets{position:absolute;inset:0;pointer-events:none}.target{position:absolute;pointer-events:auto;border:2px solid #74c5f8;border-radius:5px;background:#14598399;color:#fff;font:11px system-ui,sans-serif;padding:0 2px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;text-shadow:0 1px 2px #000}
.controls{display:flex;gap:8px;justify-content:center;flex-wrap:wrap;margin:12px auto;max-width:430px}.controls button,button{border:1px solid #626774;border-radius:9px;padding:9px 14px;background:#282b33;color:#fff;font:inherit;cursor:pointer}
.controls button:hover,button:hover{background:#363b47}.text{display:flex;gap:8px;max-width:430px;margin:auto}.text input{flex:1;min-width:0;border:1px solid #626774;border-radius:9px;padding:9px 10px;background:#202228;color:#fff;font:inherit}
p{max-width:430px;margin:10px auto;color:#aeb5c0;font-size:13px;line-height:1.4}#feedback{min-height:20px;color:#c8d7e6}
</style></head><body><main><header><h1>iPhone Mirror</h1><span id="status">Connecting…</span></header>
<div class="screen" id="screen" tabindex="0" aria-label="Live iPhone screen"><img id="video" src="/stream" alt="Live iPhone display" draggable="false"><div id="targets" class="targets" aria-label="Detected screen labels"></div></div>
<div class="controls"><button type="button" id="control">Take control</button><button type="button" id="home">Home</button><button type="button" id="search">Spotlight</button><button type="button" id="labels">Find labels</button></div>
<div class="text"><input id="text" type="text" autocomplete="off" spellcheck="false" placeholder="Text to paste on iPhone" aria-label="Text to paste"><button type="button" id="paste">Paste</button></div>
<p id="feedback" role="status" aria-live="polite"></p>
<p>Tap, drag, or scroll on the screen. Focus the screen for keyboard keys. Find labels uses temporary, in-memory OCR; verify the live result after each action.</p>
</main><script>
const screen=document.getElementById('screen'),video=document.getElementById('video'),status=document.getElementById('status');
const feedback=document.getElementById('feedback'),overlay=document.getElementById('targets'),control=document.getElementById('control');
const client=crypto.randomUUID();
let pressed=false,lastMove=0,pending=Promise.resolve(),hasControl=false,labelsVisible=false,lastStreamRetry=0;
async function request(path,data){
  const options={credentials:'same-origin',cache:'no-store',headers:{'X-Mirror-Client':client}};
  if(data!==undefined){options.method='POST';options.headers['Content-Type']='application/json';options.body=JSON.stringify(data)}
  const r=await fetch(path,options);
  if(!r.ok)throw Error(r.status===409?'Another tab controls the iPhone':`iPhone request failed (${r.status})`);
  return r.json();
}
function showError(error){feedback.textContent=error.message||'iPhone input unavailable'}
async function acquire(){if(!hasControl){await request('/lease',{action:'acquire'});hasControl=true;control.textContent='Release control'}return true}
async function release(){if(hasControl){await request('/lease',{action:'release'});hasControl=false;control.textContent='Take control'}return true}
function report(kind,result){feedback.textContent=`${kind} sent · ${result.frameAdvanced?'new video frame':'waiting for video'}${result.pixelsChanged===true?' · pixels changed':''}`}
function send(data){
  const task=pending.catch(()=>{}).then(async()=>{await acquire();const result=await request('/input',data);report(data.type,result);return result});
  pending=task;return task;
}
function ui(task){task.catch(showError)}
function imageRect(){const r=video.getBoundingClientRect(),iw=video.naturalWidth||9,ih=video.naturalHeight||19.5,s=Math.min(r.width/iw,r.height/ih),w=iw*s,h=ih*s;return{left:r.left+(r.width-w)/2,top:r.top+(r.height-h)/2,width:w,height:h}}
function pos(e){const r=imageRect();return{x:Math.max(0,Math.min(1,(e.clientX-r.left)/r.width)),y:Math.max(0,Math.min(1,(e.clientY-r.top)/r.height))}}
screen.addEventListener('pointerdown',e=>{if(e.button!==0||e.target.classList.contains('target'))return;e.preventDefault();screen.focus();screen.setPointerCapture(e.pointerId);pressed=true;ui(send({type:'down',...pos(e)}))});
screen.addEventListener('pointermove',e=>{if(!pressed)return;e.preventDefault();const now=performance.now();if(now-lastMove<25)return;lastMove=now;ui(send({type:'move',...pos(e)}))});
function lift(e){if(!pressed)return;e.preventDefault();pressed=false;ui(send({type:'up',...pos(e)}))}
screen.addEventListener('pointerup',lift);screen.addEventListener('pointercancel',lift);
screen.addEventListener('wheel',e=>{e.preventDefault();const p=pos(e),distance=Math.max(.12,Math.min(.48,Math.abs(e.deltaY)/900));ui(send({type:'swipe',x:p.x,y:p.y,x2:p.x,y2:Math.max(.05,Math.min(.95,p.y+(e.deltaY>0?-distance:distance))),duration:180}))},{passive:false});
screen.addEventListener('keydown',e=>{if(e.key==='Tab')return;if(e.key.length===1||['Enter','Backspace','Delete','Escape','ArrowLeft','ArrowRight','ArrowUp','ArrowDown',' '].includes(e.key)){e.preventDefault();ui(send({type:'key',key:e.key}))}});
async function targets(){return(await request('/targets')).targets}
function clearTargets(){overlay.replaceChildren();labelsVisible=false;document.getElementById('labels').textContent='Find labels'}
function drawTargets(list){clearTargets();const image=imageRect(),box=screen.getBoundingClientRect();for(const target of list){
  const button=document.createElement('button');button.type='button';button.className='target';button.textContent=target.text;
  button.setAttribute('aria-label',`Tap label ${target.text}`);button.title=`${target.text} (${Math.round(target.confidence*100)}%)`;
  button.style.left=`${image.left-box.left+target.x*image.width}px`;button.style.top=`${image.top-box.top+target.y*image.height}px`;
  button.style.width=`${Math.max(28,target.w*image.width)}px`;button.style.height=`${Math.max(18,target.h*image.height)}px`;
  button.onclick=e=>{e.stopPropagation();clearTargets();ui(send({type:'tap',x:target.x+target.w/2,y:target.y+target.h/2}))};overlay.append(button)
}labelsVisible=true;document.getElementById('labels').textContent='Hide labels';feedback.textContent=`${list.length} temporary labels found`}
async function tapLabel(label){const list=await targets(),needle=String(label).trim().toLocaleLowerCase();if(!needle)throw Error('Label is required');
  let matches=list.filter(t=>t.confidence>=.45&&t.text.toLocaleLowerCase()===needle);
  if(!matches.length)matches=list.filter(t=>t.confidence>=.45&&t.text.toLocaleLowerCase().includes(needle));
  if(matches.length!==1)throw Error(matches.length?'Label is ambiguous':'Label not found');
  const t=matches[0];return send({type:'tap',x:t.x+t.w/2,y:t.y+t.h/2})}
document.getElementById('home').onclick=()=>ui(send({type:'home'}));document.getElementById('search').onclick=()=>ui(send({type:'search'}));
control.onclick=()=>ui(hasControl?release():acquire());
document.getElementById('labels').onclick=()=>ui(labelsVisible?Promise.resolve(clearTargets()):targets().then(drawTargets));
document.getElementById('paste').onclick=()=>{const input=document.getElementById('text');if(input.value){ui(send({type:'text',text:input.value}));input.value=''}};
document.getElementById('text').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();document.getElementById('paste').click()}});
async function getStatus(){return request('/status')}
async function waitForFrame(seq,timeout=3000){const until=performance.now()+timeout;while(performance.now()<until){const s=await getStatus();if(s.video&&s.frameSeq>seq)return s;await new Promise(r=>setTimeout(r,100))}throw Error('No new iPhone frame')}
function retryStream(){const now=performance.now();if(now-lastStreamRetry<3000)return;lastStreamRetry=now;video.src=`/stream?retry=${Date.now()}`}
video.addEventListener('error',retryStream);
window.phone=Object.freeze({
  status:getStatus,acquire,release,targets,tapLabel,waitForFrame,
  tap:(x,y)=>send({type:'tap',x,y}),swipe:(x,y,x2,y2,duration=250)=>send({type:'swipe',x,y,x2,y2,duration}),
  longPress:(x,y,duration=700)=>send({type:'longPress',x,y,duration}),typeText:text=>send({type:'text',text}),
  key:key=>send({type:'key',key}),home:()=>send({type:'home'}),spotlight:()=>send({type:'search'})
});
async function refresh(){try{const s=await getStatus();hasControl=s.control==='yours';control.textContent=hasControl?'Release control':'Take control';
  status.textContent=!s.input?'Waiting for iPhone':!s.video?'Video stale':`Live · ${s.control==='yours'?'your control':s.control==='busy'?'in use':'view only'}`;
  if(!s.video)retryStream();
}catch{status.textContent='Disconnected';hasControl=false;control.textContent='Take control';retryStream()}}
refresh();setInterval(refresh,1000);
setInterval(()=>{if(hasControl)request('/lease',{action:'heartbeat'}).catch(showError)},5000);
window.addEventListener('pagehide',()=>{if(hasControl)fetch('/lease',{method:'POST',credentials:'same-origin',keepalive:true,headers:{'Content-Type':'application/json','X-Mirror-Client':client},body:JSON.stringify({action:'release'})})});
</script></body></html>"""


class WebMirror:
    """One browser viewer for a caller-owned iPhone media session.

    ``start`` and ``close`` are synchronous. ``set_input`` and
    ``clear_input`` must run on ``loop``. ``feed`` may run on that loop or
    another thread and never waits for the video encoder.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop, port: int = 8765):
        self.loop = loop
        self.port = port
        self.url = f"http://127.0.0.1:{port}/"
        self._origin = f"http://127.0.0.1:{port}"
        self._host = f"127.0.0.1:{port}"
        self._token = secrets.token_urlsafe(32)
        self._httpd: ThreadingHTTPServer | None = None
        self._server_thread: threading.Thread | None = None
        self._proc: subprocess.Popen[bytes] | None = None
        self._writer_thread: threading.Thread | None = None
        self._reader_thread: threading.Thread | None = None
        self._video_queue: queue.Queue[bytes | None] = queue.Queue(maxsize=256)
        self._frames = threading.Condition()
        self._jpeg: bytes | None = None
        self._frame_seq = 0
        self._frame_time = 0.0
        self._closed = False
        self._input_lock: asyncio.Lock | None = None
        self._hid: Any = None
        self._indigo: Any = None
        self._rsd: Any = None
        self._keyboard_id: int | None = None
        self._contact: tuple[int, int] | None = None
        self._touch_timer: asyncio.TimerHandle | None = None
        self._input_ready = False
        self._lease_lock = threading.Lock()
        self._controller: str | None = None
        self._lease_deadline = 0.0
        self._lease_thread: threading.Thread | None = None
        self._lease_stop = threading.Event()
        self._last_action: dict[str, Any] | None = None
        self._ocr_gate = threading.Lock()

    def _lease_state(self, client: str | None = None) -> str:
        with self._lease_lock:
            if self._controller is None or time.monotonic() >= self._lease_deadline:
                return "free"
            return "yours" if client == self._controller else "busy"

    def _claim(self, client: str) -> bool:
        if not isinstance(client, str) or len(client) != 36:
            return False
        with self._lease_lock:
            now = time.monotonic()
            if self._controller is not None and self._controller != client and now < self._lease_deadline:
                return False
            self._controller = client
            self._lease_deadline = now + 15
            return True

    def _release_lease(self, client: str) -> bool:
        with self._lease_lock:
            if client != self._controller:
                return False
            self._controller = None
            self._lease_deadline = 0.0
        asyncio.run_coroutine_threadsafe(self._release_held_input(), self.loop)
        return True

    def _watch_lease(self) -> None:
        while not self._lease_stop.wait(1):
            expired = False
            with self._lease_lock:
                if self._controller is not None and time.monotonic() >= self._lease_deadline:
                    self._controller = None
                    self._lease_deadline = 0.0
                    expired = True
            if expired:
                asyncio.run_coroutine_threadsafe(self._release_held_input(), self.loop)

    async def _release_held_input(self) -> None:
        lock = self._input_lock
        if lock is None:
            return
        async with lock:
            try:
                await self._release_touch()
            except Exception:
                pass
            if self._hid is not None and self._keyboard_id is not None:
                try:
                    await self._hid.send_keyboard(self._keyboard_id, [])
                except Exception:
                    pass

    def _frame_snapshot(self) -> tuple[int, bytes | None, float]:
        with self._frames:
            return self._frame_seq, self._jpeg, self._frame_time

    @staticmethod
    def _pixels_changed(before: bytes | None, after: bytes | None) -> bool | None:
        if before is None or after is None:
            return None
        try:
            from PIL import Image, ImageChops, ImageStat
            with Image.open(BytesIO(before)) as source:
                old = source.convert("L").resize((64, 64))
            with Image.open(BytesIO(after)) as source:
                new = source.convert("L").resize((64, 64))
            difference = ImageChops.difference(old, new)
            return ImageStat.Stat(difference).mean[0] >= 2.5
        except Exception:
            return None

    def _feedback(self, kind: str, baseline: tuple[int, bytes | None, float]) -> dict[str, Any]:
        previous_seq, previous_jpeg, _ = baseline
        if kind not in {"down", "move", "up"}:
            with self._frames:
                self._frames.wait_for(lambda: self._closed or self._frame_seq > previous_seq + 2, timeout=1.2)
        seq, jpeg, stamp = self._frame_snapshot()
        return {"sent": True, "frameSeq": seq, "frameAdvanced": seq > previous_seq,
                "pixelsChanged": self._pixels_changed(previous_jpeg, jpeg) if seq > previous_seq else None,
                "frameAgeMs": round((time.monotonic() - stamp) * 1000) if stamp else None}

    def start(self) -> str:
        if self._httpd is not None:
            return self.url
        self._closed = False
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_args: Any) -> None:
                pass

            def _allowed_host(self) -> bool:
                return self.client_address[0] == "127.0.0.1" and self.headers.get("Host") == owner._host

            def _has_cookie(self) -> bool:
                cookies = SimpleCookie()
                try:
                    cookies.load(self.headers.get("Cookie", ""))
                except Exception:
                    return False
                item = cookies.get("iphone_mirror_session")
                return item is not None and secrets.compare_digest(item.value, owner._token)

            def _headers(self, code: int, content_type: str, length: int | None = None) -> None:
                self.send_response(code)
                self.send_header("Content-Type", content_type)
                self.send_header("Connection", "close")
                self.close_connection = True
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Frame-Options", "DENY")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("Content-Security-Policy", "default-src 'none'; img-src 'self'; connect-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
                if length is not None:
                    self.send_header("Content-Length", str(length))

            def _reply(self, code: int, body: bytes = b"", content_type: str = "text/plain; charset=utf-8") -> None:
                self._headers(code, content_type, len(body))
                self.end_headers()
                if body:
                    self.wfile.write(body)

            def do_GET(self) -> None:
                if not self._allowed_host():
                    return self._reply(HTTPStatus.FORBIDDEN)
                path = urlsplit(self.path).path
                if path == "/":
                    body = _HTML.encode("utf-8")
                    self._headers(HTTPStatus.OK, "text/html; charset=utf-8", len(body))
                    self.send_header("Set-Cookie", f"iphone_mirror_session={owner._token}; HttpOnly; SameSite=Strict; Path=/")
                    self.end_headers()
                    self.wfile.write(body)
                    return
                if not self._has_cookie():
                    return self._reply(HTTPStatus.FORBIDDEN)
                if path == "/status":
                    seq, jpeg, stamp = owner._frame_snapshot()
                    age = round((time.monotonic() - stamp) * 1000) if stamp else None
                    body = json.dumps({"input": owner._input_ready, "video": jpeg is not None and age is not None and age < 3000,
                                       "frameSeq": seq, "frameAgeMs": age,
                                       "control": owner._lease_state(self.headers.get("X-Mirror-Client")),
                                       "lastAction": owner._last_action}, separators=(",", ":")).encode()
                    return self._reply(HTTPStatus.OK, body, "application/json")
                if path == "/targets":
                    seq, jpeg, stamp = owner._frame_snapshot()
                    if jpeg is None or time.monotonic() - stamp > 3:
                        return self._reply(HTTPStatus.SERVICE_UNAVAILABLE)
                    if not owner._ocr_gate.acquire(blocking=False):
                        return self._reply(HTTPStatus.TOO_MANY_REQUESTS)
                    try:
                        from iphone_mirror_ocr import detect_targets
                        targets = detect_targets(jpeg)
                    except Exception:
                        return self._reply(HTTPStatus.SERVICE_UNAVAILABLE)
                    finally:
                        owner._ocr_gate.release()
                    body = json.dumps({"frameSeq": seq, "targets": targets}, separators=(",", ":")).encode()
                    return self._reply(HTTPStatus.OK, body, "application/json")
                if path != "/stream":
                    return self._reply(HTTPStatus.NOT_FOUND)
                self._headers(HTTPStatus.OK, "multipart/x-mixed-replace; boundary=frame")
                self.end_headers()
                seq = 0
                try:
                    while not owner._closed:
                        with owner._frames:
                            owner._frames.wait_for(lambda: owner._closed or owner._frame_seq != seq, timeout=3)
                            if owner._closed:
                                break
                            seq, jpeg = owner._frame_seq, owner._jpeg
                        if jpeg is None:
                            continue
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(jpeg)).encode() + b"\r\n\r\n")
                        self.wfile.write(jpeg + b"\r\n")
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass

            def do_POST(self) -> None:
                if (not self._allowed_host() or self.headers.get("Origin") != owner._origin
                        or not self._has_cookie()):
                    return self._reply(HTTPStatus.FORBIDDEN)
                path = urlsplit(self.path).path
                if path not in ("/input", "/lease"):
                    return self._reply(HTTPStatus.NOT_FOUND)
                if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/json":
                    return self._reply(HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 1024 * 1024 + 4096:
                        return self._reply(HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
                    action = json.loads(self.rfile.read(length))
                    if not isinstance(action, dict):
                        raise ValueError
                except (ValueError, UnicodeError, json.JSONDecodeError):
                    return self._reply(HTTPStatus.BAD_REQUEST)
                client = self.headers.get("X-Mirror-Client", "")
                if path == "/lease":
                    operation = action.get("action")
                    if operation in ("acquire", "heartbeat"):
                        if not owner._claim(client):
                            return self._reply(HTTPStatus.CONFLICT)
                    elif operation == "release":
                        if not owner._release_lease(client):
                            return self._reply(HTTPStatus.CONFLICT)
                    else:
                        return self._reply(HTTPStatus.BAD_REQUEST)
                    body = json.dumps({"control": owner._lease_state(client)}, separators=(",", ":")).encode()
                    return self._reply(HTTPStatus.OK, body, "application/json")
                if not owner._claim(client):
                    return self._reply(HTTPStatus.CONFLICT)
                baseline = owner._frame_snapshot()
                try:
                    future = asyncio.run_coroutine_threadsafe(owner._dispatch(action, client), owner.loop)
                    future.result(timeout=12)
                except FutureTimeout:
                    future.cancel()
                    return self._reply(HTTPStatus.GATEWAY_TIMEOUT)
                except (ValueError, TypeError):
                    return self._reply(HTTPStatus.BAD_REQUEST)
                except Exception:
                    return self._reply(HTTPStatus.SERVICE_UNAVAILABLE)
                feedback = owner._feedback(action.get("type", ""), baseline)
                owner._last_action = {"type": action.get("type"), "sent": True,
                                      "frameAdvanced": feedback["frameAdvanced"],
                                      "pixelsChanged": feedback["pixelsChanged"]}
                body = json.dumps(feedback, separators=(",", ":")).encode()
                self._reply(HTTPStatus.OK, body, "application/json")

        self._httpd = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        self._httpd.daemon_threads = True
        self._httpd.request_queue_size = 32
        try:
            self._proc = subprocess.Popen([
                "ffmpeg", "-hide_banner", "-loglevel", "quiet", "-nostdin",
                "-threads", "2", "-probesize", "32", "-analyzeduration", "0", "-f", "hevc", "-i", "pipe:0",
                "-an", "-vf", "fps=12,scale=540:-2", "-q:v", "4",
                "-f", "image2pipe", "-vcodec", "mjpeg", "pipe:1",
            ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
        except Exception:
            self._httpd.server_close()
            self._httpd = None
            raise
        self._writer_thread = threading.Thread(target=self._write_video, daemon=True, name="iphone-web-hevc")
        self._reader_thread = threading.Thread(target=self._read_video, daemon=True, name="iphone-web-jpeg")
        self._server_thread = threading.Thread(target=self._httpd.serve_forever, daemon=True, name="iphone-web-http")
        self._lease_stop.clear()
        self._lease_thread = threading.Thread(target=self._watch_lease, daemon=True, name="iphone-web-lease")
        self._writer_thread.start()
        self._reader_thread.start()
        self._server_thread.start()
        self._lease_thread.start()
        return self.url

    def feed(self, data: bytes) -> bool:
        """Queue one Annex-B access unit without blocking capture."""
        if self._closed or self._proc is None or self._proc.poll() is not None:
            return False
        try:
            self._video_queue.put_nowait(data)
            return True
        except queue.Full:
            return False

    @property
    def video_failed(self) -> bool:
        return (self._proc is None or self._proc.poll() is not None
                or (self._reader_thread is not None and not self._reader_thread.is_alive())
                or (self._frame_seq > 0 and time.monotonic() - self._frame_time > 15))

    def _write_video(self) -> None:
        proc = self._proc
        if proc is None or proc.stdin is None:
            return
        try:
            while not self._closed:
                try:
                    data = self._video_queue.get(timeout=0.2)
                except queue.Empty:
                    continue
                if data is None:
                    break
                proc.stdin.write(data)
        except (BrokenPipeError, OSError):
            pass
        finally:
            try:
                proc.stdin.close()
            except OSError:
                pass

    def _read_video(self) -> None:
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        buffer = bytearray()
        try:
            while not self._closed:
                chunk = proc.stdout.read(65536)
                if not chunk:
                    break
                buffer.extend(chunk)
                while True:
                    start = buffer.find(b"\xff\xd8")
                    if start < 0:
                        # The JPEG start marker can straddle pipe reads.
                        tail = buffer[-1:] if buffer.endswith(b"\xff") else b""
                        buffer.clear()
                        buffer.extend(tail)
                        break
                    if start:
                        del buffer[:start]
                    end = buffer.find(b"\xff\xd9", 2)
                    if end < 0:
                        if len(buffer) > 8 * 1024 * 1024:
                            buffer.clear()
                        break
                    jpeg = bytes(buffer[:end + 2])
                    del buffer[:end + 2]
                    with self._frames:
                        self._jpeg = jpeg
                        self._frame_seq += 1
                        self._frame_time = time.monotonic()
                        self._frames.notify_all()
        except OSError:
            pass

    async def set_input(self, rsd: Any) -> None:
        from pymobiledevice3.remote.core_device.hid_service import UniversalHIDServiceService

        await self.clear_input()
        self._input_lock = asyncio.Lock()
        hid = UniversalHIDServiceService(rsd)
        await hid.connect()
        self._rsd = rsd
        self._hid = hid
        self._input_ready = True

    async def clear_input(self) -> None:
        self._input_ready = False
        with self._lease_lock:
            self._controller = None
            self._lease_deadline = 0.0
        lock = self._input_lock
        if lock is None:
            return
        async with lock:
            self._cancel_touch_timer()
            if self._hid is not None:
                if self._contact is not None:
                    from pymobiledevice3.remote.core_device.hid_service import TOUCHSCREEN_STATE_RELEASE
                    try:
                        await self._hid.send_touchscreen(TOUCHSCREEN_STATE_RELEASE, *self._contact)
                    except Exception:
                        pass
                    self._contact = None
                if self._keyboard_id is not None:
                    try:
                        await self._hid.send_keyboard(self._keyboard_id, [])
                    except Exception:
                        pass
                try:
                    await self._hid.close()
                except Exception:
                    pass
            if self._indigo is not None:
                try:
                    await self._indigo.close()
                except Exception:
                    pass
            self._hid = self._indigo = self._rsd = None
            self._keyboard_id = None

    def _cancel_touch_timer(self) -> None:
        if self._touch_timer is not None:
            self._touch_timer.cancel()
            self._touch_timer = None

    def _arm_touch_timer(self) -> None:
        self._cancel_touch_timer()
        self._touch_timer = self.loop.call_later(5, lambda: asyncio.create_task(self._expire_touch()))

    async def _expire_touch(self) -> None:
        lock = self._input_lock
        if lock is None:
            return
        async with lock:
            await self._release_touch()

    async def _release_touch(self, pos: tuple[int, int] | None = None) -> None:
        from pymobiledevice3.remote.core_device.hid_service import TOUCHSCREEN_STATE_RELEASE

        self._cancel_touch_timer()
        if self._contact is not None and self._hid is not None:
            last = pos or self._contact
            self._contact = None
            await self._hid.send_touchscreen(TOUCHSCREEN_STATE_RELEASE, *last)

    @staticmethod
    def _point(action: dict[str, Any], x_key: str = "x", y_key: str = "y") -> tuple[int, int]:
        x, y = action[x_key], action[y_key]
        if type(x) not in (int, float) or type(y) not in (int, float):
            raise ValueError("invalid coordinates")
        if not math.isfinite(x) or not math.isfinite(y) or not 0 <= x <= 1 or not 0 <= y <= 1:
            raise ValueError("invalid coordinates")
        return round(x * 65535), round(y * 65535)

    async def _ensure_keyboard(self) -> int:
        if self._keyboard_id is None:
            self._keyboard_id = await self._hid.create_keyboard_service()
        return self._keyboard_id

    async def _press(self, usage: int, modifiers: set[int] | None = None) -> None:
        keyboard = await self._ensure_keyboard()
        modifiers = modifiers or set()
        try:
            if modifiers:
                await self._hid.send_keyboard(keyboard, modifiers)
                await asyncio.sleep(0.01)
            await self._hid.send_keyboard(keyboard, modifiers | {usage})
            await asyncio.sleep(0.05)
            if modifiers:
                await self._hid.send_keyboard(keyboard, modifiers)
        finally:
            await self._hid.send_keyboard(keyboard, [])

    async def _dispatch(self, action: dict[str, Any], client: str) -> None:
        from pymobiledevice3.remote.core_device.hid_service import (
            HID_BUTTON_STATE_DOWN, HID_BUTTON_STATE_UP, IndigoHIDService,
            TOUCHSCREEN_STATE_CONTACT,
        )
        from pymobiledevice3.remote.core_device.pasteboard_service import PasteboardService
        from pymobiledevice3.remote.core_device.vnc_server import ASCII_TO_HID

        kind = action.get("type")
        if kind not in {"down", "move", "up", "tap", "swipe", "longPress", "key", "text", "home", "search"}:
            raise ValueError("invalid input action")
        lock = self._input_lock
        if not self._input_ready or lock is None:
            raise RuntimeError("iPhone input is unavailable")
        async with lock:
            if not self._input_ready or self._hid is None:
                raise RuntimeError("iPhone input is unavailable")
            if self._lease_state(client) != "yours":
                raise RuntimeError("control lease expired")
            if kind in {"down", "move", "up", "tap", "swipe", "longPress"}:
                pos = self._point(action)
                if kind == "down":
                    await self._release_touch()
                    await self._hid.send_touchscreen(TOUCHSCREEN_STATE_CONTACT, *pos)
                    self._contact = pos
                    self._arm_touch_timer()
                elif kind == "move":
                    if self._contact is not None:
                        await self._hid.send_touchscreen(TOUCHSCREEN_STATE_CONTACT, *pos)
                        self._contact = pos
                        self._arm_touch_timer()
                elif kind == "up":
                    await self._release_touch(pos)
                elif kind == "tap":
                    await self._release_touch()
                    try:
                        await self._hid.send_touchscreen(TOUCHSCREEN_STATE_CONTACT, *pos)
                        self._contact = pos
                        await asyncio.sleep(0.06)
                    finally:
                        await self._release_touch(pos)
                elif kind == "longPress":
                    duration = action.get("duration", 700)
                    if type(duration) not in (int, float) or not math.isfinite(duration) or not 100 <= duration <= 4000:
                        raise ValueError("invalid duration")
                    await self._release_touch()
                    try:
                        await self._hid.send_touchscreen(TOUCHSCREEN_STATE_CONTACT, *pos)
                        self._contact = pos
                        await asyncio.sleep(duration / 1000)
                    finally:
                        await self._release_touch(pos)
                else:
                    end = self._point(action, "x2", "y2")
                    duration = action.get("duration", 250)
                    if type(duration) not in (int, float) or not math.isfinite(duration) or not 50 <= duration <= 2000:
                        raise ValueError("invalid duration")
                    await self._release_touch()
                    steps = max(5, min(40, round(duration / 20)))
                    try:
                        for i in range(steps + 1):
                            point = (round(pos[0] + (end[0] - pos[0]) * i / steps),
                                     round(pos[1] + (end[1] - pos[1]) * i / steps))
                            await self._hid.send_touchscreen(TOUCHSCREEN_STATE_CONTACT, *point)
                            self._contact = point
                            if i < steps:
                                await asyncio.sleep(duration / steps / 1000)
                    finally:
                        await self._release_touch()
                return
            if kind == "home":
                if self._indigo is None:
                    self._indigo = IndigoHIDService(self._rsd)
                    await self._indigo.connect()
                try:
                    await self._indigo.send_button(0x0C, 0x40, HID_BUTTON_STATE_DOWN)
                    await asyncio.sleep(0.06)
                finally:
                    await self._indigo.send_button(0x0C, 0x40, HID_BUTTON_STATE_UP)
                return
            if kind == "search":
                await self._press(44, {227})
                return
            if kind == "text":
                value = action.get("text")
                if not isinstance(value, str) or not value or len(value.encode("utf-8")) > 1024 * 1024:
                    raise ValueError("invalid text")
                pasteboard = PasteboardService(self._rsd)
                try:
                    await pasteboard.connect()
                    reply = await pasteboard.set_text(value)
                    if not isinstance(reply, dict) or reply.get("command") != "SET_REPLY" or reply.get("error"):
                        raise RuntimeError("paste failed")
                finally:
                    await pasteboard.close()
                await self._press(25, {227})
                return
            key = action.get("key")
            if not isinstance(key, str) or len(key) > 24:
                raise ValueError("invalid key")
            specials = {"Enter": 40, "Backspace": 42, "Delete": 76, "Escape": 41,
                        "ArrowLeft": 80, "ArrowRight": 79, "ArrowUp": 82, "ArrowDown": 81,
                        " ": 44}
            if key in specials:
                usage, modifiers = specials[key], set()
            elif len(key) == 1 and key in ASCII_TO_HID:
                usage, shifted = ASCII_TO_HID[key]
                modifiers = {225} if shifted else set()
            else:
                raise ValueError("unsupported key")
            await self._press(usage, modifiers)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._lease_stop.set()
        with self._frames:
            self._frames.notify_all()
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        if self._proc is not None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait(timeout=1)
            self._proc = None
        for thread in (self._writer_thread, self._reader_thread, self._server_thread, self._lease_thread):
            if thread is not None:
                thread.join(timeout=1)
        self._jpeg = None
