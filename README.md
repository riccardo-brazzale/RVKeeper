# RVKeeper

RVKeeper is a Django application for camper service workshops. It uses PostgreSQL, Django templates, Gunicorn, and Nginx.

## Production install

The interface defaults to English. Signed-in users can change their saved interface language between English and Italian from **Settings**. After changing translation catalogs, run `python manage.py compilemessages` before starting the application.

The automated installer supports Debian and Ubuntu with systemd. It installs the system dependencies, creates `.venv` and a private `.env`, provisions a local PostgreSQL role/database, applies migrations, asks for the initial Django superuser, creates an initial US demo workshop and dataset, then configures Gunicorn and Nginx.

On a fresh server:

```bash
sudo apt-get update
sudo apt-get install -y git
sudo git clone https://github.com/OWNER/REPOSITORY.git /opt/rvkeeper
cd /opt/rvkeeper
sudo ./scripts/provision_server.sh
```

The installer never drops a database. It preserves an existing `.env`, refuses to overwrite unmanaged systemd/Nginx configuration, and stops if an existing database has pending initial migrations or missing model columns. See [Documentazione/Deployment Linux RVKeeper.md](Documentazione/Deployment%20Linux%20RVKeeper.md) for HTTPS, operations, and recovery details.

For a DNS hostname on a fresh install, the installer offers to request a Let's Encrypt certificate. If skipped, the site starts on HTTP; an IPv4 address cannot use this automatic certificate flow.

Keep `.env`, database dumps, uploaded media, and generated static files out of GitHub. The migration files are required to create the schema and must remain in the repository.
