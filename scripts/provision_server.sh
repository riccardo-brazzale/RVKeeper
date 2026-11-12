#!/usr/bin/env bash
set -Eeuo pipefail
umask 027

readonly MANAGED_MARKER="# Managed by RVKeeper provision_server.sh"
readonly SERVICE_NAME="rvkeeper"
readonly APP_USER="rvkeeper"
readonly APP_GROUP="www-data"
readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly ENV_FILE="$ROOT_DIR/.env"
readonly VENV_DIR="$ROOT_DIR/.venv"
readonly UNIT_FILE="/etc/systemd/system/rvkeeper.service"
readonly NGINX_AVAILABLE="/etc/nginx/sites-available/rvkeeper"
readonly NGINX_ENABLED="/etc/nginx/sites-enabled/rvkeeper"

if [[ "$(id -u)" -ne 0 ]]; then
    echo "Esegui lo script come root: sudo $0" >&2
    exit 1
fi

if [[ ! -f "$ROOT_DIR/manage.py" || ! -f "$ROOT_DIR/requirements.txt" ]]; then
    echo "Esegui lo script dalla copia Git del progetto RVKeeper." >&2
    exit 1
fi

if [[ ! -r /etc/os-release ]]; then
    echo "Impossibile identificare la distribuzione Linux." >&2
    exit 1
fi
# shellcheck disable=SC1091
source /etc/os-release
if [[ "${ID:-}" != "ubuntu" && "${ID:-}" != "debian" && " ${ID_LIKE:-} " != *" debian "* ]]; then
    echo "Questa versione dello script supporta Debian e Ubuntu." >&2
    exit 1
fi

read_env_value() {
    local key="$1"
    if [[ ! -f "$ENV_FILE" ]]; then
        return 0
    fi
    python3 - "$ENV_FILE" "$key" <<'PY'
import sys

try:
    from dotenv import dotenv_values
    values = dotenv_values(sys.argv[1])
except ModuleNotFoundError:
    # Before the venv exists, parse the simple KEY=VALUE format used by this installer.
    values = {}
    with open(sys.argv[1], encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("\"'")
value = values.get(sys.argv[2], "") or ""
sys.stdout.write(str(value))
PY
}

ensure_packages() {
    local packages=(build-essential certbot libpq-dev nginx postgresql python3-dev python3-venv)
    local missing=()
    local package
    for package in "${packages[@]}"; do
        if ! dpkg-query -W -f='${Status}' "$package" 2>/dev/null | grep -qx 'install ok installed'; then
            missing+=("$package")
        fi
    done
    if ((${#missing[@]})); then
        apt-get update
        DEBIAN_FRONTEND=noninteractive apt-get install -y "${missing[@]}"
    else
        echo "Dipendenze di sistema già installate."
    fi
}

ensure_packages

if ! getent group "$APP_GROUP" >/dev/null; then
    echo "Il gruppo $APP_GROUP non esiste dopo l'installazione di Nginx." >&2
    exit 1
fi
if ! getent group "$APP_USER" >/dev/null; then
    groupadd --system "$APP_USER"
fi
if ! id "$APP_USER" >/dev/null 2>&1; then
    useradd --system --gid "$APP_USER" --home-dir /nonexistent --shell /usr/sbin/nologin "$APP_USER"
fi

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/python" -m pip install --disable-pip-version-check -r "$ROOT_DIR/requirements.txt"

manage() {
    DJANGO_SETTINGS_MODULE=config.production_settings \
        "$VENV_DIR/bin/python" "$ROOT_DIR/manage.py" "$@"
}

SERVER_NAME="${RVKEEPER_SERVER_NAME:-$(read_env_value RVKEEPER_SERVER_NAME)}"
if [[ -z "$SERVER_NAME" ]]; then
    configured_hosts="$(read_env_value DJANGO_ALLOWED_HOSTS)"
    IFS=',' read -r -a host_candidates <<< "$configured_hosts"
    for candidate in "${host_candidates[@]}"; do
        candidate="$(xargs <<< "$candidate")"
        if [[ -n "$candidate" && "$candidate" != "localhost" && "$candidate" != "127.0.0.1" ]]; then
            SERVER_NAME="$candidate"
            break
        fi
    done
fi
if [[ -z "$SERVER_NAME" ]]; then
    read -r -p "Hostname pubblico o IPv4 del server (es. rvkeeper.example.com): " SERVER_NAME
fi
if [[ ! "$SERVER_NAME" =~ ^[A-Za-z0-9][A-Za-z0-9.-]*$ ]]; then
    echo "Hostname non valido: usare un nome DNS o un indirizzo IPv4, senza schema o percorso." >&2
    exit 1
fi

FRESH_ENV=0
if [[ ! -f "$ENV_FILE" ]]; then
    FRESH_ENV=1
fi
AUTO_TLS_EMAIL="${RVKEEPER_LETSENCRYPT_EMAIL:-}"
if [[ "$FRESH_ENV" == "1" && -z "$AUTO_TLS_EMAIL" && ! "$SERVER_NAME" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]]; then
    read -r -p "Email per il certificato HTTPS Let's Encrypt (invio per saltare): " AUTO_TLS_EMAIL
fi

if [[ -f "$ENV_FILE" ]]; then
    configured_hosts="$(read_env_value DJANGO_ALLOWED_HOSTS)"
    host_is_allowed=0
    IFS=',' read -r -a allowed_hosts <<< "$configured_hosts"
    for allowed_host in "${allowed_hosts[@]}"; do
        allowed_host="$(xargs <<< "$allowed_host")"
        if [[ "$allowed_host" == "$SERVER_NAME" || "$allowed_host" == "*" ]]; then
            host_is_allowed=1
            break
        fi
    done
    if [[ "$host_is_allowed" != "1" ]]; then
        echo "Aggiungere $SERVER_NAME a DJANGO_ALLOWED_HOSTS nel .env prima del provisioning." >&2
        exit 1
    fi
fi

if [[ ! -f "$ENV_FILE" ]]; then
    DJANGO_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(64))')"
    DB_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(40))')"
    cat > "$ENV_FILE" <<EOF
DJANGO_SECRET_KEY=$DJANGO_SECRET_KEY
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=$SERVER_NAME,127.0.0.1,localhost
DJANGO_CSRF_TRUSTED_ORIGINS=http://$SERVER_NAME
DJANGO_SECURE_COOKIES=false
DJANGO_SECURE_SSL_REDIRECT=false
RVKEEPER_SERVER_NAME=$SERVER_NAME
RVKEEPER_TLS_CERTIFICATE=
RVKEEPER_TLS_KEY=

DB_NAME=rvkeeper
DB_USER=rvkeeper_user
DB_PASSWORD=$DB_PASSWORD
DB_HOST=127.0.0.1
DB_PORT=5432

EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
EMAIL_HOST=
EMAIL_PORT=587
EMAIL_USE_TLS=false
EMAIL_USE_SSL=false
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
DEFAULT_FROM_EMAIL=noreply@$SERVER_NAME

RVKEEPER_WORKSHOP_NAME=RVKeeper Demo Workshop
RVKEEPER_WORKSHOP_SLUG=rvkeeper-demo
EOF
    chmod 640 "$ENV_FILE"
    chown "root:$APP_USER" "$ENV_FILE"
    echo "Creato $ENV_FILE con segreti casuali. Conservane una copia sicura fuori da Git."
else
    echo "Configurazione .env esistente: mantenuta senza sovrascriverla."
    chown "root:$APP_USER" "$ENV_FILE"
    chmod 640 "$ENV_FILE"
fi

TLS_CERTIFICATE="$(read_env_value RVKEEPER_TLS_CERTIFICATE)"
TLS_KEY="$(read_env_value RVKEEPER_TLS_KEY)"
if [[ -n "$TLS_CERTIFICATE" || -n "$TLS_KEY" ]]; then
    if [[ -z "$TLS_CERTIFICATE" || -z "$TLS_KEY" || ! -r "$TLS_CERTIFICATE" || ! -r "$TLS_KEY" ]]; then
        echo "Configurazione TLS incompleta: verificare RVKEEPER_TLS_CERTIFICATE e RVKEEPER_TLS_KEY nel .env." >&2
        exit 1
    fi
    if [[ "$(read_env_value DJANGO_SECURE_COOKIES | tr '[:upper:]' '[:lower:]')" != "true" || "$(read_env_value DJANGO_SECURE_SSL_REDIRECT | tr '[:upper:]' '[:lower:]')" != "true" ]]; then
        echo "Con TLS attivo impostare DJANGO_SECURE_COOKIES=true e DJANGO_SECURE_SSL_REDIRECT=true nel .env." >&2
        exit 1
    fi
    csrf_origins=",$(read_env_value DJANGO_CSRF_TRUSTED_ORIGINS | tr -d '[:space:]'),"
    if [[ "$csrf_origins" != *",https://$SERVER_NAME,"* ]]; then
        echo "Con TLS aggiungere https://$SERVER_NAME a DJANGO_CSRF_TRUSTED_ORIGINS nel .env." >&2
        exit 1
    fi
fi

if [[ "$FRESH_ENV" == "0" && -z "$AUTO_TLS_EMAIL" && -x "$VENV_DIR/bin/gunicorn" ]] \
    && systemctl is-active --quiet "$SERVICE_NAME" \
    && systemctl is-active --quiet nginx \
    && systemctl is-enabled --quiet "$SERVICE_NAME" \
    && systemctl is-enabled --quiet nginx; then
    if manage check_install_state >/dev/null 2>&1 \
        && manage migrate --check --noinput >/dev/null 2>&1 \
        && nginx -t >/dev/null 2>&1; then
        HTTP_STATUS="$(SERVER_NAME="$SERVER_NAME" TLS_CERTIFICATE="$TLS_CERTIFICATE" python3 - <<'PY'
import http.client
import os
import ssl

try:
    if os.environ["TLS_CERTIFICATE"]:
        connection = http.client.HTTPSConnection(
            "127.0.0.1", 443, timeout=3, context=ssl._create_unverified_context()
        )
    else:
        connection = http.client.HTTPConnection("127.0.0.1", 80, timeout=3)
    connection.request("GET", "/", headers={"Host": os.environ["SERVER_NAME"]})
    print(connection.getresponse().status)
except OSError:
    print("000")
PY
)"
        case "$HTTP_STATUS" in
            200|301|302|307|308)
                echo "RVKeeper è già configurato e risponde correttamente: nessuna modifica necessaria."
                exit 0
                ;;
        esac
    fi
fi

# Gunicorn reads the source and venv through its private group; Nginx cannot read .env.
find "$ROOT_DIR" \
    -path "$ROOT_DIR/.git" -prune -o \
    -path "$VENV_DIR" -prune -o \
    -path "$ROOT_DIR/media" -prune -o \
    -path "$ROOT_DIR/staticfiles" -prune -o \
    -type d -exec chgrp "$APP_USER" {} + -exec chmod g+rx {} +
while IFS= read -r -d '' tracked_file; do
    chgrp "$APP_USER" "$ROOT_DIR/$tracked_file"
    chmod g+r "$ROOT_DIR/$tracked_file"
done < <(git -C "$ROOT_DIR" ls-files -z)
chgrp -R "$APP_USER" "$VENV_DIR"
chmod -R g+rX "$VENV_DIR"
chgrp "$APP_USER" "$ROOT_DIR"
chmod 755 "$ROOT_DIR"

DB_CONFIG_FILE="$(mktemp /tmp/rvkeeper-db-config.XXXXXX)"
PG_SQL_FILE="$(mktemp /tmp/rvkeeper-pg-bootstrap.XXXXXX)"
cleanup() {
    rm -f "$DB_CONFIG_FILE" "$PG_SQL_FILE"
}
trap cleanup EXIT

"$VENV_DIR/bin/python" - "$ENV_FILE" "$DB_CONFIG_FILE" <<'PY'
import sys
from dotenv import dotenv_values

values = dotenv_values(sys.argv[1])
keys = ("DB_NAME", "DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT")
missing = [key for key in keys if not values.get(key)]
if missing:
    raise SystemExit("Variabili DB mancanti nel .env: " + ", ".join(missing))
with open(sys.argv[2], "w", encoding="utf-8") as output:
    for key in keys:
        output.write(str(values[key]) + "\0")
PY
mapfile -d '' -t DB_CONFIG < "$DB_CONFIG_FILE"
DB_NAME="${DB_CONFIG[0]}"
DB_USER="${DB_CONFIG[1]}"
DB_PASSWORD="${DB_CONFIG[2]}"
DB_HOST="${DB_CONFIG[3]}"
DB_PORT="${DB_CONFIG[4]}"
if [[ "$DB_HOST" != "127.0.0.1" && "$DB_HOST" != "localhost" ]]; then
    echo "Il provisioning crea PostgreSQL locale; DB_HOST nel .env deve essere localhost o 127.0.0.1." >&2
    exit 1
fi
if [[ ! "$DB_PORT" =~ ^[0-9]+$ ]]; then
    echo "DB_PORT nel .env deve essere un numero." >&2
    exit 1
fi

systemctl enable --now postgresql

"$VENV_DIR/bin/python" - "$ENV_FILE" "$PG_SQL_FILE" <<'PY'
import sys
from dotenv import dotenv_values

values = dotenv_values(sys.argv[1])
keys = ("DB_NAME", "DB_USER", "DB_PASSWORD")
config = {key: values[key] for key in keys}
if any("\x00" in value for value in config.values()):
    raise SystemExit("I valori DB nel .env non possono contenere byte NUL.")

def sql_literal(value):
    return "'" + value.replace("'", "''") + "'"

db_user = sql_literal(config["DB_USER"])
db_password = sql_literal(config["DB_PASSWORD"])
db_name = sql_literal(config["DB_NAME"])
script = f"""\
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', {db_user}, {db_password})
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = {db_user})
\\gexec
SELECT format('CREATE DATABASE %I OWNER %I', {db_name}, {db_user})
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = {db_name})
\\gexec
"""
with open(sys.argv[2], "w", encoding="utf-8") as output:
    output.write(script)
PY
chmod 600 "$PG_SQL_FILE"
chown postgres:postgres "$PG_SQL_FILE"
sudo -u postgres psql -X -v ON_ERROR_STOP=1 -p "$DB_PORT" -d postgres -f "$PG_SQL_FILE"

cd "$ROOT_DIR"
manage check_install_state
manage migrate --noinput
manage collectstatic --noinput
chgrp -R "$APP_GROUP" "$ROOT_DIR/staticfiles"
chmod -R g+rX "$ROOT_DIR/staticfiles"
chmod 755 "$ROOT_DIR/staticfiles"

if ! manage shell -c 'from django.contrib.auth import get_user_model; import sys; sys.exit(0 if get_user_model().objects.filter(is_superuser=True, is_active=True).exists() else 1)' --verbosity 0 >/dev/null 2>&1; then
    echo "Crea il superuser iniziale. Le password non vengono salvate nei log."
    manage createsuperuser
fi
manage bootstrap_site

install -d -o "$APP_USER" -g "$APP_GROUP" -m 2770 "$ROOT_DIR/media"
chgrp -R "$APP_GROUP" "$ROOT_DIR/media"
chmod -R g+rX "$ROOT_DIR/media"
find "$ROOT_DIR/media" -type d -exec chmod g+w {} +
install -d -o root -g "$APP_GROUP" -m 0755 "$ROOT_DIR/staticfiles"

TLS_CERTIFICATE="$(read_env_value RVKEEPER_TLS_CERTIFICATE)"
TLS_KEY="$(read_env_value RVKEEPER_TLS_KEY)"

write_managed_file() {
    local source="$1"
    local target="$2"
    if [[ -f "$target" ]] && cmp -s "$source" "$target"; then
        echo "Configurazione già corretta: $target"
        return
    fi
    if [[ -e "$target" ]] && ! grep -Fq "$MANAGED_MARKER" "$target"; then
        echo "Il file esiste ma non è gestito da RVKeeper: $target. Non lo sovrascrivo." >&2
        exit 1
    fi
    install -o root -g root -m 0644 "$source" "$target"
    echo "Configurato $target"
    MANAGED_CHANGED=1
}

MANAGED_CHANGED=0
UNIT_TEMP="$(mktemp)"
cat > "$UNIT_TEMP" <<EOF
$MANAGED_MARKER
[Unit]
Description=RVKeeper Django application
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=$APP_USER
Group=$APP_GROUP
SupplementaryGroups=$APP_USER
WorkingDirectory=$ROOT_DIR
EnvironmentFile=$ENV_FILE
Environment=DJANGO_SETTINGS_MODULE=config.production_settings
RuntimeDirectory=rvkeeper
RuntimeDirectoryMode=0750
UMask=0007
ExecStart=$VENV_DIR/bin/gunicorn --workers 2 --access-logfile - --error-logfile - --bind unix:/run/rvkeeper/gunicorn.sock config.wsgi:application
ExecReload=/bin/kill -s HUP \$MAINPID
Restart=on-failure
RestartSec=5
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF
write_managed_file "$UNIT_TEMP" "$UNIT_FILE"
rm -f "$UNIT_TEMP"

NGINX_TEMP="$(mktemp)"
if [[ -n "$TLS_CERTIFICATE" ]]; then
    cat > "$NGINX_TEMP" <<EOF
$MANAGED_MARKER
server {
    listen 80;
    server_name $SERVER_NAME;
    location /.well-known/acme-challenge/ { root /var/www/rvkeeper-acme; }
    location / { return 301 https://\$host\$request_uri; }
}

server {
    listen 443 ssl http2;
    server_name $SERVER_NAME;
    ssl_certificate $TLS_CERTIFICATE;
    ssl_certificate_key $TLS_KEY;
    ssl_protocols TLSv1.2 TLSv1.3;
    client_max_body_size 30m;
    location /static/ { alias $ROOT_DIR/staticfiles/; }
    location /media/ { alias $ROOT_DIR/media/; }
    location / {
        proxy_pass http://unix:/run/rvkeeper/gunicorn.sock;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_redirect off;
    }
}
EOF
else
    cat > "$NGINX_TEMP" <<EOF
$MANAGED_MARKER
server {
    listen 80;
    server_name $SERVER_NAME;
    client_max_body_size 30m;
    location /.well-known/acme-challenge/ { root /var/www/rvkeeper-acme; }
    location /static/ { alias $ROOT_DIR/staticfiles/; }
    location /media/ { alias $ROOT_DIR/media/; }
    location / {
        proxy_pass http://unix:/run/rvkeeper/gunicorn.sock;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_redirect off;
    }
}
EOF
fi
write_managed_file "$NGINX_TEMP" "$NGINX_AVAILABLE"
rm -f "$NGINX_TEMP"
install -d -o root -g root -m 0755 /var/www/rvkeeper-acme/.well-known/acme-challenge

if [[ -L "$NGINX_ENABLED" ]]; then
    if [[ "$(readlink -f "$NGINX_ENABLED")" != "$NGINX_AVAILABLE" ]]; then
        echo "Il collegamento $NGINX_ENABLED punta a un'altra configurazione; non lo modifico." >&2
        exit 1
    fi
elif [[ -e "$NGINX_ENABLED" ]]; then
    echo "$NGINX_ENABLED esiste e non è un collegamento gestito; non lo modifico." >&2
    exit 1
else
    ln -s "$NGINX_AVAILABLE" "$NGINX_ENABLED"
    MANAGED_CHANGED=1
fi

nginx -t
if ! systemctl is-enabled --quiet nginx; then
    systemctl enable nginx
fi
if ! systemctl is-active --quiet nginx; then
    systemctl start nginx
elif [[ "$MANAGED_CHANGED" == "1" ]]; then
    systemctl reload nginx
fi

if [[ "$MANAGED_CHANGED" == "1" ]]; then
    systemctl daemon-reload
fi
if ! systemctl is-enabled --quiet "$SERVICE_NAME"; then
    systemctl enable "$SERVICE_NAME"
fi
if ! systemctl is-active --quiet "$SERVICE_NAME"; then
    systemctl start "$SERVICE_NAME"
elif [[ "$MANAGED_CHANGED" == "1" ]]; then
    systemctl restart "$SERVICE_NAME"
fi

if [[ -n "$AUTO_TLS_EMAIL" && -z "$TLS_CERTIFICATE" && "${RVKEEPER_TLS_BOOTSTRAPPED:-0}" != "1" ]]; then
    certbot certonly --non-interactive --agree-tos --no-eff-email \
        --email "$AUTO_TLS_EMAIL" --webroot -w /var/www/rvkeeper-acme -d "$SERVER_NAME"
    python3 - "$ENV_FILE" "$SERVER_NAME" <<'PY'
import os
import sys
import tempfile

env_path, hostname = sys.argv[1:]
updates = {
    "DJANGO_CSRF_TRUSTED_ORIGINS": f"https://{hostname}",
    "DJANGO_SECURE_COOKIES": "true",
    "DJANGO_SECURE_SSL_REDIRECT": "true",
    "RVKEEPER_TLS_CERTIFICATE": f"/etc/letsencrypt/live/{hostname}/fullchain.pem",
    "RVKEEPER_TLS_KEY": f"/etc/letsencrypt/live/{hostname}/privkey.pem",
}
lines = []
seen = set()
with open(env_path, encoding="utf-8") as source:
    for line in source:
        key, separator, _ = line.partition("=")
        if separator and key in updates:
            lines.append(f"{key}={updates[key]}\n")
            seen.add(key)
        else:
            lines.append(line)
for key, value in updates.items():
    if key not in seen:
        lines.append(f"{key}={value}\n")
fd, temp_path = tempfile.mkstemp(prefix=".rvkeeper-env-", dir=os.path.dirname(env_path))
with os.fdopen(fd, "w", encoding="utf-8") as target:
    target.writelines(lines)
os.chmod(temp_path, 0o640)
os.replace(temp_path, env_path)
PY
    chown "root:$APP_USER" "$ENV_FILE"
    export RVKEEPER_TLS_BOOTSTRAPPED=1
    exec "$ROOT_DIR/scripts/provision_server.sh"
fi

echo "RVKeeper è configurato. Host: $SERVER_NAME"
if [[ -n "$TLS_CERTIFICATE" ]]; then
    echo "Admin: /admin/ — URL: https://$SERVER_NAME/"
else
    echo "Admin: /admin/ — URL iniziale: http://$SERVER_NAME/"
    echo "HTTPS non configurato. Segui Documentazione/Deployment Linux RVKeeper.md per Let's Encrypt."
fi
