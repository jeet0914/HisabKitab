# Spec: Login and Logout

## Overview
Wires up real authentication for Spendly. `GET /login` currently renders a
static form (`login.html`) with no backend behind it, and `GET /logout` is a
placeholder that returns a raw string. This step adds the `POST /login`
handler that verifies a submitted email/password against the `users` table,
starts a session on success, and redirects into the app — plus a real
`GET /logout` that clears the session and returns the user to the landing
page. It reuses the `users` table, `get_db()`, and session pattern
established in Steps 1 and 2, and completes the account lifecycle
(register → login → logout) ahead of the profile/expenses work in later steps.

## Depends on
- Step 1 — Database Setup (`.claude/specs/01-database-setup.md`): requires
  `get_db()`, `init_db()`, and the `users` table to already exist.
- Step 2 — Registration (`.claude/specs/02-registration.md`): requires
  `get_user_by_email()`, `app.secret_key`, and the session pattern
  (`session["user_id"]`) already in place.

## Routes
- `POST /login` — validate submitted email/password against the `users`
  table, start a session on success, redirect to `/profile` — public
- `GET /login` — unchanged, already implemented (renders the form) — public
- `GET /logout` — clear the session and redirect to `/` — logged-in

## Database changes
No schema changes and no new functions needed. `get_user_by_email(email)`
(added in Step 2) is sufficient to fetch the row for password verification.

## Templates
- **Create:** none
- **Modify:** `templates/login.html` — replace the hardcoded
  `action="/login"` with `action="{{ url_for('login') }}"` (per CLAUDE.md's
  no-hardcoded-URLs rule); it already renders `{{ error }}` when present, so
  validation failures just re-render it with a message

## Files to change
- `app.py` — add `methods=["GET", "POST"]` to `/login`, add credential
  validation using `check_password_hash`, set the session, redirect on
  success; replace the `/logout` stub with a real handler that pops
  `session["user_id"]` and redirects to `/`
- `templates/login.html` — fix hardcoded form action to use `url_for()`

## Files to create
None.

## New dependencies
No new dependencies (`werkzeug.security.check_password_hash` ships with
Flask's existing werkzeug dependency, same package `generate_password_hash`
already comes from).

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (`check_password_hash` against the stored
  `password_hash`)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- All DB access goes through `database/db.py` — no inline SQL in `app.py`
- Use a single generic error message ("Invalid email or password.") for both
  a nonexistent email and a wrong password — never reveal which one was
  incorrect
- Do not touch `/register` or `/profile` beyond redirecting into the
  existing `/profile` stub — those are separate roadmap steps
- Do not add "remember me" or password-reset functionality — not in scope

## Definition of done
- [ ] Submitting the login form with the seeded demo account
      (`demo@spendly.com` / `demo123`) redirects to `/profile` and starts a
      session
- [ ] Submitting with a correct email but wrong password re-renders
      `login.html` with "Invalid email or password." and does not start a
      session
- [ ] Submitting with an email that doesn't exist re-renders `login.html`
      with the same "Invalid email or password." message
- [ ] Submitting with a missing field (blank email or password) re-renders
      `login.html` with an error message and does not hit the database
- [ ] `GET /login` still renders the empty form with no error, unchanged
- [ ] Visiting `/logout` while logged in clears the session and redirects to
      `/`
- [ ] App starts and runs on port 5001 with no errors
