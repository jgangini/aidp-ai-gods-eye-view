"""Exercise the deployed proxy configuration with a real Nginx and a local auth stub."""
import http.server
import json
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request


@unittest.skipUnless(shutil.which("nginx"), "Requires the application's Nginx image")
class ViewerProxyTest(unittest.TestCase):
    def test_identity_outage_is_retryable_without_forwarding_unauthorized_requests(self):
        state = {"auth": 503, "forwarded": 0, "upstream": 200}
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass
            def do_GET(self):
                if self.path == "/api/gods-eye-view/session":
                    self.send_response(state["auth"])
                    self.send_header("X-Gods-Eye-View-User", "viewer:reader")
                    self.send_header("X-Gods-Eye-View-Role", "reader")
                else:
                    state["forwarded"] += 1
                    self.send_response(state["upstream"])
                self.end_headers()
                self.wfile.write(b'{"configured":true}')
        backend = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=backend.serve_forever, daemon=True)
        thread.start()
        process = None
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                repository = Path(__file__).resolve().parents[5]
                config = (repository / "docker/gateway.conf.template").read_text()
                with socket.socket() as reservation:
                    reservation.bind(("127.0.0.1", 0))
                    port = reservation.getsockname()[1]
                # Exercise the actual deployed locations; TLS is outside this auth-subrequest check.
                config = config.replace("${PUBLIC_HOST}", "viewer.test")
                config = config.replace("listen 443 ssl;", f"listen 127.0.0.1:{port};")
                config = "\n".join(line for line in config.splitlines() if "ssl_certificate" not in line)
                config = config.replace("/var/log/nginx/access.log", "/dev/null")
                config = config.replace("/etc/nginx/viewer-headers.conf", str(repository / "docker/viewer-headers.conf"))
                for upstream in ("api:8000", "viewer:8081"):
                    config = config.replace(upstream, f"127.0.0.1:{backend.server_port}")
                config = (f"worker_processes 1;\npid {root}/nginx.pid;\nerror_log stderr;\n"
                    f"events {{ worker_connections 64; }}\nhttp {{ client_body_temp_path {root}/body; "
                    f"proxy_temp_path {root}/proxy;\n{config}\n}}\n")
                path = root / "nginx.conf"
                path.write_text(config)
                subprocess.run(["nginx", "-t", "-c", str(path)], check=True, capture_output=True)
                process = subprocess.Popen(["nginx", "-c", str(path), "-g", "daemon off;"], stderr=subprocess.DEVNULL)
                for attempt in range(100):
                    try:
                        with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                            break
                    except OSError:
                        if process.poll() is not None or attempt == 99:
                            self.fail("Nginx failed to start")
                        time.sleep(0.01)
                for auth_status, expected in ((503, 503), (401, 401), (403, 403), (200, 200)):
                    state.update(auth=auth_status, forwarded=0)
                    for route in ("/api/setup/browser", "/api/opensky"):
                        try:
                            response = urllib.request.urlopen(f"http://127.0.0.1:{port}{route}", timeout=2)
                        except urllib.error.HTTPError as error:
                            response = error
                        with response:
                            self.assertEqual(response.status, expected)
                            body = response.read()
                            if expected == 503:
                                self.assertEqual(response.headers["Retry-After"], "2")
                                self.assertEqual(response.headers.get_content_type(), "application/json")
                                self.assertEqual(response.headers["Cache-Control"], "no-store")
                                self.assertEqual(json.loads(body), {"detail": "Viewer access could not be verified"})
                    self.assertEqual(state["forwarded"], 2 if expected == 200 else 0)
                state.update(auth=200)
                for upstream_status in (401, 403, 500, 503):
                    state.update(upstream=upstream_status, forwarded=0)
                    for route in ("/api/setup/browser", "/api/opensky"):
                        with self.assertRaises(urllib.error.HTTPError) as failure:
                            urllib.request.urlopen(f"http://127.0.0.1:{port}{route}", timeout=2)
                        with failure.exception as response:
                            self.assertEqual(response.status, upstream_status)
                            self.assertIsNone(response.headers.get("Retry-After"))
                            self.assertNotIn(b"Viewer access could not be verified", response.read())
                    self.assertEqual(state["forwarded"], 2)
        finally:
            if process is not None:
                process.terminate()
                process.wait(timeout=5)
            backend.shutdown()
            backend.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
