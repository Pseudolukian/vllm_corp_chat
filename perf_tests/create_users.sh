#!/usr/bin/env bash
set -euo pipefail

CONTAINER=${CONTAINER:-open-webui}
USERS_FILE=${USERS_FILE:-perf_tests/users.json}
DB_PATH=${DB_PATH:-/app/backend/data/webui.db}

if [[ ! -f "$USERS_FILE" ]]; then
  echo "Users file not found: $USERS_FILE" >&2
  exit 1
fi

echo "Copying users file into container $CONTAINER..."
docker cp "$USERS_FILE" "$CONTAINER:/tmp/users.json"

echo "Inserting users directly into SQLite ($DB_PATH) inside $CONTAINER..."
docker exec -e DB_PATH="$DB_PATH" -i "$CONTAINER" python3 - <<'PY'
import json, sqlite3, time, uuid, bcrypt, os, sys

users_path = '/tmp/users.json'
db_path = os.environ.get('DB_PATH', '/app/backend/data/webui.db')

try:
    users = json.load(open(users_path))
except Exception as e:
    print({'error': f'failed to load users: {e}'})
    sys.exit(1)

conn = sqlite3.connect(db_path)
cur = conn.cursor()
now = int(time.time())
users_inserted = 0
auth_inserted = 0
auth_updated = 0

for u in users:
    username = u.get('username')
    password = u.get('password', '12345678')
    if not username:
        continue
    email = f"{username}@example.com"
    uid = str(uuid.uuid4())
    ts = now

    cur.execute(
        "INSERT OR IGNORE INTO user(id,name,email,role,profile_image_url,created_at,updated_at,last_active_at,username)"
        " VALUES(?,?,?,?,?,?,?,?,?)",
        (uid, username, email, 'user', '', ts, ts, ts, username),
    )
    if cur.rowcount > 0:
        users_inserted += 1

    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    cur.execute(
        "INSERT OR IGNORE INTO auth(id,email,password,active) VALUES(?,?,?,1)",
        (uid, email, pw_hash),
    )
    if cur.rowcount > 0:
        auth_inserted += 1
    else:
        cur.execute("UPDATE auth SET password=?, active=1 WHERE email=?", (pw_hash, email))
        auth_updated += cur.rowcount

conn.commit()
print({'users_inserted': users_inserted, 'auth_inserted': auth_inserted, 'auth_updated': auth_updated})
PY

echo "Done"
