"""Item pages (one per question or feature) and method pages, generated from item files.

Every page is flat in planning/dashboard/ so the review server can serve the folder as one site.
Browser storage keys all start with "wd:" (the front door shares one origin across apps).
"""
from __future__ import annotations

import html
import re
import json
from pathlib import Path

E = html.escape

CSS = """
:root{--bg:#f6f7f9;--panel:#fff;--ink:#1c2230;--muted:#5d6676;--line:#e2e5ea;--chip:#eef1f5;
--yes:#1f8a4c;--yes-bg:#e9f7ef;--no:#5d6676;--no-bg:#eef1f5;--tie:#1a6fd1;--tie-bg:#eaf3ff;--gap:#b4540a;--gap-bg:#fff4e8;--run:#7b3fe4;--run-bg:#f2ebff;--bad:#c0322b;--bad-bg:#fdecec}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#12151b;--panel:#1b2029;--ink:#e6e9ef;--muted:#9aa3b2;--line:#2b313c;--chip:#262c37;
--yes:#5fd08f;--yes-bg:#16291f;--no:#9aa3b2;--no-bg:#262c37;--tie:#6aa8ff;--tie-bg:#182638;--gap:#f3a35b;--gap-bg:#33261a;--run:#b48cff;--run-bg:#251d38;--bad:#ff7b73;--bad-bg:#351c1c}}
:root[data-theme="dark"]{--bg:#12151b;--panel:#1b2029;--ink:#e6e9ef;--muted:#9aa3b2;--line:#2b313c;--chip:#262c37;
--yes:#5fd08f;--yes-bg:#16291f;--no:#9aa3b2;--no-bg:#262c37;--tie:#6aa8ff;--tie-bg:#182638;--gap:#f3a35b;--gap-bg:#33261a;--run:#b48cff;--run-bg:#251d38;--bad:#ff7b73;--bad-bg:#351c1c}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
header{background:var(--panel);border-bottom:1px solid var(--line);padding:14px 16px}header h1{font-size:19px;margin:4px 0}
.muted{color:var(--muted)}.small{font-size:12px}a{color:var(--tie)}
.tag{display:inline-block;font-size:11px;font-weight:700;border-radius:10px;padding:1px 8px;margin-right:4px;background:var(--gap-bg);color:var(--gap)}
.tag.ok{background:var(--yes-bg);color:var(--yes)}
main{max-width:1300px;margin:0 auto;padding:10px 16px 80px}section{margin:22px 0}
h2{font-size:14px;text-transform:uppercase;letter-spacing:.04em;margin:0 0 8px}
.box{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:10px 14px;margin:6px 0;position:relative}
.answer{border-left:5px solid var(--tie);font-size:15px}.draft{border-left:5px solid var(--gap)}
.wrap{overflow-x:auto}table.g{border-collapse:separate;border-spacing:4px;width:100%}
table.g th{font-size:12px;color:var(--muted);font-weight:600;text-align:left;padding:4px 6px;vertical-align:bottom}
table.g td{vertical-align:top;border-radius:6px;padding:6px 8px;font-size:12.5px;position:relative;min-width:90px}
td.method{font-weight:700;font-size:13px;padding-top:14px}td.row{background:var(--panel);border:1px solid var(--line);min-width:190px}
.sub{font-weight:400;color:var(--muted);font-size:12px}.v{font-weight:700;display:block}
.c-yes{background:var(--yes-bg);border-left:4px solid var(--yes)}.c-tie{background:var(--tie-bg);border-left:4px solid var(--tie)}
.c-no{background:var(--no-bg);border-left:4px solid var(--no)}.c-gap{border:1px dashed var(--gap);color:var(--gap)}
.c-running,.c-waiting{background:var(--run-bg);border-left:4px solid var(--run)}.c-na{color:var(--muted);border:1px dotted var(--line)}
.c-done{background:var(--yes-bg);border-left:4px solid var(--yes)}.c-doing{background:var(--run-bg);border-left:4px solid var(--run)}
.c-todo{border:1px dashed var(--gap)}.c-blocked{background:var(--bad-bg);border-left:4px solid var(--bad)}
.legend span{display:inline-block;margin-right:10px;font-size:12px}.legend i{display:inline-block;width:12px;height:12px;border-radius:3px;vertical-align:-2px;margin-right:4px}
.dec{border-left:4px solid var(--gap)}.feat{border-left:4px solid var(--run)}
.chip{display:inline-block;background:var(--chip);border-radius:10px;padding:1px 8px;font-size:11.5px;margin:2px 4px 2px 0}
.chip.unmerged{background:var(--gap-bg);color:var(--gap)}.chip.permanent{background:var(--yes-bg);color:var(--yes)}
code{font:12px ui-monospace,Menlo,monospace;word-break:break-all}
.cwrap{position:absolute;top:3px;right:3px}button.cic{background:none;border:0;cursor:pointer;font-size:12px;opacity:.3;filter:grayscale(1);padding:0}
button.cic:hover{opacity:.9}button.cic.has{opacity:1;filter:none}
.pop{position:absolute;z-index:30;right:0;top:18px;width:300px;background:var(--panel);border:1px solid var(--tie);border-radius:8px;padding:6px;box-shadow:0 6px 20px rgba(0,0,0,.2)}
.pop textarea,textarea.big{width:100%;min-height:80px;background:var(--bg);color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:6px;font:13px/1.4 inherit}
button.b{background:var(--chip);color:var(--ink);border:1px solid var(--line);border-radius:5px;font-size:12px;cursor:pointer;padding:2px 10px;margin-top:4px}
button.pri{background:var(--tie);color:#fff;border-color:var(--tie)}
"""

# Comment icons + approve; state in browser storage under wd: keys (saved by the review server when served).
JS = r"""
const $=id=>document.getElementById(id);const esc=s=>String(s??"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/"/g,"&quot;");
const LABELS={};
function lsGet(k,d){try{return JSON.parse(localStorage.getItem(k)||"null")??d}catch(e){return d}}
function lsSet(k,v){try{localStorage.setItem(k,JSON.stringify(v))}catch(e){}}
let ITEM=null,WORDING=null,DRAFT=null,CK=null,C={};
function initItem(id,wording,saved,draft){ITEM=id;WORDING=wording;DRAFT=draft||null;CK="wd:c:"+id;C=lsGet(CK,{});
 for(const [k,v] of Object.entries(saved||{})) if(!C[k]) C[k]={text:v.text,label:v.label,at:v.at};
 wire();}
function icon(key,label){LABELS[key]=label;return `<span class="cwrap"><button class="cic" data-key="${key}" title="Comment: ${esc(label)}" onclick="pop(event,this)">💬</button><span class="pop" hidden><textarea class="cm" data-key="${key}" data-label="${esc(label)}" placeholder="${esc(label).slice(0,70)}…"></textarea><button class="b" onclick="this.parentElement.hidden=true">done</button></span></span>`}
function pop(e,b){e.stopPropagation();const p=b.nextElementSibling,open=p.hidden;document.querySelectorAll(".pop").forEach(x=>x.hidden=true);p.hidden=!open;if(open)p.querySelector("textarea").focus()}
document.addEventListener("click",e=>{if(!e.target.closest(".cwrap"))document.querySelectorAll(".pop").forEach(x=>x.hidden=true)});
function icons(){document.querySelectorAll("button.cic").forEach(b=>b.classList.toggle("has",!!((C[b.dataset.key]||{}).text||"").trim()))}
function wire(){document.querySelectorAll("[data-icon]").forEach(el=>{el.insertAdjacentHTML("afterbegin",icon(el.dataset.icon,el.dataset.label||el.dataset.icon));el.removeAttribute("data-icon")});
 document.querySelectorAll("textarea.cm,textarea.big").forEach(t=>{const k=t.dataset.key;t.value=(C[k]||{}).text||"";
 t.oninput=()=>{C[k]={text:t.value,label:t.dataset.label,at:new Date().toISOString()};icons();lsSet(CK,C);stat()}});icons();stat()}
function saving(){return /mine\[k\]/.test(String(Storage.prototype.setItem))}   // the review server's save script is present
function stat(){const n=Object.values(C).filter(c=>c.text&&c.text.trim()).length;const s=$("cstat");if(!s)return;
 s.textContent=`${n} comment${n===1?"":"s"} · `+(saving()?"saved to the mount as you type":location.protocol==="file:"?"opened as a file: comments stay in this browser":"NOT SAVED on this page: open it from the dashboard")}
function approve(){const a=lsGet("wd:approve",{});a[ITEM]={at:new Date().toISOString(),wording:WORDING};lsSet("wd:approve",a);$("apr").outerHTML='<span class="tag ok">approved, applied at the next refresh</span>'}
function acceptDraft(){const a=lsGet("wd:accept-draft",{});a[ITEM]={at:new Date().toISOString(),draft:DRAFT};lsSet("wd:accept-draft",a);$("acc").outerHTML='<span class="tag ok">accepted, applied at the next refresh</span>'}

"""

STATE_LABEL = {"yes": "helps, held up", "tie": "level", "no": "no gain", "running": "running",
               "waiting": "waiting on you", "gap": "not run", "na": "—",
               "done": "done", "doing": "in progress", "todo": "to do", "blocked": "blocked"}


def _cell(c: dict, key: str, label: str) -> str:
    st = c.get("state", "gap")
    v = c.get("value") or STATE_LABEL.get(st, st)
    extra = " · ".join(x for x in [c.get("note", ""), ("session " + c["session"]) if c.get("session") else "",
                                    ("code " + c["commit"]) if c.get("commit") else "",
                                    "" if c.get("planned", True) else "exploratory, not pre-registered"] if x)
    return (f'<td class="c-{E(st)}" data-icon="{E(key)}" data-label="{E(label)}"><span class="v">{E(v)}</span>'
            f'{f"<span class=small>{E(extra)}</span>" if extra else ""}</td>')


def _grid(g: dict) -> str:
    cols = g.get("columns", [])
    h = "<tr><th></th>" + "".join(f'<th data-icon="col-{i}" data-label="Column: {E(c)}" style="position:relative">{E(c)}</th>' for i, c in enumerate(cols)) + "</tr>"
    ri = 0
    for grp in g.get("groups", []):
        h += f'<tr><td class="method" colspan="{len(cols) + 1}">{E(grp.get("method", ""))}</td></tr>'
        for r in grp.get("rows", []):
            ri += 1
            h += (f'<tr><td class="row" data-icon="row-{ri}" data-label="Row: {E(r.get("label", ""))}">{E(r.get("label", ""))}'
                  f'<div class="sub">{E(r.get("sub", ""))}</div></td>')
            cells = r.get("cells", [])
            for ci in range(len(cols)):
                c = cells[ci] if ci < len(cells) else {"state": "gap"}
                h += _cell(c, f"row-{ri}-c{ci}", f'{r.get("label", "")} · {cols[ci]}')
            h += "</tr>"
    legend = "".join(f'<span><i class="c-{k}"></i>{v}</span>' for k, v in
                     [("yes", "helps, held up"), ("tie", "level"), ("no", "no gain"), ("running", "running / waiting on you"), ("gap", "not run")])
    return f'<div class="legend">{legend}</div><div class="wrap"><table class="g">{h}</table></div>'


def _findings(fs: list) -> str:
    return "".join(f'<div class="box c-{E(f.get("state", "na"))}" data-icon="f-{i}" data-label="Finding: {E(f.get("text", "")[:60])}">'
                   f'<b>{E(f.get("number", ""))}</b> {E(f.get("text", ""))}'
                   + (f"<div class=small>{E(f.get('note', ''))}</div>" if f.get("note") else "") + '</div>'
                   for i, f in enumerate(fs))


def _checklist(cl: list) -> str:
    return "".join(f'<div class="box c-{E(s.get("state", "todo"))}" data-icon="s-{i}" data-label="Step: {E(s.get("step", "")[:60])}">'
                   f'<b>{E(STATE_LABEL.get(s.get("state", "todo"), s.get("state", "")))}</b> · {E(s.get("step", ""))}'
                   + (f" <code>{E(s['commit'])}</code>" if s.get("commit") else "") + '</div>'
                   for i, s in enumerate(cl))


def item_body(it: dict, by_id: dict, sessions: list, generated: str) -> str:
    approved = bool(it.get("approved")) and not it.get("approved_stale")
    lay = it.get("layout") or ("grid" if it.get("grid") else "findings" if it.get("findings") else "checklist" if it.get("checklist") else None)
    body = {"grid": lambda: _grid(it.get("grid", {})), "findings": lambda: _findings(it.get("findings", [])),
            "checklist": lambda: _checklist(it.get("checklist", []))}.get(lay, lambda: '<div class="muted">No results recorded yet.</div>')()
    res_title = {"grid": "What's been run", "findings": "What we've found", "checklist": "Build steps"}.get(lay, "Results")
    dr = it.get("draft") or {}
    draft_html = ""
    if dr:
        parts = "".join(f'<div><b>{E(k)}:</b> {E(v)}</div>' for k, v in dr.items() if k in ("title", "why", "answer"))
        draft_html = (f'<div class="box draft"><b>Proposed change, waiting on you</b> <span class="small muted">by {E(dr.get("by", "?"))}, {E(dr.get("at", ""))}</span>'
                      f'{parts}<button class="b pri" id="acc" onclick="acceptDraft()">Accept</button> <span class="small muted">or edit via the 💬 on the answer</span></div>')
    decs = [d for d in it.get("decisions", []) if not d.get("closed")]
    dec_html = "".join(f'<div class="box dec" data-icon="dec-{E(d.get("id", str(i)))}" data-label="Decision: {E(d.get("text", "")[:80])}">'
                       f'<span class="small muted">{E(d.get("kind", "decision"))} · since {E(d.get("since", "?"))}</span><br><b>{E(d.get("text", ""))}</b>'
                       + (f"<div class=small>{E(d.get('detail', ''))}</div>" if d.get("detail") else "") + '</div>'
                       for i, d in enumerate(decs)) or '<div class="muted">none open</div>'
    runs_html = "".join(f'<div class="box"><b>{E(r.get("state_label", r.get("state", "?")))}</b> · {E(r.get("label", ""))} '
                        f'<span class="small muted">· {E(r.get("machine", "?"))}{" · " + E(r.get("summary")) if r.get("summary") else ""}</span>'
                        + (f"<div class=small><code>{E(r['readback'])}</code></div>" if r.get("readback") else "") + '</div>'
                        for r in it.get("runs", [])) or '<div class="muted">no runs listed</div>'
    code_html = "".join(f'<div class="box feat" data-icon="code-{i}" data-label="Code: {E(c.get("what", ""))}"><b>{E(c.get("what", ""))}</b> '
                        f'<span class="chip {E(c.get("state", ""))}">{E(c.get("state", ""))}</span>'
                        f'{"<span class=chip>make permanent?</span>" if c.get("promote") else ""}'
                        f'<div class="small"><code>{E(c.get("where", ""))}</code></div>'
                        f'{f"<div class=small muted>used by: " + ", ".join(E(by_id.get(u, {}).get("title", u)) for u in c.get("used_by", [])) + "</div>" if c.get("used_by") else ""}</div>'
                        for i, c in enumerate(it.get("code", []))) or '<div class="muted">none listed</div>'
    links = "".join(f'<a href="index.html#i={E(l)}">{E(by_id[l]["title"])}</a> · ' for l in it.get("links", []) if l in by_id)
    methods = "".join(f'<a class="chip" href="method-{E(m)}.html">{E(m)}</a>' for m in it.get("methods", []))
    sess = "".join(f'<div class="small">{E(s["bucket"])} · {E(s["name"])} <span class="muted">· {E(s["host"])} · <code>claude attach {E(s["id"])}</code></span></div>'
                   for s in sessions) or '<div class="small muted">none in the last 3 days</div>'
    head_tag = ('<span class="tag ok">wording approved ' + E(str(it["approved"].get("at", ""))) + '</span>') if approved else \
        '<span class="tag">draft wording</span><button class="b pri" id="apr" onclick="approve()">Approve wording</button>'
    return f"""<div class="itemview"><header><div class="small"><a href="index.html">← dashboard</a> · {E(it.get("kind", ""))} · program <b>{E(it.get("program", "?"))}</b> · built {E(generated)}</div>
<h1>{E(it.get("title", ""))}</h1><div>{E(it.get("why", ""))}</div>
<div style="margin-top:6px">{head_tag} {methods} <span class="small muted" id="cstat"></span></div></header>
<main>
<section><h2>Answer so far</h2><div class="box answer" data-icon="answer" data-label="Answer so far">{E(it.get("answer") or "No answer yet.")}</div>
<div class="small muted">Now: {E(it.get("status", ""))}</div>{draft_html}</section>
<section><h2>{res_title}</h2>{body}</section>
{f'<section><h2>Results</h2>{_findings(it["findings"])}</section>' if lay != "findings" and it.get("findings") else ""}
<section><h2>Decisions for you</h2>{dec_html}</section>
<section><h2>Runs</h2>{runs_html}</section>
<section><h2>Code</h2>{code_html}</section>
<section><h2>Sessions on it</h2>{sess}</section>
<section><h2>Connected</h2><div class="small">{links or '<span class="muted">no links</span>'}</div></section>
<section><h2>Your overall comments</h2><textarea class="big" data-key="overall" data-label="Overall comments" placeholder="Is this the right question? What's missing?"></textarea></section>
</main></div>"""


def draft_seen(it: dict) -> dict | None:
    """The proposed wording exactly as the page shows it; Accept stores this and the builder compares it."""
    d = it.get("draft") or {}
    seen = {k: d[k] for k in ("title", "why", "answer") if k in d}
    return seen or None


def wording_hash(it: dict) -> str:
    import hashlib
    return hashlib.sha1(json.dumps([it.get(k) for k in ("title", "why", "answer")], ensure_ascii=False).encode()).hexdigest()[:12]


def item_page(it: dict, by_id: dict, sessions: list, saved_comments: dict, mount_js: str, generated: str) -> str:
    """Standalone file for opening locally; on the served site the same body opens inside index.html."""
    body = item_body(it, by_id, sessions, generated)
    wording = json.dumps({k: it.get(k) for k in ("title", "why", "answer")})
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(it.get("title", it["id"]))[:60]}</title><script>{mount_js}</script><style>{CSS}</style></head><body>
{body}<script>{JS}
document.addEventListener("DOMContentLoaded",()=>initItem({json.dumps(it["id"])},{wording},{json.dumps(saved_comments)},{json.dumps(draft_seen(it))}));</script></body></html>"""


def method_page(name: str, items: list, mount_js: str, generated: str) -> str:
    rows = "".join(f'<div class="box"><a href="index.html#i={E(i["id"])}"><b>{E(i["title"])}</b></a> <span class="small muted">· {E(i.get("program", ""))}</span>'
                   f'<div class="small">{E(i.get("answer") or i.get("status", ""))}</div></div>' for i in items)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Method: {E(name)}</title><script>{mount_js}</script><style>{CSS}</style></head><body>
<header><div class="small"><a href="index.html">← dashboard</a> · built {E(generated)}</div><h1>Every question using: {E(name)}</h1></header>
<main>{rows}</main></body></html>"""


def scoped_css(css: str, scope: str = ".itemview") -> str:
    """Prefix top-level rules so the item view can sit inside the status page without restyling it."""
    out = []
    for m in re.finditer(r"\s*(@media[^{]*\{(?:[^{}]*\{[^}]*\})*\s*\}|[^{}@]+\{[^{}]*\})", css):
        rule = m.group(1).strip()
        if rule.startswith("@") or rule.startswith(":root"):
            out.append(rule)
            continue
        sel, body = rule.split("{", 1)
        sels = []
        for x in sel.split(","):
            x = x.strip()
            sels.append(scope if x == "body" else f"{scope} {x}" if x != "*" else f"{scope} *")
        out.append(",".join(sels) + "{" + body)
    return "\n".join(out)


def write_atomic(path: Path, text: str) -> None:
    tmp = path.with_name("." + path.name + ".tmp")
    tmp.write_text(text)
    tmp.replace(path)
