#!/usr/bin/env python3
"""Turn one /grill round into a self-contained HTML page for the dashboard's "To review" tab. Stdlib only.

    python3 grill_page.py ROUND.json OUT.html

ROUND.json:
    {"title": "Grill: <the work>", "round": 2,
     "context": "one or two plain sentences on what is being decided",
     "settled": ["<question> -> <answer>", ...],                    # decided in earlier rounds
     "questions": [{"title": "...", "body": "...", "recommend": "...",
                    "options": ["200 patients", {"label": "500 patients", "detail": "a day more GPU"}],  # optional
                    "multi": false}, ...],                           # optional; true = tick any number
     "spec": "<markdown of the one-page spec>"}                      # final round only; questions may be []

Body and spec text are escaped; blank lines make paragraphs, lines starting "- " make bullets, `x` and **x**
work inline.

Each question is answerable on the page. With "options", Phil picks one (or ticks several when "multi"); the
recommended option starts selected, so "recommend" must equal one option label (a list of labels when "multi").
Every question also has "Other", whose text box starts filled with the recommendation for Phil to edit.
Without "options" the choice is just "Recommended" or "Other". Any answer that differs from the recommendation
becomes a "Q2: <answer>" line, which the dashboard's To review tab copies into its comment box (the page runs in
a sandboxed frame and posts the lines to the dashboard). Approve with no lines = yes to every recommendation;
on the final round, the spec is approved.
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

CSS = """body{font:15px/1.5 -apple-system,system-ui,sans-serif;max-width:860px;margin:24px auto;padding:0 16px;color:#1d1d1f}
h1{font-size:22px;margin:0 0 4px}.sub{color:#666;margin-bottom:16px}
.how{background:#f2f6ff;border:1px solid #c9d8ff;border-radius:8px;padding:10px 14px;margin:12px 0 20px}
.q{border:1px solid #ddd;border-radius:8px;padding:12px 16px;margin:14px 0}
.q h2{font-size:17px;margin:0 0 6px}.rec{background:#f3fbf3;border-left:4px solid #3a9a3a;padding:6px 10px;margin-top:8px}
details{margin:10px 0 18px}pre{white-space:pre-wrap;background:#fafafa;border:1px solid #eee;border-radius:6px;padding:12px}
code{background:#f2f2f2;padding:0 3px;border-radius:3px}ul{margin:4px 0 4px 20px;padding:0}
.ans{margin-top:10px}.ans label{display:block;padding:3px 0;cursor:pointer}.ans .d{color:#666;font-size:13px;margin-left:4px}
.tag{font-size:12px;color:#3a9a3a;font-weight:600;margin-left:6px}
.ans textarea{display:block;width:100%;box-sizing:border-box;min-height:48px;margin:4px 0 0 22px;max-width:calc(100% - 22px);font:inherit}
#out{background:#fffbea;border:1px solid #ecd98b;border-radius:8px;padding:10px 14px;margin:20px 0}#out pre{margin:6px 0 0;background:#fff}"""

# Runs in the page. Builds "Qn: answer" lines for answers that differ from the recommendation and posts them
# to the dashboard (the parent frame); the dashboard sends back its saved comment on load so choices survive.
JS = r"""
const QS = JSON.parse(document.getElementById('qdata').textContent);
let live = false;  // post only after the dashboard restored the saved answers, or Phil changed one
function el(i){ return document.querySelectorAll(`[name="q${i}"]`); }
function answer(i){
  const q = QS[i-1], other = document.getElementById(`o${i}`), txt = document.getElementById(`t${i}`).value.trim();
  if(q.multi){
    const picked = [...el(i)].filter(x=>x.checked && x.value!=='__other').map(x=>x.value);
    const same = picked.length===q.rec.length && picked.every(v=>q.rec.includes(v)) && !(other.checked && txt);
    if(same) return null;
    const parts = picked.concat(other.checked && txt ? ['other: '+txt] : []);
    return parts.length ? parts.join('; ') : 'none of these';
  }
  const sel = [...el(i)].find(x=>x.checked);
  if(!sel) return null;
  if(sel.value==='__other') return txt && txt!==q.rec ? txt : null;
  return sel.value===q.rec ? null : sel.value;
}
function lines(){ const out=[]; QS.forEach((q,k)=>{ const a=answer(k+1); if(a!==null) out.push(`Q${k+1}: ${a.replace(/\s*\n\s*/g,' ')}`); }); return out; }
function sync(){
  QS.forEach((q,k)=>{ const i=k+1, o=document.getElementById(`o${i}`); document.getElementById(`t${i}`).style.display=o.checked?'':'none'; });
  const ls = lines();
  document.getElementById('outl').textContent = ls.length ? ls.join('\n') : 'nothing changed: every recommendation stands';
  if(live && window.parent!==window) window.parent.postMessage({wd:'grill-answer', lines:ls}, '*');
}
function restore(comment){
  (comment||'').split('\n').forEach(l=>{ const m=l.match(/^Q(\d+):\s*(.*)$/); if(!m) return; const i=+m[1], q=QS[i-1]; if(!q) return;
    const v=m[2].trim(), t=document.getElementById(`t${i}`), o=document.getElementById(`o${i}`);
    if(q.multi){ let rest=[]; const parts=v==='none of these'?[]:v.split(/;\s*/);
      el(i).forEach(x=>{ if(x.value!=='__other') x.checked=false; }); o.checked=false;
      parts.forEach(p=>{ const x=[...el(i)].find(x=>x.value===p); if(x&&x.value!=='__other') x.checked=true; else rest.push(p.replace(/^other:\s*/,'')); });
      if(rest.length){ o.checked=true; t.value=rest.join('; '); } }
    else { const x=[...el(i)].find(x=>x.value===v && x.value!=='__other'); if(x) x.checked=true; else { o.checked=true; t.value=v; } } });
  live = true; sync();
}
function copyAll(){
  const head = JSON.parse(document.getElementById('gtitle').textContent);
  const body = QS.map((q,k)=>{ const a=answer(k+1), rec=Array.isArray(q.rec)?q.rec.join('; '):q.rec;
    return `Q${k+1} (${q.title}): ${a===null ? rec+' [recommended]' : a.replace(/\s*\n\s*/g,' ')}`; });
  const t = [head].concat(body).join('\n'), btn = document.getElementById('cp'), pre = document.getElementById('cpt');
  const sel = ()=>{ pre.textContent=t; pre.style.display=''; const r=document.createRange(); r.selectNodeContents(pre);
    getSelection().removeAllRanges(); getSelection().addRange(r); btn.textContent='selected: press Cmd+C'; };
  const legacy = ()=>{ const ta=document.createElement('textarea'); ta.value=t; document.body.appendChild(ta); ta.select();
    let ok=false; try{ ok=document.execCommand('copy'); }catch(e){} ta.remove(); ok ? btn.textContent='copied' : sel(); };
  (navigator.clipboard ? navigator.clipboard.writeText(t) : Promise.reject()).then(()=>btn.textContent='copied', legacy);
}
window.addEventListener('message', e=>{ if(e.source===window.parent && e.data && e.data.wd==='grill-restore') restore(e.data.comment); });
const touched = ()=>{ live = true; sync(); };
document.addEventListener('input', touched); document.addEventListener('change', touched);
sync();
if(window.parent!==window) window.parent.postMessage({wd:'grill-ready'}, '*');
"""


def options(q: dict, i: int) -> tuple[list[tuple[str, str]], object]:
    """(label, detail) pairs and the recommendation in the form the page script compares against."""
    raw = q.get("options") or []
    opts = [(o, "") if isinstance(o, str) else (str(o.get("label", "")), str(o.get("detail", ""))) for o in raw]
    rec = q.get("recommend", "")
    labels = [l for l, _ in opts]
    if q.get("multi") and opts:
        rec = [rec] if isinstance(rec, str) else list(rec or [])
        missing = [r for r in rec if r not in labels]
    else:
        missing = [rec] if opts and rec not in labels else []
    if missing:
        raise SystemExit(f"ERROR: Q{i} recommends {missing!r}, which is not one of its options {labels!r}")
    return opts, rec


def answer_form(q: dict, i: int) -> tuple[str, dict]:
    opts, rec = options(q, i)
    multi = bool(q.get("multi")) and bool(opts)
    kind = "checkbox" if multi else "radio"
    rows = []
    if not opts:  # free-form question: keep the recommendation, or write something else
        rows.append(f"<label><input type='radio' name='q{i}' value='{html.escape(str(rec), quote=True)}' checked> "
                    f"Recommended<span class='tag'>default</span></label>")
    for label, detail in opts:
        on = (label in rec) if multi else (label == rec)
        rows.append(f"<label><input type='{kind}' name='q{i}' value=\"{html.escape(label, quote=True)}\"{' checked' if on else ''}> "
                    f"{inline(label)}{'<span class=tag>recommended</span>' if on else ''}"
                    f"{f'<span class=d>— {inline(detail)}</span>' if detail else ''}</label>")
    prefill = "" if multi else (rec if isinstance(rec, str) else "")
    rows.append(f"<label><input type='{kind}' name='q{i}' id='o{i}' value='__other'> Other{' (add your own)' if multi else ''}</label>"
                f"<textarea id='t{i}' placeholder='your answer'>{html.escape(prefill)}</textarea>")
    return "<div class='ans'>" + "".join(rows) + "</div>", {"multi": multi, "rec": rec}


def inline(s: str) -> str:
    s = html.escape(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)


def block(text: str) -> str:
    out = []
    for para in re.split(r"\n\s*\n", (text or "").strip()):
        lines = [l for l in para.splitlines() if l.strip()]
        if not lines:
            continue
        if all(l.lstrip().startswith("- ") for l in lines):
            out.append("<ul>" + "".join(f"<li>{inline(l.lstrip()[2:])}</li>" for l in lines) + "</ul>")
        else:
            out.append("<p>" + "<br>".join(inline(l) for l in lines) + "</p>")
    return "".join(out)


def build(r: dict) -> str:
    qs, spec = r.get("questions") or [], r.get("spec") or ""
    if not qs and not spec:
        raise SystemExit("ERROR: the round has no questions and no spec")
    title = r.get("title") or "Grill"
    rnd = r.get("round")
    sub = (f"Round {int(rnd)} · " if rnd else "") + (f"{len(qs)} question{'s' * (len(qs) != 1)}" if qs else "final check")
    if qs:
        how = ("<b>How to answer.</b> The recommended answers start selected. Change any you want: pick another "
               "option, or <b>Other</b> to edit the text. Your changes go into the comment box above as lines like "
               "<i>Q2: 500 patients</i>; then press <b>Needs changes</b>. <b>Approve</b> with nothing changed = yes "
               "to every recommendation below. To answer in chat instead, press <b>Copy all answers for chat</b> at the bottom and paste.")
    else:
        how = ("<b>How to answer.</b> <b>Approve</b> = the spec below is right and the build can start. "
               "<b>Needs changes</b> = say what is wrong in the comment and you get a revised page.")
    parts = [f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title>",
             f"<style>{CSS}</style></head><body><h1>{html.escape(title)}</h1><div class='sub'>{html.escape(sub)}</div>"]
    if r.get("context"):
        parts.append(block(r["context"]))
    parts.append(f"<div class='how'>{how}</div>")
    if r.get("settled"):
        parts.append(f"<details><summary>Settled so far ({len(r['settled'])})</summary><ul>"
                     + "".join(f"<li>{inline(s)}</li>" for s in r["settled"]) + "</ul></details>")
    data = []
    for i, q in enumerate(qs, 1):
        form, d = answer_form(q, i)
        data.append({**d, "title": str(q.get("title", ""))})
        rec = q.get("recommend", "")
        rec_txt = "; ".join(rec) if isinstance(rec, list) else str(rec)
        parts.append(f"<div class='q'><h2>Q{i} · {inline(q.get('title', ''))}</h2>{block(q.get('body', ''))}"
                     f"<div class='rec'><b>Recommended:</b> {inline(rec_txt)}</div>{form}</div>")
    if qs:
        parts.append("<div id='out'><b>Your answers</b> (also copied into the dashboard's comment box) "
                     "<button id='cp' type='button' onclick='copyAll()'>Copy all answers for chat</button>"
                     "<pre id='outl'></pre><pre id='cpt' style='display:none'></pre></div>")
        qjson = json.dumps(data).replace("<", "\\u003c")
        parts.append(f"<script type='application/json' id='gtitle'>{json.dumps(title + ' · ' + sub).replace('<', chr(92) + 'u003c')}</script>")
        parts.append(f"<script type='application/json' id='qdata'>{qjson}</script><script>{JS}</script>")
    if spec:
        parts.append(f"<h2>The spec</h2><pre>{html.escape(spec)}</pre>")
    parts.append("</body></html>")
    return "\n".join(parts)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[2], file=sys.stderr)
        return 2
    page = build(json.loads(Path(argv[0]).read_text()))
    Path(argv[1]).write_text(page)
    print(argv[1])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
