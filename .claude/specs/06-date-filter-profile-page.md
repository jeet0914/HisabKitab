# Spec: Date Filter For Profile Page

## Overview
The `/profile` route currently shows summary stats, the 10 most recent
transactions, and a category breakdown computed across a user's entire
expense history, with no way to narrow the view to a specific time window.
This step adds a date-range filter to the profile page so a user can view
their stats, transactions, and category breakdown for "This Month", "Last
Month", "Last 3 Months", or "All Time". The filter is read from the query
string, applied entirely in the database layer, and re-renders the same
`profile.html` sections with scoped data — no new page, no new route.

## Depends on
- Step 1: Database setup (`expenses` table with `date` column)
- Step 2: Registration (users exist)
- Step 3: Login / Logout (`session["user_id"]` is set)
- Step 4: Profile page static UI (template structure already renders all
  three dynamic sections)
- Step 5: Backend Connection (`database/queries.py` already wires
  `get_summary_stats`, `get_recent_transactions`, `get_category_breakdown`
  to the live database)

## Routes
- `GET /profile?range=<value>` — modifies the existing `GET /profile` route
  — logged-in only. `range` is optional; accepted values are `this_month`,
  `last_month`, `last_3_months`, `all_time`. Defaults to `all_time` when
  absent or invalid (no error, just fall back).

No new routes.

## Database changes
No database changes. The `expenses.date` column (`YYYY-MM-DD` text) already
supports range comparison with parameterized `BETWEEN` / `>=` / `<`
conditions.

## Templates
- **Modify:** `templates/profile.html`
  - Add a date-range filter control (e.g. a `<select>` inside a `<form>`
    that submits via GET, or plain links) above the stat row, with options
    for This Month / Last Month / Last 3 Months / All Time.
  - Selected option must reflect the active `range` value on page load.
  - Stat row, transaction table, and category breakdown must all reflect
    the filtered data with no other structural changes.
  - If no transactions fall in the selected range, show the existing
    "empty" presentation (zeroed stats, empty table/breakdown) — no errors.

## Files to change
- `app.py` — read `range` from `request.args`, validate/default it, pass it
  into the three query calls, and pass the active range back to the
  template for the selected-option state
- `database/queries.py` — add date-bounds parameters to
  `get_summary_stats`, `get_recent_transactions`, and
  `get_category_breakdown` (or add a shared helper that computes
  `(start_date, end_date)` from the `range` key, used by all three)
- `templates/profile.html` — add the filter control
- `static/css/profile.css` — style the new filter control using existing
  CSS variables

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never string-format values into SQL
- Passwords hashed with werkzeug (unaffected by this step, but no
  regressions)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Date-range boundaries are computed in Python (e.g. via `datetime`/
  `date`), never via SQLite date-string manipulation in the query itself
  beyond a simple `BETWEEN ? AND ?` / `>= ? AND < ?` comparison
- An invalid or missing `range` value must silently fall back to
  `all_time` — never raise or 500
- `database/queries.py` functions must stay pure (no Flask imports) and
  continue to open/close their own connection via `get_db()`
- Filtering must not change the definition of "recent" — `get_recent_transactions`
  still returns at most 10 rows, newest-first, now scoped to the range

## Definition of done
- [ ] Visiting `/profile` with no query string shows all-time data, same as
      before this step
- [ ] Visiting `/profile?range=this_month` shows only stats/transactions/
      breakdown for the current calendar month
- [ ] Visiting `/profile?range=last_month` shows only last calendar month's
      data
- [ ] Visiting `/profile?range=last_3_months` shows data from the last 3
      calendar months up to today
- [ ] The filter control on the page reflects whichever range is active in
      the URL
- [ ] Selecting a range from the UI control updates the URL and re-renders
      stats, transaction table, and category breakdown together
- [ ] A range with zero matching expenses shows ₹0.00 total spent, 0
      transactions, and an empty category breakdown — no errors
- [ ] Visiting `/profile?range=garbage` behaves identically to `all_time`
      (no 500, no crash)
- [ ] `/profile` still redirects to `/login` when not authenticated
