"""
HTTP server for the VOD Archiver dashboard.
Serves the dashboard HTML and log files.
"""

import os
import threading
import http.server
import socketserver
import json
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
        
        def translate_path(self, path):
            """Override to intercept API paths before file translation."""
            # Check for API endpoints - don't translate them to file paths
            parsed_path = path.split('?')[0].strip()
            if parsed_path.startswith('/api/'):
                return parsed_path  # Return as-is for API endpoints
            # Default translation for file paths
            return super().translate_path(path)
        
        def do_GET(self):
            """Handle GET requests, including custom endpoints."""
            # Handle custom endpoints (check before file serving)
            parsed_path = self.path.split('?')[0].strip()  # Remove query string and whitespace
            
            # Check for API endpoints first
            if parsed_path == '/api/authenticate':
                self.handle_authenticate()
                return
            elif parsed_path == '/api/status':
                self.handle_status()
                return
            elif parsed_path == '/api/restart':
                self.handle_restart()
                return
            elif parsed_path.startswith('/api/'):
                # Other API endpoints that don't exist
                self.send_response(404)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "API endpoint not found"}).encode())
                return
            
            # Default file serving for non-API paths
            try:
                super().do_GET()
            except Exception as e:
                # If file serving fails, send 404
                self.send_error(404, f"File not found: {e}")
        
        def do_POST(self):
            """Handle POST requests for API endpoints."""
            parsed_path = self.path.split('?')[0].strip()
            if parsed_path == '/api/authenticate':
                self.handle_authenticate()
                return
            elif parsed_path == '/api/status':
                self.handle_status()
                return
            elif parsed_path == '/api/restart':
                self.handle_restart()
                return
            elif parsed_path.startswith('/api/'):
                self.send_response(404)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "API endpoint not found"}).encode())
                return
            
            self.send_error(404, "Not Found")
        
        def handle_authenticate(self):
            """Handle authentication request."""
            import subprocess
            import sys
            from pathlib import Path
            
            try:
                # Run authentication script
                project_root = Path(__file__).parent.parent
                script_path = project_root / "scripts" / "authenticate_youtube.py"
                
                # Run in background so it doesn't block
                subprocess.Popen(
                    [sys.executable, str(script_path)],
                    cwd=str(project_root),
                    creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
                )
                
                response_data = {"status": "success", "message": "Authentication window opened. Please complete the OAuth flow in the browser window."}
            except Exception as e:
                response_data = {"status": "error", "message": str(e)}
            
            # Send JSON response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode('utf-8'))
        
        def handle_status(self):
            """Handle status check request."""
            import subprocess
            import shutil
            from pathlib import Path
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            # Check if Python process is running
            try:
                result = subprocess.run(
                    ["powershell", "-Command", "Get-Process python -ErrorAction SilentlyContinue | Where-Object {$_.Path -like '*BigVods*'} | Measure-Object | Select-Object -ExpandProperty Count"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                is_running = int(result.stdout.strip()) > 0
            except:
                is_running = False
            
            # Check disk space
            try:
                project_root = Path(__file__).parent.parent
                downloads_dir = project_root / "downloads"
                downloads_dir.mkdir(exist_ok=True)
                
                stat = shutil.disk_usage(downloads_dir)
                free_gb = stat.free / (1024 ** 3)
                total_gb = stat.total / (1024 ** 3)
                used_gb = stat.used / (1024 ** 3)
                
                # Check if we have at least 5GB free
                has_space = free_gb >= 5.0
                space_status = "OK" if has_space else "LOW"
            except Exception as e:
                free_gb = 0
                total_gb = 0
                used_gb = 0
                has_space = False
                space_status = "UNKNOWN"
            
            response = {
                "running": is_running,
                "disk_space": {
                    "free_gb": round(free_gb, 2),
                    "total_gb": round(total_gb, 2),
                    "used_gb": round(used_gb, 2),
                    "has_space": has_space,
                    "status": space_status
                }
            }
            self.wfile.write(json.dumps(response).encode())
        
        def handle_restart(self):
            """Handle restart request - restarts the scheduled task."""
            import subprocess
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            try:
                # Stop and restart the scheduled task
                subprocess.run(
                    ["powershell", "-Command", "Stop-ScheduledTask -TaskName 'TwitchVODArchiver' -ErrorAction SilentlyContinue"],
                    timeout=5
                )
                subprocess.run(
                    ["powershell", "-Command", "Start-Sleep -Seconds 2; Start-ScheduledTask -TaskName 'TwitchVODArchiver'"],
                    timeout=10
                )
                response = {"status": "success", "message": "Archiver restarted. It will pick up new credentials on next check."}
            except Exception as e:
                response = {"status": "error", "message": str(e)}
            
            self.wfile.write(json.dumps(response).encode())
        
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
