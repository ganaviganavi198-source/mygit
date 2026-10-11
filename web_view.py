r"""Read-only web page that shows a mygit repository in your browser.

Run it from inside the repository folder you want to view, for example:
    python "C:\Users\DELL\Desktop\Built my Own Git\web_view.py"
Then open http://localhost:8000 in your browser. Press Ctrl+C in the terminal to stop.
"""
import html
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

PORT = 8000
MYGIT = Path(__file__).resolve().parent / "mygit.py"
REPO = Path.cwd()

SECTIONS = [
    ("Status", ["status"]),
    ("Branches", ["branch"]),
    ("History (log)", ["log"]),
    ("Reflog (all moves)", ["reflog", "--all"]),
    ("Tags", ["tag-list"]),
    ("Integrity check", ["fsck"]),
]


def run_mygit(args):
    """Run one mygit command in the repository folder and return its text output."""
    result = subprocess.run(
        [sys.executable, str(MYGIT), *args],
        cwd=REPO, capture_output=True, text=True,
        encoding="utf-8", errors="replace")
    return (result.stdout + result.stderr).strip() or "(no output)"


def build_page():
    if not (REPO / ".mygit").exists():
        body = ("<p>This folder is not a mygit repository. Open PowerShell in a folder "
                "where you ran <code>mygit init</code>, then start the viewer again.</p>")
    else:
        parts = []
        for title, args in SECTIONS:
            output = run_mygit(args)
            parts.append(f"<h2>{html.escape(title)}</h2><pre>{html.escape(output)}</pre>")
        body = "\n".join(parts)
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>mygit viewer</title>
<style>
body {{ font-family: Segoe UI, sans-serif; margin: 2em; background: #fafafa; color: #222; }}
h1 {{ margin-bottom: 0.2em; }}
h2 {{ margin-top: 1.5em; }}
pre {{ background: #1e1e1e; color: #ddd; padding: 1em; border-radius: 6px; overflow-x: auto; }}
</style></head>
<body>
<h1>mygit repository viewer</h1>
<p>Repository: <code>{html.escape(str(REPO))}</code> (read-only view)</p>
{body}
</body></html>"""


class Viewer(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ("/", "/index.html"):
            self.send_error(404, "Page not found")
            return
        page = build_page().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(page)))
        self.end_headers()
        self.wfile.write(page)

    def log_message(self, format, *args):
        pass  # keep the terminal quiet


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", PORT), Viewer)
    print(f"Viewing repository: {REPO}")
    print(f"Open http://localhost:{PORT} in your browser. Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopped.")