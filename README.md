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

Favorites, members, and worship history are shared by everyone who has the
family password. Anyone who can open the app can see the login page, but only
people who know that password can view or change family data.

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
backup and does not replace provider-level backups. Version 2 backups include
worship history and Drive file IDs; the actual audio remains in Google Drive.

Five failed admin attempts temporarily lock backup login for five minutes in
the current app process. This is not a substitute for provider-level access
controls or rate limiting, and restarting or scaling the app resets that limit.
The rest of the app remains publicly accessible. Sign out after use.

## Family history and optional recordings

Set a separate family password in Streamlit Secrets. The entire app, including
history, is behind this shared password. Use a unique password of at least 16
characters and share it only with family:

```toml
[family]
password = "replace-with-a-different-long-unique-password"
```

Each time a family member starts a worship session, the chosen verse, prayer
leader, teacher, and an original discussion outline are stored in PostgreSQL.
History is paginated in the app and included in version 2 manual backups. The
teaching outline is an offline template based on the verse reference, not
copied from devotional publications; review scripture context before teaching.

Recording is optional and user-initiated. For audio uploads to work, configure
a Google OAuth **Web application** client in Google Cloud:

1. Enable the Google Drive API and configure the OAuth consent screen for
   **External** testing. Add the Google account that owns the family's Drive as
   a test user. Select only the `drive.file` scope.
2. Create a **Web application** OAuth client. Add the exact Streamlit app URL
   as an authorized redirect URI, including `https://` and the trailing `/`.
3. Generate an encryption key in a trusted local Python terminal:
   `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
4. Add the following values to Streamlit Cloud's Secrets, using the new OAuth
   client credentials, the exact redirect URI, and the downloaded Aiven CA.
   Never commit these credentials or share them in chat.

```toml
[drive]
client_id = "your-oauth-client-id"
client_secret = "your-oauth-client-secret"
redirect_uri = "https://your-app.streamlit.app/"
token_encryption_key = "generated-fernet-key"
```

The app links Drive only after the family member clicks the connect link and
approves access. The Google account that authorizes Drive owns the private
recordings folder. OAuth refresh tokens are encrypted in PostgreSQL. While the
OAuth app remains in testing mode, Google may expire refresh tokens after
seven days; reconnect Drive when prompted. Public use beyond test users may
require Google verification.

From a history entry, recording starts only when the user explicitly presses
Record, and upload is a separate confirmation. Recordings are stored in Drive,
not the database. Playback is fetched through the app and limited to 200 MiB
per file; browser microphone support, memory, upload size, network, and Drive
quota limit practical duration. The app does not set a duration timer. Store
and back up important audio separately in Drive; JSON backups contain Drive
file IDs, not audio bytes.

The shared family password is not per-person identity. Anyone who knows it
can access all family history and recordings, so protect it and the Google
account that authorized Drive.
