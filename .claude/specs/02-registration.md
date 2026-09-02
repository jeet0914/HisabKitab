# Spec: Registration

## Overview
Wires up real account creation for Spendly. `GET /register` currently just
renders a static form (`register.html`) with no backend behind it. This step
adds the `POST /register` handler that validates input, hashes the password,
inserts a new row into `users`, starts a session, and redirects the new user
into the app. It builds directly on the `users` table and `get_db()` helper
from Step 1, and is the foundation the future Login/Logout step will reuse
(shared session pattern, shared `users` table).

## Depends on
- Step 1 — Database Setup (`.claude/specs/01-database-setup.md`): requires
  `get_db()`, `init_db()`, and the `users` table to already exist.

## Routes
- `POST /register` — validate form input, create the user, log them in, and
  redirect to `/profile` — public
- `GET /register` — unchanged, already implemented (renders the form) — public

## Database changes
No schema changes. `users` table (from Step 1) already has the columns
needed: `name`, `email`, `password_hash`.

New functions in `database/db.py` (no inline SQL in `app.py`):
- `get_user_by_email(email)` — returns the matching row or `None`; used to
  check for a duplicate email before insert
- `create_user(name, email, password)` — hashes the password with
  `werkzeug.security.generate_password_hash`, inserts the row, returns the
  new user's `id`

## Templates
- **Create:** none
- **Modify:** `templates/register.html` — no structural changes expected;
  it already posts to `/register` and already renders `{{ error }}` when
  present, so validation failures just re-render it with a message

## Files to change
- `app.py` — add `methods=["GET", "POST"]` to the `/register` route, add
  form validation, call `create_user`, set the session, redirect on success
- `database/db.py` — add `get_user_by_email()` and `create_user()`
- `app.py` — set `app.secret_key` (required for Flask `session` to work;
  not currently set anywhere)

## Files to create
None.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (`generate_password_hash`)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- All DB access goes through `database/db.py` — no inline SQL in `app.py`
- Validate on the server even though the form has `required`/`type=email`
  attributes (client-side HTML validation is not a substitute)
- Reject a duplicate email with a friendly re-rendered error, not a raw
  500 from an unhandled `IntegrityError`
- Do not touch `/login`, `/logout`, or `/profile` beyond redirecting into
  the existing `/profile` stub — those are separate roadmap steps

## Definition of done
- [ ] Submitting the register form with a new name/email/password creates a
      row in `users` with a hashed (not plaintext) password
- [ ] After successful registration, the browser is redirected to `/profile`
      and a session is active (reloading `/profile` doesn't re-prompt login)
- [ ] Submitting with an email that's already registered re-renders
      `register.html` with an error message and does not create a duplicate row
- [ ] Submitting with a missing field (blank name/email/password) re-renders
      `register.html` with an error message and does not hit the database
- [ ] Submitting with a password under 8 characters re-renders the form with
      an error message
- [ ] `GET /register` still renders the empty form with no error, unchanged
- [ ] App starts and runs on port 5001 with no errors
