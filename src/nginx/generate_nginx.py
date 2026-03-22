#!/usr/bin/env python3
import json, glob, os, sys
INSTALL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
vhosts = []
seen = set()
# Build list of directories to scan for plugin manifests
# Must work on host (~/wickerman, ~/WickermanSupport) AND inside container (/app, /support)
scan_dirs = [
    os.path.join(INSTALL_DIR, "plugins"),
]
# Inside container: /support/plugins is the mounted WickermanSupport
if os.path.isdir("/support/plugins"):
    scan_dirs.append("/support/plugins")
# On host: derive from INSTALL_DIR parent (e.g. ~/WickermanSupport)
host_support = os.path.join(os.path.dirname(INSTALL_DIR), "WickermanSupport", "plugins")
if os.path.isdir(host_support):
    scan_dirs.append(host_support)
# Also check HOST_SUPPORT_DIR env var
env_support = os.environ.get("HOST_SUPPORT_DIR", "")
if env_support and os.path.isdir(os.path.join(env_support, "plugins")):
    scan_dirs.append(os.path.join(env_support, "plugins"))
print(f"Nginx generator: scanning {scan_dirs}", file=sys.stderr)
for scan_dir in scan_dirs:
    for path in glob.glob(os.path.join(scan_dir, "*.json")):
        fname = os.path.basename(path)
        if fname in seen: continue
        seen.add(fname)
        try:
            with open(path) as f: m = json.load(f)
            if m.get("nginx_host") and m.get("container_name"):
                port = m.get("ports", [80])[0]
                varname = m["container_name"].replace("-", "_")
                host = m["nginx_host"]
                cname = m["container_name"]
                block = (
                    "\n    server {"
                    "\n        listen 80;"
                    "\n        server_name " + host + ";"
                    "\n        location / {"
                    "\n            set $upstream_" + varname + " http://" + cname + ":" + str(port) + ";"
                    "\n            proxy_pass $upstream_" + varname + ";"
                    "\n            proxy_http_version 1.1;"
                    "\n            proxy_set_header Upgrade $http_upgrade;"
                    '\n            proxy_set_header Connection "upgrade";'
                    "\n            proxy_set_header Host $host;"
                    "\n            proxy_hide_header X-Frame-Options;"
                    "\n            proxy_hide_header Content-Security-Policy;"
                    "\n        }"
                    "\n        error_page 502 503 504 @starting;"
                    "\n        location @starting {"
                    "\n            default_type text/html;"
                    "\n            add_header Cache-Control 'no-cache, no-store, must-revalidate';"
                    "\n            return 200 '<html><body style=background:#11111b;color:#cdd6f4;font-family:sans-serif;text-align:center;padding:60px><h2>Plugin is starting up...</h2><p>Wait a moment and refresh.</p></body></html>';"
                    "\n        }"
                    "\n    }"
                )
                vhosts.append(block)
                print(f"  vhost: {host} -> {cname}:{port}", file=sys.stderr)
        except Exception as e:
            print(f"  ERROR processing {fname}: {e}", file=sys.stderr)
print(f"  Total vhosts: {len(vhosts)}", file=sys.stderr)
conf = """
events { worker_connections 1024; }
http {
    resolver 127.0.0.11 valid=10s;
    server {
        listen 80;
        server_name wickerman.local;
        proxy_connect_timeout 5s;
        proxy_read_timeout 60s;
        location / {
            proxy_pass http://wm-core:8000;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
        }
        error_page 502 503 504 @starting;
        location @starting {
            add_header Cache-Control "no-cache, no-store, must-revalidate";
            return 200 '<html><body style="background:#11111b;color:#cdd6f4;font-family:sans-serif;text-align:center;padding:60px"><h2>Wickerman OS is starting up...</h2><p>Wait a moment and refresh.</p></body></html>';
            add_header Content-Type text/html;
        }
    }
    server {
        listen 80;
        server_name downloader.wickerman.local;
        client_max_body_size 0;
        location / {
            proxy_pass http://wm-downloader:5000;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_read_timeout 3600;
            proxy_hide_header X-Frame-Options;
            proxy_hide_header Content-Security-Policy;
        }
    }
""" + "".join(vhosts) + """
}
"""
with open(os.path.join(INSTALL_DIR, "nginx", "nginx.conf"), "w") as f: f.write(conf)
print("Nginx config written.", file=sys.stderr)
