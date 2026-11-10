# Reminder Scheduler

## Deployment constraint

Run the API with exactly one application worker. The scheduler is an in-process
APScheduler 3.x instance; running multiple Uvicorn workers or multiple API
instances would create multiple pollers. The database row locks reduce races,
but they are not a distributed scheduler or a substitute for one-worker
deployment.

## Existing MySQL database update

Back up the database, then apply `migrations/001_reminder_scheduler_mysql8.sql`
once before starting the updated application:

```sh
mysql --host=localhost --user=YOUR_DB_USER --database=YOUR_DB_NAME < migrations/001_reminder_scheduler_mysql8.sql
```

The migration extends the existing reminder status and reminder-log event
constraints and creates `reminder_occurrences`. It preserves existing reminder
and log rows. `Base.metadata.create_all()` only creates missing tables; it does
not update existing MySQL tables or constraints. Do not rely on it to apply this
migration.

For a fresh development database, the existing development-only
`create_all()` startup hook creates the current metadata. Production databases
must use the SQL migration above.

## Audio files and retries

Generated WAV files are saved under `generated_audio/` using random filenames.
The database stores only a relative path in `reminder_occurrences`; the audio
metadata API returns availability and timestamps, not filesystem paths or file
contents. Back up or retain this directory with the database if generated audio
must persist across deployments.

The poller runs every 15 seconds. Failed TTS attempts are limited to three per
occurrence, with delayed retries. An occurrence is uniquely identified by its
reminder and original scheduled time. A five-minute processing lease allows
recovery after a process exits while handling an occurrence.

## Start the API

From the `backend/` directory, with `DATABASE_URL` and `GNANI_API_KEY` set in
`.env`:

```sh
./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Scheduler state is available at `GET /api/scheduler/status`. Generated audio
means only that the WAV file was created; this implementation does not deliver
or play it on a phone.

## Authentication setup

Set `JWT_SECRET` to a unique random value of at least 32 bytes and configure
`JWT_ACCESS_TOKEN_EXPIRE_MINUTES`. Never commit the secret. New accounts are
registered through `/api/auth/register`; passwords are Argon2 hashes.

The migration adds nullable `users.password_hash` for existing records. Those
accounts receive no default password and cannot log in until a verified operator
issues a short-lived setup token. With the backend environment and
`JWT_SECRET` configured, run from `backend/`:

```sh
./.venv/bin/python scripts/create_password_setup_token.py USER_ID
```

Deliver the printed token to the verified account owner through a trusted
out-of-band channel, then have them POST it with their new password to
`/api/auth/password/setup`. The token expires after 15 minutes and is single-use.

## MySQL authentication/link migration

Back up the database, then apply `migrations/002_auth_family_links_mysql8.sql`
once, separately from migration 001:

```sh
mysql --host=localhost --user=YOUR_DB_USER --database=YOUR_DB_NAME < migrations/002_auth_family_links_mysql8.sql
```

The migration preserves existing users and reminders. Existing users retain a
NULL password hash until the verified setup flow is completed.