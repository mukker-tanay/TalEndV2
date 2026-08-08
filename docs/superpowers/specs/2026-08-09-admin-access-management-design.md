# Admin Access Management — Password Reset, Disable, Delete

Date: 2026-08-09
Status: Approved for planning

## Context

The admin panel (`FrontEnd/pages/admin.tsx` + `BackEnd/app/api/auth.py`) currently supports
creating users and toggling their role (user/admin). There is no way for an admin to:

- Reset a user's password (e.g. if they're locked out).
- Revoke a user's access without deleting them.
- Permanently remove a user.

An earlier ask included "see passwords" — rejected: passwords are hashed with bcrypt
(`app/utils/auth.py`), a one-way function, so plaintext is never recoverable, and storing/
displaying plaintext would be a serious security regression for a live app with real
recruiter data. Password reset (issue a new temp password) is the safe equivalent and is
what's specified below.

## Data model

Add `disabled: bool` to user documents, default absent/`False`. No migration needed — Mongo
is schemaless; existing docs are read via `.get("disabled", False)`.

## Backend — `BackEnd/app/api/auth.py`

Three new endpoints, all behind the existing `get_current_admin` dependency.

### `POST /auth/admin/users/{email}/reset-password`

- Generates a new temp password via the existing `generate_temp_password()`.
- Updates the target user: `hashed_password` = hash of new temp password, `must_change_password: True`.
- Returns `{"msg": ..., "temp_password": <plaintext>}` — same one-time-disclosure pattern as
  `admin_create_user`.
- Guard: 400 if `email` == the calling admin's own email ("Cannot perform this action on your own account.").

### `PUT /auth/admin/users/{email}/disable`

- Body: `{"disabled": bool}`.
- Sets the `disabled` flag on the target user document.
- Guard: 400 if `email` == calling admin's own email.
- No owner exemption — the owner account can be disabled (reversible via direct DB fix if needed).

### `DELETE /auth/admin/users/{email}`

- Permanently deletes the user document (`users.delete_one({"email": email})`).
- Guards:
  - 400 if `email` == calling admin's own email.
  - 403 if `email` == the protected owner account (`tanaymukker@gmail.com`) — irreversible action,
    so the owner is exempt here even though not exempt from disable.
- 404 if no user matched.

All three follow the existing pattern in the file: plain FastAPI route, `Depends(get_current_admin)`,
direct `users` collection access, no new abstractions.

## Login enforcement — `POST /auth/login`

After password verification succeeds, check `db_user.get("disabled", False)`. If true, return
403 "Account disabled. Contact your administrator." before issuing a token. This check sits
between password verification and token creation in the existing `login()` function.

## Frontend — `FrontEnd/pages/admin.tsx`

- `UserData` type gains `disabled: boolean`; `get_all_users` response and `fetchUsers` include it.
- Each user row gets three more actions alongside the existing Make/Revoke Admin button:
  - **Reset Password** — calls the reset endpoint, then shows the returned temp password once
    in a modal/alert for the admin to copy and relay to the user manually (call, chat, etc.).
    No email-sending involved.
  - **Disable / Enable** — toggle button, same `confirm()` pattern as the existing role-change
    button, calls the disable endpoint with the flipped value.
  - **Delete** — `confirm()` with a stronger warning ("This permanently deletes the user. This
    cannot be undone."), calls the delete endpoint, removes the row on success.
- Row-level guards mirror the backend:
  - The admin's own row: Reset Password, Disable, and Delete are all hidden (self-targeting blocked).
  - The owner row (`tanaymukker@gmail.com`): Delete is hidden (keeps existing "Protected" label
    for that action); Disable and Reset Password remain available.

## Out of scope

- Emailing temp passwords automatically (no SMTP infra currently wired up).
- "See passwords" in any form — not implemented, not planned.
- Bulk actions (disable/delete multiple users at once).
- Audit log of admin actions (who reset/disabled/deleted whom) — not requested, could be a
  future addition if needed.

## Testing

- Manual verification via the admin panel (create a test user, reset its password, log in with
  the new temp password, confirm mandatory change-password redirect still fires via
  `must_change_password`).
- Disable a test user, confirm login is rejected with the 403 message.
- Delete a test user, confirm it disappears from the ledger and Mongo.
- Confirm self-targeting guards (buttons hidden client-side; also verify server-side 400 by
  calling the endpoint directly against your own account).
- Confirm owner account cannot be deleted (403) but can be disabled.
