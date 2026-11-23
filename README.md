# Family worship app

The app uses the public-domain Judson 1840 Bible distributed by
[Bible SuperSearch](https://sourceforge.net/projects/biblesuper/files/All%20Bibles%20-%20JSON/MY-Burmese/).
The `my_judson.json` file includes the source metadata and 31,044 verses.
Draws include these verses and any manually added verses.

## Database setup

Back up the deployed app's `bible.json` and `family.json` **before** updating
or restarting it. Streamlit Community Cloud's local filesystem is not durable;
data that has already disappeared cannot be recovered from GitHub automatically.
Put any backup files in the app directory before the first database initialization
if they are to be imported. The checked-in `bible.json` and available `family.json`
are imported once; if `family.json` is absent, the original default members are used.
The import is not repeated on subsequent runs.

Create an Aiven PostgreSQL service on the free plan, then copy its host, port,
database name and username from its Connection information section. The user
needs permission to create tables in its schema and SELECT and INSERT into them.
The service must be reachable from Streamlit Community Cloud. Free services
may stop after inactivity; check Aiven's current plan terms and arrange backups.

Download the service's CA certificate from the Aiven console. The app verifies
both the server certificate and hostname using this CA. Follow the provider's
network access and firewall rules.

In Streamlit Community Cloud, open the app's settings and add the following
in **Secrets**, replacing the placeholder values. Never commit real credentials.
For local use, place the same settings in `.streamlit/secrets.toml` and do not
commit that file.

```toml
[postgresql]
host = "your-database-host"
port = 5432
user = "your-database-user"
password = "your-database-password"
database = "your-database-name"
ca_certificate = """
-----BEGIN CERTIFICATE-----
replace-with-the-full-certificate-from-Aiven
-----END CERTIFICATE-----
"""
```

Deploy `ab.py`, `storage.py`, `requirements.txt`, `my_judson.json`, and
`bible.json` together. After deployment, test saving a member, a custom verse,
and a favorite, then restart the app and confirm that all three remain.
If the database cannot be reached, the app displays an error rather than
pretending data was saved.

Favorites and members are shared by all visitors. This app has no login or
access control, so anyone who can open the app can view and add entries.

## Manual backup and restore

Add a separate, strong, unique admin password of at least 16 characters to
Streamlit Community Cloud's Secrets (outside the `[postgresql]` section):

```toml
[backup]
admin_password = "replace-with-a-long-unique-password"
```

Do not post or commit the real password. In the app, sign in under **Database
Backup & Restore**, prepare a backup, and download the JSON file. Store it
securely outside the app; it contains family names, custom verses, and
favorites. Downloads are manual, not scheduled or encrypted. The static Judson
Bible, database credentials, other database tables, and app code are not
included; retain the repository and configure credentials separately.

To restore, upload a backup created by this feature, check the confirmation
box, and press Restore. Restore merges into existing data, skips exact
duplicates, and writes all entries in one transaction. Invalid files are
rejected before writing. The maximum backup file size is 20 MiB. Keep previous
backup copies and test recovery periodically; this is not a full PostgreSQL
backup and does not replace provider-level backups.

Five failed admin attempts temporarily lock backup login for five minutes in
the current app process. This is not a substitute for provider-level access
controls or rate limiting, and restarting or scaling the app resets that limit.
The rest of the app remains publicly accessible. Sign out after use.
