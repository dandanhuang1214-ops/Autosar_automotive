"""Loopback web entry for versioned graph, project evidence and local Ollama."""
from __future__ import annotations

import argparse
import json
import secrets
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, urlsplit

from automotive_workbench.explanation_services import parse_json
from automotive_workbench.knowledge_chat import (
    _connect, ask, edit_memory, forget, history, memories, new_session, remember,
)
from automotive_workbench.knowledge_graph_workspace import (
    MAX_GRAPH_BYTES, MAX_REVIEW_BYTES, MAX_SOURCE_BYTES, active_reviews,
    active_snapshot, import_graph, import_reviews,
)

HTML = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Automotive Workbench</title><style>
:root{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;color:#18242a;background:#f3f5f2}*{box-sizing:border-box}body{margin:0}header{background:#16303a;color:white;padding:20px 28px;display:flex;justify-content:space-between;align-items:center}header h1{font-size:22px;margin:0}header small{color:#bdd1d1}.layout{display:grid;grid-template-columns:300px 1fr 300px;gap:16px;padding:16px;max-width:1700px;margin:auto}.panel{background:white;border:1px solid #d8e1dd;border-radius:12px;padding:18px;min-width:0;box-shadow:0 3px 12px #16303a0b}h2{font-size:16px;margin:0 0 12px}h3{font-size:14px;margin:18px 0 8px}label{display:block;font-size:13px;font-weight:600;margin:12px 0 5px}input,textarea,select,button{font:inherit}input,textarea,select{width:100%;border:1px solid #b9c9c5;border-radius:7px;padding:9px;background:white}textarea{resize:vertical}button{border:0;border-radius:7px;padding:9px 12px;background:#087969;color:white;cursor:pointer}button:disabled{opacity:.5;cursor:wait}.secondary{background:#e9efed;color:#1b4546}.muted{color:#607373;font-size:13px}.warn{background:#fff3df;color:#674300;border-radius:7px;padding:9px;font-size:13px}.good{background:#e3f5ed;color:#155644;border-radius:7px;padding:9px;font-size:13px}#evidence{max-height:52vh;overflow:auto}.messages{height:52vh;overflow:auto;border:1px solid #e0e7e3;border-radius:8px;padding:12px;background:#fcfdfb}.message{margin:0 0 12px;padding:11px;border-radius:8px;background:#eef4f2;white-space:pre-wrap;overflow-wrap:anywhere}.message.user{background:#dff0ea}.message strong{display:block;margin-bottom:5px}.chips{display:flex;flex-wrap:wrap;gap:6px}.chip{font-size:12px;background:#eef1e9;border-radius:99px;padding:4px 8px}details{margin:10px 0;border:1px solid #dce5e0;border-radius:8px;padding:8px}summary{cursor:pointer}ul{padding-left:20px}.row{display:flex;gap:7px;align-items:center}.row>*{flex:1}.row button{flex:0 0 auto}.smallbtn{padding:4px 8px;font-size:12px}code{overflow-wrap:anywhere}@media(max-width:1000px){.layout{grid-template-columns:1fr}.messages{height:36vh}}
</style></head><body><header><div><h1>Automotive Workbench</h1><small>工程证据 · 知识图谱 · 本地模型</small></div><span id="service" class="muted">本机运行 · 本地数据</span></header><div class="layout">
<aside class="panel"><h2>项目与图谱</h2><div id="graphState" class="warn">尚未导入图谱</div><label for="files">从知识图谱站点下载并选择 graph.json 与全部 source-*.md</label><input id="files" type="file" multiple accept=".json,.md"><label for="siteVersion">站点版本标记（供记录）</label><input id="siteVersion" placeholder="例如 5"><button id="importBtn" style="margin-top:10px">导入并核验</button><div id="importStatus" class="muted"></div><h3>图谱核实记录</h3><p class="muted">如已在站点填写工作单，可单独导出核实记录 JSON。这里只显示注释，不自动改写候选结论。</p><input id="reviewFile" type="file" accept=".json" aria-label="选择图谱核实记录"><button id="reviewImportBtn" class="secondary" style="margin-top:8px">导入核实记录</button><div id="reviewState" class="muted"></div><h3>工程报告</h3><label for="report">本机 project-report.json 绝对路径</label><input id="report" placeholder="/mnt/d/.../bundle/project-report.json"><p class="muted">每次提问都重放报告证据。没有报告时可探索图谱候选知识。</p><h3>会话</h3><select id="sessions" aria-label="选择历史会话"></select><button id="newSession" class="secondary" style="margin-top:8px">新会话</button></aside>
<main class="panel"><h2>工程问答</h2><div id="messages" class="messages" aria-live="polite"></div><label for="question">提问</label><textarea id="question" rows="3" placeholder="例如：这个信号到 CAN 的链路证据有哪些？哪些仍待核实？"></textarea><div class="row" style="margin-top:10px"><label style="flex:1"><input id="useModel" type="checkbox" checked style="width:auto"> 使用本地 Ollama 生成解释草稿</label><button id="askBtn">发送</button></div><p class="muted">工程事实来自重放报告；图谱关系均标为候选。模型草稿未经语义验收。</p></main>
<aside class="panel"><h2>证据与记忆</h2><div id="evidence" class="muted">提问后显示来源和状态。</div><h3>长期记忆（明确保存）</h3><p class="muted">只记录你主动保存的偏好或决定，不自动记住模型结论。</p><label for="memory">要记住的内容</label><textarea id="memory" rows="3"></textarea><label for="memoryScope">范围</label><select id="memoryScope"><option value="global">通用偏好</option><option value="project">当前工程版本</option></select><button id="saveMemory" style="margin-top:8px">保存记忆</button><ul id="memoryList"></ul></aside></div>
<script>
const token='__TOKEN__';const $=id=>document.getElementById(id);let sessionId=localStorage.getItem('awb-session')||'';let projectHash='';let activeHash='';
async function api(path,body){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Workbench-Token':token},body:JSON.stringify(body)});const d=await r.json();if(!r.ok)throw Error(d.error||'请求失败');return d}
function el(name,text,cls){const n=document.createElement(name);n.textContent=text;if(cls)n.className=cls;return n}
function showError(e){$('service').textContent='错误：'+e.message}
function renderMessage(role,content,status){const n=el('div','',`message ${role}`);const title=role==='user'?'你':status==='draft_unassessed'?'Ollama 草稿 · 未经语义审阅':'工作台证据';n.append(el('strong',title),el('span',content||'没有模型草稿；请查看右侧证据。'));$('messages').append(n);$('messages').scrollTop=$('messages').scrollHeight}
function renderAssistant(d){renderMessage('assistant',d.summary||'证据见右侧。','evidence_only');if(d.draft)renderMessage('assistant',d.draft,'draft_unassessed')}
function renderEvidence(d){const box=$('evidence');box.replaceChildren();const ev=d.evidence||{};box.append(el('div',`所选项目验收：${ev.project_status||'未选择'}`,'good'),el('p','此状态不证明 CFG 生成或 CAN 总线实测。','muted'),el('p',`图谱版本：${(ev.graph_sha256||'').slice(0,16)}；节点/关系均为候选。`,'muted'));const current=ev.graph_sha256===activeHash;if(ev.graph_sha256&&!current)box.append(el('div','历史回答使用旧版图谱，请重新提问以核对新版。','warn'));for(const f of ev.project_facts||[])box.append(el('div',`${f.artifact_id}#${f.pointer} = ${JSON.stringify(f.value)}`,'chip'));for(const n of ev.graph_nodes||[])box.append(el('div',`${n.id} · ${n.label} · 候选 · ${n.source}`,'chip'));for(const a of ev.review_annotations||[])box.append(el('div',`用户核实注释 ${a.task_id}：${a.status}；${a.evidence}。图谱仍为候选。`,'warn'));if(current){const needed=new Set((ev.graph_nodes||[]).flatMap(n=>n.source_documents||[]));for(const s of ev.source_documents||[]){if(!needed.has(s.id))continue;const a=el('a',`查看来源：${s.filename}`);a.href='/api/source?name='+encodeURIComponent(s.filename);a.target='_blank';a.rel='noopener';box.append(el('p',''),a)}}if(d.citations?.length)box.append(el('p',`模型引用 ID：${d.citations.join(', ')}`,'muted'));if(d.model_error)box.append(el('div',`Ollama：${d.model_error}`,'warn'))}
async function refresh(){const r=await fetch('/api/state?session='+encodeURIComponent(sessionId));const d=await r.json();if(!d.sessions.length){const created=await api('/api/session',{});sessionId=created.session_id;localStorage.setItem('awb-session',sessionId);return refresh()}activeHash=d.active?.graph_sha256||'';if(d.active){$('graphState').textContent=`已导入：${d.active.site_version} · ${d.active.graph_sha256.slice(0,16)} · ${d.active.counts.nodes} 节点 / ${d.active.counts.edges} 关系`;$('graphState').className='good'}else{$('graphState').textContent='尚未导入图谱';$('graphState').className='warn'}$('reviewState').textContent=d.reviews?.status==='stale_graph'?'核实记录属于旧版图谱，请重新导出并导入。':d.reviews?.status==='user_annotation_only'?`已导入核实记录，${Object.keys(d.reviews.reviews).length} 项；仅作用户注释。`:'未导入核实记录。';const sel=$('sessions');sel.replaceChildren();for(const x of d.sessions){const o=el('option',`${x.created_at.slice(0,16)} · ${x.id.slice(0,8)}`);o.value=x.id;sel.append(o)}if(!d.sessions.some(x=>x.id===sessionId))sessionId=d.sessions[0].id;sel.value=sessionId;localStorage.setItem('awb-session',sessionId);$('messages').replaceChildren();for(const m of d.messages){if(m.role==='assistant')renderAssistant(m.detail);else renderMessage('user',m.content)}const last=[...d.messages].reverse().find(x=>x.role==='assistant');if(last){renderEvidence(last.detail);projectHash=last.project_sha256||''}renderMemories(d.memories)}
function renderMemories(items){const box=$('memoryList');box.replaceChildren();for(const m of items){const li=el('li',m.content);const edit=el('button','编辑','secondary smallbtn');edit.onclick=async()=>{const next=prompt('修改记忆',m.content);if(next===null)return;await api('/api/memory/edit',{id:m.id,content:next});await refresh()};const b=el('button','删除','secondary smallbtn');b.onclick=async()=>{await api('/api/memory/delete',{id:m.id});await refresh()};li.append(' ',edit,' ',b);box.append(li)}}
$('newSession').onclick=async()=>{try{const d=await api('/api/session',{});sessionId=d.session_id;localStorage.setItem('awb-session',sessionId);await refresh()}catch(e){showError(e)}};
$('sessions').onchange=async()=>{sessionId=$('sessions').value;localStorage.setItem('awb-session',sessionId);await refresh()};
$('importBtn').onclick=async()=>{const b=$('importBtn');b.disabled=true;try{const files=Array.from($('files').files);const data={};for(const f of files)data[f.name]=await f.text();const d=await api('/api/import',{files:data,site_version:$('siteVersion').value||'未标记'});const changes=Object.entries(d.diff).map(([kind,v])=>`${kind}: +${v.added.length} / -${v.removed.length} / 改${v.changed.length}`).join('；');$('importStatus').textContent=`核验通过。哈希 ${d.graph_sha256.slice(0,16)}；${changes}`;await refresh()}catch(e){$('importStatus').textContent=e.message}finally{b.disabled=false}};
$('reviewImportBtn').onclick=async()=>{try{const file=$('reviewFile').files[0];if(!file)throw Error('请先选择站点导出的核实记录 JSON');const d=await api('/api/reviews/import',{content:await file.text()});$('reviewState').textContent=`已保存 ${Object.values(d.counts).reduce((a,b)=>a+b,0)} 项注释；图谱候选状态不变。`;await refresh()}catch(e){showError(e)}};
$('askBtn').onclick=async()=>{const b=$('askBtn');b.disabled=true;try{const q=$('question').value.trim();if(!q)return;renderMessage('user',q);const d=await api('/api/chat',{session_id:sessionId,question:q,report:$('report').value.trim(),use_model:$('useModel').checked});renderAssistant(d);renderEvidence(d);$('question').value='';projectHash=d.evidence.project_sha256||''}catch(e){showError(e)}finally{b.disabled=false}};
$('saveMemory').onclick=async()=>{try{const scope=$('memoryScope').value==='global'?'global':projectHash;if(!scope)throw Error('请先选择工程并提问，再保存工程记忆');await api('/api/memory',{scope,content:$('memory').value});$('memory').value='';await refresh()}catch(e){showError(e)}};
refresh().catch(showError);
</script></body></html>"""


class WorkspaceServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], root: Path, model: str, ollama_url: str):
        if address[0] not in {"127.0.0.1", "localhost"}:
            raise ValueError("Workbench web server must bind to loopback")
        self.root = root
        self.db_path = root / "chat.sqlite3"
        self.model = model
        self.ollama_url = ollama_url
        self.token = secrets.token_urlsafe(24)
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    server: WorkspaceServer

    def _trusted_host(self) -> bool:
        host = self.headers.get("Host", "")
        return host in {f"127.0.0.1:{self.server.server_address[1]}",
                        f"localhost:{self.server.server_address[1]}"}

    def _json(self, status: int, body: Mapping[str, Any]) -> None:
        raw = json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        if not self._trusted_host():
            self._json(403, {"error": "Local host required"})
            return
        try:
            self._get_local()
        except (ValueError, TypeError, KeyError, OSError, sqlite3.Error) as exc:
            self._json(400, {"error": str(exc)[:500]})

    def _get_local(self) -> None:
        route = urlsplit(self.path)
        if route.path == "/":
            raw = HTML.replace("__TOKEN__", self.server.token).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)
            return
        if route.path == "/api/state":
            session = parse_qs(route.query).get("session", [""])[0]
            active = active_snapshot(self.server.root)
            with _connect(self.server.db_path) as db:
                rows = db.execute("SELECT id,created_at FROM sessions ORDER BY created_at DESC LIMIT 100").fetchall()
            selected = session if any(x["id"] == session for x in rows) else (rows[0]["id"] if rows else "")
            messages = history(self.server.db_path, selected) if selected else []
            latest = next((x for x in reversed(messages) if x["role"] == "assistant"), None)
            memory_scope = latest["project_sha256"] if latest else "global"
            self._json(200, {"active": active[1] if active else None,
                             "reviews": active_reviews(self.server.root),
                             "sessions": [dict(x) for x in rows],
                             "messages": messages,
                             "memories": memories(self.server.db_path, memory_scope or "global")})
            return
        if route.path == "/api/source":
            name = parse_qs(route.query).get("name", [""])[0]
            active = active_snapshot(self.server.root)
            if not active or name not in active[1]["source_files"]:
                self._json(404, {"error": "Source document not found"})
                return
            raw = (self.server.root / "snapshots" / active[1]["graph_sha256"] / name).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(raw)
            return
        self._json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        if not self._trusted_host():
            self._json(403, {"error": "Local host required"})
            return
        if self.headers.get("X-Workbench-Token") != self.server.token:
            self._json(403, {"error": "Invalid local session token"})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 15_000_000:
                raise ValueError("Request body size is invalid")
            body = parse_json(self.rfile.read(size).decode("utf-8"))
            if not isinstance(body, dict):
                raise ValueError("Expected JSON object")
            result: dict[str, Any]
            if self.path == "/api/session":
                result = {"session_id": new_session(self.server.db_path)}
            elif self.path == "/api/import":
                files = body.get("files")
                if not isinstance(files, dict) or not all(isinstance(x, str) and isinstance(v, str) for x, v in files.items()):
                    raise ValueError("Select graph.json and its source Markdown files")
                raw = files.get("graph.json", "").encode("utf-8")
                sources = {name: data.encode("utf-8") for name, data in files.items() if name != "graph.json"}
                if len(raw) > MAX_GRAPH_BYTES or any(len(x) > MAX_SOURCE_BYTES for x in sources.values()):
                    raise ValueError("Graph import exceeds supported size")
                result = import_graph(self.server.root, raw, sources,
                                      site_version=str(body.get("site_version", "unreported")))
            elif self.path == "/api/chat":
                report = body.get("report")
                result = ask(self.server.root, self.server.db_path,
                             session_id=str(body.get("session_id", "")), question=str(body.get("question", "")),
                             report=Path(report) if isinstance(report, str) and report else None,
                             model=self.server.model, ollama_url=self.server.ollama_url,
                             use_model=body.get("use_model") is True)
            elif self.path == "/api/reviews/import":
                content = body.get("content")
                if not isinstance(content, str) or len(content.encode("utf-8")) > MAX_REVIEW_BYTES:
                    raise ValueError("Invalid review export")
                result = import_reviews(self.server.root, content.encode("utf-8"))
            elif self.path == "/api/memory":
                result = remember(self.server.db_path, str(body.get("scope", "")), str(body.get("content", "")))
            elif self.path == "/api/memory/delete":
                result = {"deleted": forget(self.server.db_path, str(body.get("id", "")))}
            elif self.path == "/api/memory/edit":
                result = {"edited": edit_memory(self.server.db_path, str(body.get("id", "")),
                                                 str(body.get("content", "")))}
            else:
                self._json(404, {"error": "Not found"})
                return
            self._json(200, result)
        except (ValueError, TypeError, KeyError, OSError, sqlite3.Error) as exc:
            self._json(400, {"error": str(exc)[:500]})


def main() -> None:
    parser = argparse.ArgumentParser(description="Local automotive graph and project chat")
    parser.add_argument("--data", type=Path, default=Path("output/knowledge-chat"))
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument("--model", default="qwen3.5:2b")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    args = parser.parse_args()
    server = WorkspaceServer(("127.0.0.1", args.port), args.data, args.model, args.ollama_url)
    print(f"Automotive Workbench: http://127.0.0.1:{args.port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()
