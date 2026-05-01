#!/usr/bin/env python3
"""
Start a lightweight HTTP server for the experiment UI.

Usage:
    python serve_ui.py

Then open http://localhost:8080 in your browser.
"""
import http.server
import socketserver
import os
from pathlib import Path
from urllib.parse import unquote, urlsplit

PORT = 8080
ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parents[1]
EXPERIMENT_RESULTS_DIR = PROJECT_ROOT / "02_outputs" / "6_experiments" / "current"

class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def translate_path(self, path):
        url_path = unquote(urlsplit(path).path)
        # Keep the browser route stable while serving the organized experiment output directory.
        if url_path.startswith('/experiment_results/'):
            relative = url_path[len('/experiment_results/'):]
            return str(EXPERIMENT_RESULTS_DIR / relative)
        return super().translate_path(path)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

if __name__ == '__main__':
    os.chdir(ROOT)
    with ReusableTCPServer(("", PORT), Handler) as httpd:
        print(f"Serving experiment UI at http://localhost:{PORT}/experiment.html")
        print("Press Ctrl+C to stop")
        httpd.serve_forever()
