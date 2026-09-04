# Spec: Add Expense

## Overview
This feature implements the `GET /expenses/add` and `POST /expenses/add` routes, letting a
logged-in user record a new expense against their account. It replaces the current stub route
in `app.py` with a real form page and a database write, and is the first write-path feature
for the `expenses` table (which so far has only been read from, in the Step 5 profile route).

## Depends on
- Step 1 (Database Setup) — `expenses` table and `get_db()` already exist
- Step 3 (Login/Logout) — requires an active `session["user_id"]`
- Step 5 (Profile Backend Route) — profile page is where the user will land after adding an
  expense, and shares the `CATEGORIES` list defined in `database/db.py`

## Routes
- `GET /expenses/add` — render the empty add-expense form — logged-in only (redirect to `/login` if no session)
- `POST /expenses/add` — validate form input, insert the expense, redirect to `/profile` — logged-in only

## Database changes
No new tables or columns. The `expenses` table (`database/db.py`) already has all required
columns (`user_id`, `amount`, `category`, `date`, `description`, `created_at`).

Add one new helper to `database/db.py`:
- `create_expense(user_id, amount, category, expense_date, description)` — parameterized
  `INSERT` into `expenses`, returns the new row's id. Mirrors the existing `create_user()`
  pattern (open connection, execute, commit, close).

## Templates
- **Create:** `templates/add_expense.html` — extends `base.html`; form with amount, category
  (`<select>` populated from `CATEGORIES`), date (defaults to today), description, and a
  submit button. Reuses `.form-group` / `.form-input` / `.btn-submit` classes from
  `style.css` where they fit; page-specific layout (card container, page heading) goes in a
  new stylesheet.
- **Modify:** none

## Files to change
- `app.py` — implement `add_expense()` for both `GET` and `POST`, add `CATEGORIES` import,
  add login-required redirect matching the pattern already used in `profile()`
- `database/db.py` — add `create_expense()` helper

## Files to create
- `templates/add_expense.html`
- `static/css/expenses.css` — page-specific styles for the add-expense form, linked via a
  `{% block head %}` `<link>` tag in `add_expense.html` (same pattern `profile.html` uses for `profile.css`)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only (`?` placeholders)
- Passwords hashed with werkzeug (n/a to this feature, but keep existing auth code untouched)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic stays in `database/db.py` — nothing inline in `app.py`
- Validate on the server: amount must be a positive number, category must be one of
  `CATEGORIES`, date and description follow the same conventions as the seeded data
- On validation failure, re-render `add_expense.html` with an `error` message (same pattern as
  `register()` / `login()`) — never a bare string return
- Redirect unauthenticated users to `/login`, matching `profile()`

## Definition of done
- [ ] Visiting `/expenses/add` while logged out redirects to `/login`
- [ ] Visiting `/expenses/add` while logged in renders a form with amount, category, date, and description fields
- [ ] Submitting the form with valid data inserts a row into `expenses` and redirects to `/profile`
- [ ] The new expense appears in the profile page's recent transactions and category breakdown
- [ ] Submitting with a missing/invalid amount (blank, negative, non-numeric) re-renders the form with an error and does not insert a row
- [ ] Submitting with a category not in `CATEGORIES` re-renders the form with an error and does not insert a row
- [ ] The form's category `<select>` options match `CATEGORIES` in `database/db.py`
- [ ] No hardcoded hex colors in `expenses.css` — all colors reference `:root` variables from `style.css`
