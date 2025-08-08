#!/usr/bin/env python3
"""
Simple HTTP server to view the Readable Runtime site locally.
"""

import http.server
import socketserver
import os
import sys
import webbrowser
from pathlib import Path

# Change to the docs directory
docs_dir = Path(__file__).parent / 'docs'
os.chdir(docs_dir)

# Set up the server
PORT = 8000
Handler = http.server.SimpleHTTPRequestHandler

# Configure MIME types for better compatibility
Handler.extensions_map.update({
    '.js': 'application/javascript',
    '.json': 'application/json',
    '.css': 'text/css',
    '.html': 'text/html',
    '.md': 'text/markdown',
})

print(f"Starting local server...")
print(f"Serving directory: {docs_dir}")
print(f"\nOpen your browser to: http://localhost:{PORT}")
print("\nPress Ctrl+C to stop the server\n")

# Try to open browser automatically
try:
    webbrowser.open(f'http://localhost:{PORT}')
except:
    pass

# Start the server
try:
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        httpd.serve_forever()
except KeyboardInterrupt:
    print("\n\nServer stopped.")
    sys.exit(0)
except OSError as e:
    if e.errno == 48:  # Port already in use
        print(f"\nError: Port {PORT} is already in use.")
        print("Try closing other applications or change the PORT in this script.")
    else:
        print(f"\nError: {e}")
    sys.exit(1)