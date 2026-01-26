"""
HTTP server for the VOD Archiver dashboard.
Serves the dashboard HTML and log files.
"""

import os
import threading
import http.server
import socketserver
from pathlib import Path
import logging

log = logging.getLogger("VODArchiver")


class DashboardServer:
    """HTTP server for the dashboard that serves log files and HTML."""
    
    def __init__(self, port: int = 8000):
        self.port = port
        self.server = None
        self.thread = None
    
    class LogFileHandler(http.server.SimpleHTTPRequestHandler):
        """Custom handler that serves log files with proper MIME type and CORS."""
        
        def end_headers(self):
            # Add CORS headers for local development
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            super().end_headers()
        
        def guess_type(self, path):
            """Override to set correct MIME type for log files."""
            result = super().guess_type(path)
            # Handle different return formats from parent class
            if isinstance(result, tuple):
                mimetype = result[0] if len(result) > 0 else 'application/octet-stream'
                encoding = result[1] if len(result) > 1 else None
            else:
                mimetype = result
                encoding = None
            
            if path.endswith('.log'):
                return ('text/plain', encoding) if encoding else 'text/plain'
            return (mimetype, encoding) if encoding else mimetype
        
        def log_message(self, format, *args):
            """Suppress HTTP server logs to avoid cluttering our log file."""
            pass
    
    def start(self):
        """Start the dashboard server in a background thread."""
        def run_server():
            # Change to project root (one level up from web/)
            project_root = Path(__file__).parent.parent
            os.chdir(project_root)
            with socketserver.TCPServer(("", self.port), self.LogFileHandler) as httpd:
                self.server = httpd
                try:
                    httpd.serve_forever()
                except Exception as e:
                    log.error(f"Dashboard server error: {e}")
        
        self.thread = threading.Thread(target=run_server, daemon=True)
        self.thread.start()
        log.info(f"Dashboard server started at http://localhost:{self.port}/web/dashboard.html")
    
    def stop(self):
        """Stop the dashboard server."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()


def main():
    """Run the dashboard server standalone for testing."""
    import sys
    
    # Set up basic logging for standalone mode
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(message)s'
    )
    
    port = 8000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Invalid port: {sys.argv[1]}. Using default port 8000.")
    
    print("=" * 60)
    print("  VOD Archiver Dashboard Server")
    print("=" * 60)
    print(f"\nStarting server on port {port}...")
    print(f"Dashboard: http://localhost:{port}/web/dashboard.html")
    print("\nPress Ctrl+C to stop")
    print("=" * 60)
    
    server = DashboardServer(port=port)
    
    # Run in foreground for testing (not as daemon thread)
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    with socketserver.TCPServer(("", port), DashboardServer.LogFileHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\nServer stopped.")


if __name__ == "__main__":
    main()
