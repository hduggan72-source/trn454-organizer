"""
UGC AI Image Organizer — Desktop Edition
=========================================
Runs a local browser UI for organizing images using Claude AI.
Files are read from _inbox and moved (or zipped) to subfolders.

QUICK START:
  1. pip install flask anthropic
  2. Create config_local.py (see config_local.py.example) with your real key
  3. Edit the rest of the CONFIG section below
  4. Double-click run_organizer.bat  (or: python ugc_organizer_desktop.py)
"""

import os, sys, shutil, base64, zipfile, logging, webbrowser, threading
from datetime import datetime
from pathlib import Path

# ════════════════════════════════════════════════════════════════
#  CONFIG  —  Edit everything in this section before running
# ════════════════════════════════════════════════════════════════

# ── API Key ─────────────────────────────────────────────────────
# The real key lives in config_local.py — a file that is NEVER
# committed to Git (see .gitignore), so it's safe even in a public repo.
# First time setup: copy config_local.py.example to config_local.py
# and paste your real key in there.
try:
    from config_local import ANTHROPIC_API_KEY
except ImportError:
    ANTHROPIC_API_KEY = "sk-ant-YOUR-KEY-HERE"
    print("\n  ⚠  config_local.py not found!")
    print("     Copy config_local.py.example to config_local.py")
    print("     and paste your real Anthropic API key inside it.\n")

# ── File Paths ──────────────────────────────────────────────────
# Root folder — your subfolders live inside here
WATCH_PATH = r"C:\Users\Admin\iCloudDrive\iCloudDrive\Workflow - Repository"

# Drop images here to organize them
INBOX_FOLDER = "_inbox"

# ── Export Mode ─────────────────────────────────────────────────
# "move" → files are moved directly into subfolders (default)
# "zip"  → files are packaged into a ZIP you download at the end
EXPORT_MODE = "move"

# Where to save the ZIP file (only used when EXPORT_MODE = "zip")
ZIP_OUTPUT_PATH = r"C:\Users\Admin\Desktop\UGC-Organized.zip"

# ── File Types ──────────────────────────────────────────────────
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm"}

# ── Categories ──────────────────────────────────────────────────
# Format: "number": ("PREFIX-", "Subfolder Name")
# The prefix is added to the front of every filename in that category.
# The subfolder name is the folder the file moves into.
CATEGORIES = {
     "1": ("BLONDES-",   "BLONDES"),
     "2": ("BRUNETTES-", "BRUNETTES"),
     "3": ("CREFs-",     "CREFs"),
     "4": ("FULLBODY-",  "FULL BODY"),
     "5": ("GINGERS-",   "GINGERS"),
     "6": ("GOTHS-",     "GOTHS"),
     "7": ("JAMES-",     "JAMES"),
     "8": ("MIKAYLA-",   "MIKAYLA"),
     "9": ("STYLE-",     "STYLE BOARDS"),
}

# ════════════════════════════════════════════════════════════════
#  END OF CONFIG  —  No need to edit below this line
# ════════════════════════════════════════════════════════════════

ALL_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
LOG_FILE       = Path(__file__).parent / "organizer_log.txt"

logging.basicConfig(
    filename=LOG_FILE, level=logging.INFO,
    format="%(asctime)s  %(message)s", datefmt="%Y-%m-%d %H:%M:%S",
)

def log(msg):
    print(msg)
    logging.info(msg)

# ── Global State ────────────────────────────────────────────────

files       = []
current_idx = 0
stats       = {"moved": 0, "skipped": 0, "errors": 0}
zip_queue   = []   # used when EXPORT_MODE = "zip"
ugc_root    = Path(WATCH_PATH)
inbox       = ugc_root / INBOX_FOLDER

# ── Flask ───────────────────────────────────────────────────────

try:
    from flask import Flask, jsonify, request, send_file, Response
except ImportError:
    print("\n  Missing library. Run:  pip install flask anthropic\n")
    input("Press Enter to exit...")
    sys.exit(1)

app = Flask(__name__)

def load_files():
    global files, current_idx, zip_queue
    if not inbox.exists():
        inbox.mkdir(parents=True)
    files = sorted([
        f for f in inbox.iterdir()
        if f.is_file() and f.suffix.lower() in ALL_EXTENSIONS
    ])
    current_idx = 0
    zip_queue   = []
    log(f"  Found {len(files)} file(s) in {INBOX_FOLDER}.")

# ── Routes ──────────────────────────────────────────────────────

@app.route("/")
def index():
    return build_page()

@app.route("/api/status")
def api_status():
    return jsonify({
        "export_mode": EXPORT_MODE,
        "has_api_key": bool(ANTHROPIC_API_KEY and "YOUR-KEY" not in ANTHROPIC_API_KEY),
    })

@app.route("/api/current")
def api_current():
    if current_idx >= len(files):
        return jsonify({"done": True, "stats": stats, "export_mode": EXPORT_MODE})
    f = files[current_idx]
    return jsonify({
        "done":     False,
        "index":    current_idx,
        "total":    len(files),
        "filename": f.name,
        "is_video": f.suffix.lower() in VIDEO_EXTENSIONS,
        "stats":    stats,
    })

@app.route("/api/image")
def api_image():
    if current_idx >= len(files):
        return ("", 204)
    f = files[current_idx]
    if f.suffix.lower() in IMAGE_EXTENSIONS:
        return send_file(str(f))
    return ("", 204)

@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    if current_idx >= len(files):
        return jsonify({"suggestion": ""})
    f = files[current_idx]
    if f.suffix.lower() in VIDEO_EXTENSIONS:
        return jsonify({"suggestion": "", "is_video": True})
    if not ANTHROPIC_API_KEY or "YOUR-KEY" in ANTHROPIC_API_KEY:
        return jsonify({"suggestion": "", "error": "No API key set"})
    try:
        import anthropic
        client   = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        ext_map  = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".heic": "image/jpeg",
            ".png": "image/png",  ".gif":  "image/gif",  ".webp": "image/webp",
            ".bmp": "image/jpeg",
        }
        media_type = ext_map.get(f.suffix.lower(), "image/jpeg")
        with open(f, "rb") as fh:
            b64 = base64.standard_b64encode(fh.read()).decode("utf-8")
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=64,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                    {"type": "text",  "text": (
                        "Analyze this image. Return ONLY a short descriptive filename: "
                        "2-4 words, all lowercase, hyphen-separated, no file extension, no extra text. "
                        "Examples: dark-velvet-gown, beach-casual-look, bold-red-outfit."
                    )},
                ],
            }],
        )
        suggestion = msg.content[0].text.strip().lower().replace(" ", "-")
        return jsonify({"suggestion": suggestion})
    except Exception as e:
        log(f"API error: {e}")
        return jsonify({"suggestion": "", "error": str(e)})

@app.route("/api/move", methods=["POST"])
def api_move():
    global current_idx
    data     = request.get_json()
    name     = (data.get("name") or "unnamed").strip().lower().replace(" ", "-")
    choice   = str(data.get("category", ""))
    if choice not in CATEGORIES:
        return jsonify({"error": "Invalid category"}), 400

    f                   = files[current_idx]
    prefix, subfolder   = CATEGORIES[choice]
    final_name          = f"{prefix}{name}{f.suffix.lower()}"
    dest_dir            = ugc_root / subfolder
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file           = dest_dir / final_name

    # Handle duplicate filenames
    if dest_file.exists():
        ts        = datetime.now().strftime("%H%M%S")
        stem      = f"{prefix}{name}_{ts}"
        dest_file = dest_dir / f"{stem}{f.suffix.lower()}"

    try:
        if EXPORT_MODE == "zip":
            # Queue for ZIP export — file stays in inbox until ZIP is built
            zip_queue.append({"src": str(f), "dest": f"{subfolder}/{dest_file.name}"})
            log(f"QUEUED  {f.name}  ->  {subfolder}/{dest_file.name}")
        else:
            # Move directly
            shutil.move(str(f), str(dest_file))
            log(f"MOVED   {f.name}  ->  {subfolder}/{dest_file.name}")

        stats["moved"] += 1
        current_idx    += 1
        return jsonify({"success": True, "dest": dest_file.name, "export_mode": EXPORT_MODE})
    except Exception as e:
        log(f"ERROR   {f.name}  --  {e}")
        stats["errors"] += 1
        return jsonify({"error": str(e)}), 500

@app.route("/api/skip", methods=["POST"])
def api_skip():
    global current_idx
    if current_idx < len(files):
        log(f"SKIP    {files[current_idx].name}")
        stats["skipped"] += 1
        current_idx += 1
    return jsonify({"success": True})

@app.route("/api/export-zip")
def api_export_zip():
    """Build and stream a ZIP of all queued files (ZIP export mode only)."""
    if not zip_queue:
        return jsonify({"error": "Nothing queued"}), 400

    zip_path = Path(ZIP_OUTPUT_PATH)
    zip_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for item in zip_queue:
                src  = Path(item["src"])
                dest = item["dest"]
                if src.exists():
                    zf.write(src, dest)
                    src.unlink()   # remove from inbox after zipping
        log(f"ZIP     Saved {len(zip_queue)} files to {zip_path}")
        return send_file(str(zip_path), as_attachment=True,
                         download_name=zip_path.name)
    except Exception as e:
        log(f"ZIP ERROR: {e}")
        return jsonify({"error": str(e)}), 500

# ── HTML ─────────────────────────────────────────────────────────

def build_page():
    cat_buttons = ""
    for num, (prefix, folder) in CATEGORIES.items():
        cat_buttons += (
            f'<button class="cat-btn" id="cat-{num}" '
            f'onclick="selectCat(\'{num}\')">{folder}</button>\n'
        )
    cats_js = "{\n"
    for num, (prefix, folder) in CATEGORIES.items():
        cats_js += f'  "{num}": "{folder}",\n'
    cats_js += "}"
    html = HTML_TEMPLATE.replace("__CAT_BUTTONS__", cat_buttons)
    html = html.replace("__CATS_JS__", cats_js)
    return html

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>UGC Organizer — Desktop</title>
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --bg:      #07070f;
  --panel:   #0d0d1c;
  --border:  #1c1c35;
  --accent:  #5b4cdb;
  --glow:    #8b79ff;
  --text:    #cccce0;
  --muted:   #4a4a62;
  --teal:    #2dd4a0;
  --red:     #f87171;
  --amber:   #fbbf24;
  --r:       8px;
}
html, body { height: 100%; background: var(--bg); color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 13px; overflow: hidden; }

/* ── Top bar ── */
#topbar {
  position: fixed; top: 0; left: 0; right: 0; height: 44px;
  background: var(--panel); border-bottom: 1px solid var(--border);
  display: flex; align-items: center; padding: 0 18px; gap: 14px; z-index: 10;
}
#app-title { font-size: 12px; font-weight: 700; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--accent); white-space: nowrap; }
#mode-badge {
  font-size: 10px; font-weight: 700; padding: 3px 8px; border-radius: 4px;
  background: rgba(91,76,219,.2); border: 1px solid var(--accent);
  color: var(--accent); letter-spacing: 0.05em; white-space: nowrap;
}
#mode-badge.zip-mode { background: rgba(251,191,36,.12); border-color: var(--amber); color: var(--amber); }
#progress-wrap { flex: 1; height: 3px; background: var(--border); border-radius: 2px; overflow: hidden; }
#progress-fill { height: 100%; background: linear-gradient(90deg, var(--accent), var(--glow)); width: 0%; transition: width .4s; }
#topbar-counter { font-size: 11px; color: var(--muted); white-space: nowrap; font-variant-numeric: tabular-nums; }
#topbar-stats   { font-size: 11px; color: var(--muted); white-space: nowrap; }

/* ── Layout ── */
#layout {
  display: grid; grid-template-columns: 1fr 360px;
  height: 100vh; padding-top: 44px;
}

/* ── Image pane ── */
#img-pane {
  background: #000; display: flex; align-items: center;
  justify-content: center; position: relative; overflow: hidden;
}
#preview { max-width: 100%; max-height: 100%; object-fit: contain; display: none; }
#video-placeholder {
  display: none; flex-direction: column; align-items: center; gap: 12px;
  color: var(--muted);
}
#video-placeholder svg { opacity: .3; }
#scanline {
  position: absolute; top: 0; left: 0; right: 0; height: 2px;
  background: linear-gradient(90deg, transparent, var(--accent), var(--glow), transparent);
  opacity: 0; pointer-events: none;
}
#scanline.active { animation: scan 1.2s ease-in-out forwards; }
@keyframes scan { 0%{top:0;opacity:.8} 100%{top:100%;opacity:0} }

/* ── Side panel ── */
#side {
  background: var(--panel); border-left: 1px solid var(--border);
  display: flex; flex-direction: column; gap: 0; overflow-y: auto;
}
.s-section { padding: 14px 16px; border-bottom: 1px solid var(--border); }
.s-label {
  font-size: 10px; font-weight: 700; letter-spacing: .1em;
  text-transform: uppercase; color: var(--muted); margin-bottom: 8px;
}

/* ── Filename tag ── */
#fname-tag {
  font-size: 11px; color: var(--muted);
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
  word-break: break-all;
}

/* ── Suggestion box ── */
#suggest-box {
  background: var(--bg); border: 1px solid var(--border); border-radius: var(--r);
  padding: 10px 12px; min-height: 48px;
}
#suggest-status { font-size: 11px; color: var(--muted); margin-bottom: 4px; }
.pulse {
  display: inline-block; width: 7px; height: 7px; border-radius: 50%;
  background: var(--accent); animation: pulse .9s ease-in-out infinite;
  vertical-align: middle; margin-right: 5px;
}
@keyframes pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.4;transform:scale(.7)} }
#suggest-text { font-size: 13px; color: var(--teal); font-family: 'Cascadia Code','Fira Code','Consolas',monospace; word-break: break-all; }

/* ── Name input ── */
#name-input {
  width: 100%; background: var(--bg); border: 1px solid var(--border);
  border-radius: var(--r); color: var(--text); font-size: 13px;
  padding: 10px 12px; outline: none;
  font-family: 'Cascadia Code','Fira Code','Consolas',monospace;
}
#name-input:focus { border-color: var(--accent); }
.hint { font-size: 10px; color: var(--muted); margin-top: 5px; }
kbd {
  background: var(--border); border-radius: 3px; padding: 1px 5px;
  font-size: 10px; font-family: inherit;
}

/* ── Category grid ── */
#cat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.cat-btn {
  background: var(--bg); border: 1px solid var(--border); border-radius: 7px;
  color: var(--text); font-size: 11px; font-weight: 600; padding: 10px 6px;
  text-align: center; cursor: pointer; transition: background .12s, border-color .12s;
  letter-spacing: .03em;
}
.cat-btn:hover  { border-color: var(--accent); color: #fff; }
.cat-btn.active { background: var(--accent); border-color: var(--glow); color: #fff; }

/* ── Actions ── */
#actions { display: grid; grid-template-columns: 1fr 2fr; gap: 8px; }
#btn-skip {
  background: transparent; border: 1px solid var(--border); border-radius: var(--r);
  color: var(--muted); font-size: 13px; padding: 12px; cursor: pointer;
}
#btn-skip:hover { border-color: var(--red); color: var(--red); }
#btn-confirm {
  background: var(--border); border: none; border-radius: var(--r);
  color: var(--muted); font-size: 13px; font-weight: 700; padding: 12px;
  cursor: default; transition: background .2s, color .2s;
}
#btn-confirm.ready { background: var(--accent); color: #fff; cursor: pointer; }
#btn-confirm.ready:hover { background: var(--glow); }

/* ── Done screen ── */
#done-screen {
  display: none; position: fixed; inset: 0; background: var(--bg);
  flex-direction: column; align-items: center; justify-content: center;
  gap: 16px; text-align: center;
}
#done-glyph { font-size: 48px; letter-spacing: -2px; opacity: .2; }
#done-screen h2 { font-size: 22px; font-weight: 800; color: #fff; }
.pill {
  display: inline-block; background: var(--panel); border: 1px solid var(--border);
  border-radius: 20px; padding: 5px 14px; font-size: 12px; margin: 3px;
}
#btn-zip {
  margin-top: 8px; background: var(--teal); color: #000;
  font-size: 14px; font-weight: 800; padding: 14px 32px;
  border: none; border-radius: var(--r); cursor: pointer; display: none;
}
#btn-zip:hover { opacity: .88; }
.done-note { font-size: 11px; color: var(--muted); max-width: 340px; line-height: 1.6; }
</style>
</head>
<body>

<div id="topbar">
  <span id="app-title">UGC Organizer</span>
  <span id="mode-badge">MOVE MODE</span>
  <div id="progress-wrap"><div id="progress-fill"></div></div>
  <span id="topbar-counter">— / —</span>
  <span id="topbar-stats"></span>
</div>

<div id="layout">
  <div id="img-pane">
    <img id="preview" src="" alt="">
    <div id="video-placeholder">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <polygon points="5 3 19 12 5 21 5 3"/>
      </svg>
      <span>Video file — enter a name manually</span>
    </div>
    <div id="scanline"></div>
  </div>

  <div id="side">
    <div class="s-section">
      <div class="s-label">Current File</div>
      <div id="fname-tag">—</div>
    </div>

    <div class="s-section">
      <div class="s-label">Claude Suggestion</div>
      <div id="suggest-box">
        <div id="suggest-status">—</div>
        <div id="suggest-text">—</div>
      </div>
    </div>

    <div class="s-section">
      <div class="s-label">File Name</div>
      <input id="name-input" type="text" placeholder="descriptive-name-here" autocomplete="off" spellcheck="false">
      <div class="hint"><kbd>Enter</kbd> to confirm &nbsp;·&nbsp; <kbd>S</kbd> to skip</div>
    </div>

    <div class="s-section" style="flex:1">
      <div class="s-label">Category &nbsp;<span style="font-weight:400;text-transform:none;letter-spacing:0">— keys 1–9</span></div>
      <div id="cat-grid">
        __CAT_BUTTONS__
      </div>
    </div>

    <div class="s-section">
      <div id="actions">
        <button id="btn-skip"    onclick="skipFile()">Skip →</button>
        <button id="btn-confirm" onclick="submitFile()">Move File →</button>
      </div>
    </div>
  </div>
</div>

<div id="done-screen">
  <div id="done-glyph">⟨∅⟩</div>
  <h2>Inbox Cleared</h2>
  <p id="done-stats"></p>
  <button id="btn-zip" onclick="downloadZip()">⬇ Download ZIP</button>
  <p class="done-note" id="done-note">Drop more files into _inbox and refresh to organize another batch.</p>
</div>

<script>
const CATS = __CATS_JS__;
let selectedCat = null;
let exportMode  = 'move';

// ── Init ─────────────────────────────────────────────────────────

async function init() {
  const s = await (await fetch('/api/status')).json();
  exportMode = s.export_mode;
  const badge = document.getElementById('mode-badge');
  if (exportMode === 'zip') {
    badge.textContent = 'ZIP MODE';
    badge.classList.add('zip-mode');
    document.getElementById('btn-confirm').textContent = 'Queue File →';
  }
  loadCurrent();
}

// ── Load current ─────────────────────────────────────────────────

async function loadCurrent() {
  const res  = await fetch('/api/current');
  const data = await res.json();
  if (data.done) { showDone(data.stats, data.export_mode); return; }

  updateProgress(data.index, data.total);
  updateStats(data.stats);
  document.getElementById('fname-tag').textContent    = data.filename;
  document.getElementById('name-input').value         = '';
  resetCat();
  setReady(false);

  if (data.is_video) {
    showVideo();
    setSuggestion('Video file — type a name below', false, false);
  } else {
    loadImage();
  }
}

// ── Image ─────────────────────────────────────────────────────────

function loadImage() {
  const img = document.getElementById('preview');
  const vid = document.getElementById('video-placeholder');
  vid.style.display = 'none';
  img.style.display = 'none';
  setSuggestion('Analyzing…', true, false);

  img.onload = async () => {
    img.style.display = 'block';
    triggerScan();
    const res  = await fetch('/api/analyze', { method: 'POST' });
    const data = await res.json();
    const s    = data.suggestion || '';
    if (s && s !== 'unnamed-image') {
      setSuggestion(s, false, true);
      document.getElementById('name-input').value = s;
      checkReady();
    } else if (data.error) {
      setSuggestion('No suggestion — type a name below', false, false);
      document.getElementById('name-input').focus();
    } else {
      setSuggestion('No API key — type a name below', false, false);
      document.getElementById('name-input').focus();
    }
  };

  img.src = '/api/image?' + Date.now();
}

function showVideo() {
  document.getElementById('preview').style.display          = 'none';
  document.getElementById('video-placeholder').style.display = 'flex';
}

function triggerScan() {
  const sl = document.getElementById('scanline');
  sl.classList.remove('active');
  void sl.offsetWidth;
  sl.classList.add('active');
}

function setSuggestion(text, loading, success) {
  const status = document.getElementById('suggest-status');
  const disp   = document.getElementById('suggest-text');
  if (loading) {
    status.innerHTML    = '<span class="pulse"></span> Analyzing…';
    disp.style.color    = 'var(--muted)';
  } else if (success) {
    status.innerHTML    = '<span style="color:var(--teal)">✓</span> Suggestion ready';
    disp.style.color    = 'var(--teal)';
  } else {
    status.innerHTML    = '<span style="color:var(--muted)">—</span>';
    disp.style.color    = 'var(--muted)';
  }
  disp.textContent = text;
}

// ── Categories ───────────────────────────────────────────────────

function selectCat(num) {
  if (selectedCat) document.getElementById('cat-' + selectedCat)?.classList.remove('active');
  selectedCat = num;
  document.getElementById('cat-' + num)?.classList.add('active');
  checkReady();
}

function resetCat() {
  if (selectedCat) document.getElementById('cat-' + selectedCat)?.classList.remove('active');
  selectedCat = null;
}

// ── Move / Skip ──────────────────────────────────────────────────

function checkReady() {
  const name = document.getElementById('name-input').value.trim();
  setReady(!!(name && selectedCat));
}

function setReady(r) {
  document.getElementById('btn-confirm').classList.toggle('ready', r);
}

async function submitFile() {
  const name = document.getElementById('name-input').value.trim();
  if (!name || !selectedCat) return;
  const res  = await fetch('/api/move', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ name, category: selectedCat }),
  });
  const data = await res.json();
  if (data.success) loadCurrent();
  else alert('Error: ' + (data.error || 'unknown'));
}

async function skipFile() {
  await fetch('/api/skip', { method: 'POST' });
  loadCurrent();
}

// ── Done ─────────────────────────────────────────────────────────

function showDone(s, mode) {
  document.getElementById('layout').style.display      = 'none';
  document.getElementById('topbar').style.display      = 'none';
  const d = document.getElementById('done-screen');
  d.style.display = 'flex';
  document.getElementById('done-stats').innerHTML =
    '<span class="pill">✓ ' + s.moved   + ' organized</span>' +
    '<span class="pill">→ ' + s.skipped + ' skipped</span>'   +
    '<span class="pill">✕ ' + s.errors  + ' errors</span>';
  if ((mode || exportMode) === 'zip' && s.moved > 0) {
    document.getElementById('btn-zip').style.display = 'block';
    document.getElementById('done-note').textContent =
      'Click Download ZIP to get all organized files, then extract into your folders.';
  }
}

async function downloadZip() {
  const btn = document.getElementById('btn-zip');
  btn.textContent = 'Building ZIP…';
  btn.disabled    = true;
  window.location.href = '/api/export-zip';
  setTimeout(() => {
    btn.textContent = '⬇ Download ZIP';
    btn.disabled    = false;
  }, 3000);
}

// ── Progress ─────────────────────────────────────────────────────

function updateProgress(idx, total) {
  const pct = total > 0 ? (idx / total * 100).toFixed(1) : 0;
  document.getElementById('progress-fill').style.width  = pct + '%';
  document.getElementById('topbar-counter').textContent = (idx + 1) + ' / ' + total;
}

function updateStats(s) {
  document.getElementById('topbar-stats').innerHTML =
    '✓ ' + s.moved + '  →  ' + s.skipped + '  ✕  ' + s.errors;
}

// ── Keyboard ─────────────────────────────────────────────────────

document.addEventListener('keydown', e => {
  if (document.activeElement.tagName === 'INPUT') {
    if (e.key === 'Enter') submitFile();
    return;
  }
  if (e.key === 's' || e.key === 'S') { skipFile(); return; }
  if (e.key === 'Enter') { submitFile(); return; }
  const n = parseInt(e.key);
  if (!isNaN(n) && n >= 1 && n <= 9) selectCat(String(n));
});

document.getElementById('name-input').addEventListener('input', checkReady);

// ── Boot ─────────────────────────────────────────────────────────
init();
</script>
</body>
</html>"""

# ── Launch ──────────────────────────────────────────────────────

def open_browser():
    import time
    time.sleep(1.2)
    webbrowser.open("http://127.0.0.1:5174")

def main():
    print("\n" + "═" * 55)
    print("  UGC AI Image Organizer — Desktop Edition")
    print(f"  Export mode : {EXPORT_MODE.upper()}")
    print("═" * 55)

    # Validate API key
    if not ANTHROPIC_API_KEY or "YOUR-KEY" in ANTHROPIC_API_KEY:
        print("\n  ⚠  No API key set — AI naming will be disabled.")
        print("     Edit ANTHROPIC_API_KEY at the top of this file.")
        print("     Get a free key at console.anthropic.com\n")

    # Validate path
    if not ugc_root.exists():
        print(f"\n  ✕  Folder not found: {ugc_root}")
        print("     Edit WATCH_PATH at the top of this file.\n")
        input("Press Enter to exit...")
        return

    load_files()

    if not files:
        print(f"\n  Inbox is empty.")
        print(f"  Drop files into: {inbox}\n")
        input("Press Enter to exit...")
        return

    print(f"\n  ✓  {len(files)} file(s) ready in inbox")
    print(f"  ✓  Opening browser at http://127.0.0.1:5174")
    print(f"  ✗  Press Ctrl+C to stop\n")

    threading.Thread(target=open_browser, daemon=True).start()

    try:
        app.run(host="127.0.0.1", port=5174, debug=False, use_reloader=False)
    except OSError:
        print("\n  Port 5174 is in use. Close the previous window and try again.\n")
        input("Press Enter to exit...")

if __name__ == "__main__":
    main()
