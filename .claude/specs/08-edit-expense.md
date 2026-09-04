# Spec: Edit Expense

## Overview
This feature implements the `GET /expenses/<id>/edit` and `POST /expenses/<id>/edit` routes,
letting a logged-in user modify an expense they previously recorded. It replaces the current
stub route in `app.py` with a real form pre-filled with the expense's existing values, and is
the first update-path feature for the `expenses` table. It reuses the same form layout and
validation rules established in Step 7 (Add Expense), applied to an existing row instead of a
new one.

## Depends on
- Step 1 (Database Setup) — `expenses` table and `get_db()` already exist
- Step 3 (Login/Logout) — requires an active `session["user_id"]`
- Step 5 (Profile Backend Route) — profile page is where the user will land after editing an
  expense, and is where edit links will originate from
- Step 7 (Add Expense) — `create_expense()` pattern, `add_expense.html` form layout, and
  `expenses.css` styles are all reused/mirrored here

## Routes
- `GET /expenses/<int:id>/edit` — render the edit form pre-filled with the expense's current
  values — logged-in only (redirect to `/login` if no session); `404` via `abort(404)` if the
  expense does not exist or does not belong to the logged-in user
- `POST /expenses/<int:id>/edit` — validate form input, update the expense, redirect to
  `/profile` — logged-in only; same ownership/`404` check as `GET`

## Database changes
No new tables or columns. The `expenses` table (`database/db.py`) already has all required
columns (`user_id`, `amount`, `category`, `date`, `description`, `created_at`).

Add two new helpers to `database/db.py`:
- `get_expense_by_id(expense_id)` — parameterized `SELECT * FROM expenses WHERE id = ?`,
  returns the row (or `None`). Mirrors `get_user_by_email()`.
- `update_expense(expense_id, amount, category, expense_date, description)` — parameterized
  `UPDATE expenses SET amount = ?, category = ?, date = ?, description = ? WHERE id = ?`.
  Mirrors the existing `create_expense()` pattern (open connection, execute, commit, close).

Ownership checks (`expense["user_id"] == session["user_id"]`) happen in `app.py`, not in the DB
helper — `get_expense_by_id()` stays a plain lookup, same as other `database/db.py` helpers.

## Templates
- **Create:** none
- **Modify:** none required, but `add_expense.html` will be reused as the rendering target for
  the edit form (see "Files to change" below) — if a separate `edit_expense.html` is preferred
  for clarity, create it as a near-duplicate of `add_expense.html` with `action` pointed at the
  edit URL and `value="{{ expense.amount }}"` / `selected` / etc. pre-filled from the existing
  row

## Files to change
- `app.py` — implement `edit_expense()` for both `GET` and `POST`, add `get_expense_by_id` and
  `update_expense` imports, add login-required redirect and ownership check matching the
  pattern already used in `add_expense()` / `profile()`
- `database/db.py` — add `get_expense_by_id()` and `update_expense()` helpers
- `templates/profile.html` — add an edit link/button per transaction row, using
  `url_for('edit_expense', id=transaction.id)` (requires passing the expense `id` through in
  the `transactions` list built in `app.py`'s `profile()`)

## Files to create
- `templates/edit_expense.html` — extends `base.html`; same form fields as
  `add_expense.html` (amount, category, date, description) but pre-filled with the expense's
  current values and posting to `url_for('edit_expense', id=expense.id)`; reuses
  `static/css/expenses.css` via the same `{% block head %}` pattern

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
  `CATEGORIES`, date is required — same rules as `add_expense()`
- On validation failure, re-render `edit_expense.html` with an `error` message and the
  submitted (not the stale DB) values, same pattern as `add_expense()`
- Redirect unauthenticated users to `/login`, matching `profile()` and `add_expense()`
- Use `abort(404)` (not a redirect, not a bare string) when the expense id doesn't exist or
  belongs to a different user — never leak another user's expense data

## Definition of done
- [ ] Visiting `/expenses/<id>/edit` while logged out redirects to `/login`
- [ ] Visiting `/expenses/<id>/edit` for an expense that doesn't exist returns a 404
- [ ] Visiting `/expenses/<id>/edit` for another user's expense returns a 404 (not the form)
- [ ] Visiting `/expenses/<id>/edit` for your own expense renders a form pre-filled with its
      current amount, category, date, and description
- [ ] Submitting the form with valid changes updates the row in `expenses` and redirects to
      `/profile`
- [ ] The updated values appear in the profile page's recent transactions and category
      breakdown, and the old values no longer do
- [ ] Submitting with a missing/invalid amount (blank, negative, non-numeric) re-renders the
      form with an error and does not update the row
- [ ] Submitting with a category not in `CATEGORIES` re-renders the form with an error and does
      not update the row
- [ ] The profile page's transaction rows link to `/expenses/<id>/edit` for each expense
- [ ] No hardcoded hex colors introduced — any new styles reference `:root` variables from
      `style.css`
