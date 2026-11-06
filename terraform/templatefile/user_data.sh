#!/bin/bash
set -euo pipefail
umask 077
dnf -y install python3 python3-pip openssl
python3 -m venv /opt/gods-eye-bootstrap
/opt/gods-eye-bootstrap/bin/pip install oci==2.160.3 cryptography==44.0.3
install -d -m 0700 /opt/gods-eye-view /etc/gods-eye-view/bootstrap
/opt/gods-eye-bootstrap/bin/python - <<'PY'
import hashlib, io, pathlib, zipfile, time
import oci
client = oci.object_storage.ObjectStorageClient({}, signer=oci.auth.signers.InstancePrincipalsSecurityTokenSigner())
for attempt in range(360):
    try:
        data = client.get_object('${namespace}', '${bucket}', '${bundle_object}').data.content
        break
    except oci.exceptions.ServiceError as exc:
        if exc.status not in (403, 404): raise
        time.sleep(5)
else:
    raise SystemExit('Immutable VM bundle unavailable after readiness window')
if hashlib.sha256(data).hexdigest() != '${bundle_sha256}':
    raise SystemExit('Immutable VM bundle hash mismatch')
with zipfile.ZipFile(io.BytesIO(data)) as archive:
    for info in archive.infolist():
        p = pathlib.PurePosixPath(info.filename)
        if p.is_absolute() or '..' in p.parts or (info.external_attr >> 16) & 0o170000 == 0o120000:
            raise SystemExit('Unsafe bundle path')
    archive.extractall('/opt/gods-eye-view')
PY
bash /opt/gods-eye-view/docker/bootstrap.sh prepare
cat > /usr/local/sbin/gods-eye-view-bootstrap-public-key <<'SH'
#!/bin/bash
set -euo pipefail
if [[ -f /etc/gods-eye-view/bootstrap/private.pem ]]; then
  cat /etc/gods-eye-view/bootstrap/public.pem
else
  echo GODS_EYE_VIEW_BOOTSTRAP_READY
fi
SH
chmod 0755 /usr/local/sbin/gods-eye-view-bootstrap-public-key
cat > /etc/sudoers.d/gods-eye-view-run-command <<'SUDO'
ocarun ALL=(root) NOPASSWD: /usr/local/sbin/gods-eye-view-bootstrap-public-key, /bin/bash /opt/gods-eye-view/docker/bootstrap.sh prepare, /bin/bash /opt/gods-eye-view/docker/bootstrap.sh start, /opt/gods-eye-bootstrap/bin/python /opt/gods-eye-view/receive.py
SUDO
chmod 0440 /etc/sudoers.d/gods-eye-view-run-command
visudo -cf /etc/sudoers.d/gods-eye-view-run-command
cat > /opt/gods-eye-view/receive.py <<'PY'
import pathlib, sys, time, json
sys.path.insert(0, '/opt/gods-eye-view/scripts/deployment')
import bootstrap_credentials as bootstrap
from image_assets_vm import load_images
import oci
client = oci.object_storage.ObjectStorageClient({}, signer=oci.auth.signers.InstancePrincipalsSecurityTokenSigner())
expected = bootstrap.binding('${deployment_id}', '${operator_user_ocid}', '${operator_fingerprint}')
root = pathlib.Path('/etc/gods-eye-view')
object_name = '.bootstrap/gods-eye-view/${deployment_id}/operator.json'
for attempt in range(360):
    try:
        result = client.get_object('${namespace}', '${bucket}', object_name)
        bootstrap.consume(result.data.content, root, expected, finalize=False)
        load_images(client, '${namespace}', '${bucket}', json.loads((root / 'bootstrap/image-assets.json').read_text()))
        client.delete_object('${namespace}', '${bucket}', object_name, if_match=result.headers['etag'])
        try:
            client.head_object('${namespace}', '${bucket}', object_name)
        except oci.exceptions.ServiceError as missing:
            if missing.status == 404:
                bootstrap.complete(root, expected)
                break
            raise
        raise SystemExit('Bootstrap object still present; refusing readiness')
    except oci.exceptions.ServiceError as exc:
        if exc.status != 404: raise
        time.sleep(5)
else:
    raise SystemExit('Operator delivery timed out')
PY
/opt/gods-eye-bootstrap/bin/python /opt/gods-eye-view/receive.py
bash /opt/gods-eye-view/docker/bootstrap.sh start
