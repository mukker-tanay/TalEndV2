# Admin Access Management (Reset / Disable / Delete) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give admins three new actions per user in the admin panel: reset password (one-time temp password), disable/enable login, and permanent delete — with self-targeting and owner-account guards.

**Architecture:** Three new FastAPI routes added to the existing `BackEnd/app/api/auth.py` (same file, same `get_current_admin` dependency pattern as `admin_update_role`). Login checks a new `disabled` field on the user document before issuing a token. Frontend adds three buttons per row in `FrontEnd/pages/admin.tsx`, following the existing `handleRoleChange` fetch + `confirm()` pattern.

**Tech Stack:** FastAPI + PyMongo (backend), Next.js/TypeScript + Tailwind (frontend). No new dependencies.

## Global Constraints

- No plaintext passwords are ever stored or displayed except the one-time temp password returned immediately after generation (spec: "Out of scope — see passwords").
- Admin cannot target their own account for reset-password, disable, or delete (400 "Cannot perform this action on your own account.").
- Owner account (`tanaymukker@gmail.com`) cannot be deleted (403 "This account cannot be deleted.") but CAN be disabled and password-reset.
- No new dependencies, no test framework introduction — this codebase has no existing pytest/test infra for `app/api`; verification is manual via `uvicorn --reload` + `curl`/browser, matching how the rest of the app is validated.
- Follow existing code style in `app/api/auth.py` exactly: plain route functions, `Depends(get_current_admin)`, direct `users` collection calls, Pydantic models in `app/models/user.py` for request bodies.

---

## File Structure

- Modify: `BackEnd/app/models/user.py` — add `DisableUpdate` Pydantic model.
- Modify: `BackEnd/app/api/auth.py` — add `disabled` check in `login()`; add three new routes.
- Modify: `FrontEnd/pages/admin.tsx` — add `disabled` to `UserData` type, fetch it, add three action handlers + buttons per row.

---

### Task 1: Disabled flag — login enforcement

**Files:**
- Modify: `BackEnd/app/api/auth.py:45-58` (the `login` function)

**Interfaces:**
- Consumes: existing `db_user` dict from `users.find_one(...)` inside `login()`.
- Produces: nothing new consumed by later tasks — this task only adds a check. Later tasks (2-4) will set the `disabled` field this checks.

- [ ] **Step 1: Add the disabled check to `login()`**

In `BackEnd/app/api/auth.py`, inside `login()`, right after the existing credential check and before `token = create_access_token(...)`:

```python
@router.post("/auth/login")
@limiter.limit("10/minute")
def login(request: Request, user: UserLogin):
    db_user = users.find_one({"email": user.email})
    if not db_user or not verify_password(user.password, db_user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if db_user.get("disabled", False):
        raise HTTPException(status_code=403, detail="Account disabled. Contact your administrator.")

    token = create_access_token({"sub": user.email})
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": db_user.get("role", "user"),
        "require_password_change": db_user.get("must_change_password", False)
    }
```

- [ ] **Step 2: Verify manually**

Start the backend: `cd BackEnd && uvicorn app.main:app --reload`

In a Mongo shell (`docker exec -it jobnoc-mongo8 mongosh -u root -p 'Pass@1108' --authenticationDatabase admin`, then `use cvtool` — adjust db name/creds to match your local `.env`), pick any existing test user's email and run:

```js
db.users.updateOne({email: "test@example.com"}, {$set: {disabled: true}})
```

Then attempt login via curl:

```bash
curl -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" -d '{"email":"test@example.com","password":"<their password>"}'
```

Expected: HTTP 403 with `{"detail":"Account disabled. Contact your administrator."}`.

Revert: `db.users.updateOne({email: "test@example.com"}, {$set: {disabled: false}})`, confirm login succeeds again.

- [ ] **Step 3: Commit**

```bash
git add BackEnd/app/api/auth.py
git commit -m "feature: reject login for disabled users"
```

---

### Task 2: Reset-password endpoint

**Files:**
- Modify: `BackEnd/app/api/auth.py` — add new route after `admin_update_role` (end of file).

**Interfaces:**
- Consumes: `get_current_admin`, `generate_temp_password()`, `hash_password()` — all already defined in this file.
- Produces: `POST /auth/admin/users/{email}/reset-password` → `{"msg": str, "temp_password": str}`, used by Task 5 (frontend).

- [ ] **Step 1: Add the route**

Append to `BackEnd/app/api/auth.py`:

```python
@router.post("/auth/admin/users/{email}/reset-password")
def admin_reset_password(email: str, admin_user = Depends(get_current_admin)):
    if email == admin_user["email"]:
        raise HTTPException(status_code=400, detail="Cannot perform this action on your own account.")

    target_user = users.find_one({"email": email})
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    temp_password = generate_temp_password()
    users.update_one(
        {"email": email},
        {"$set": {
            "hashed_password": hash_password(temp_password),
            "must_change_password": True
        }}
    )
    return {
        "msg": f"Password reset for {email}",
        "temp_password": temp_password
    }
```

- [ ] **Step 2: Verify manually**

With the backend running, log in as an admin to get a bearer token, then:

```bash
curl -X POST http://localhost:8000/auth/admin/users/test@example.com/reset-password \
  -H "Authorization: Bearer <admin token>"
```

Expected: 200 with a `temp_password` in the response. Confirm you can then log in as `test@example.com` with that temp password and that `require_password_change` is `true` in the login response.

Test the self-guard: call the same endpoint with the admin's own email in the URL.
Expected: 400 "Cannot perform this action on your own account."

- [ ] **Step 3: Commit**

```bash
git add BackEnd/app/api/auth.py
git commit -m "feature: admin password reset endpoint"
```

---

### Task 3: Disable/enable endpoint

**Files:**
- Modify: `BackEnd/app/models/user.py` — add `DisableUpdate` model.
- Modify: `BackEnd/app/api/auth.py` — add new route.

**Interfaces:**
- Consumes: `get_current_admin`.
- Produces: `PUT /auth/admin/users/{email}/disable` (body `{"disabled": bool}`) → `{"msg": str}`, used by Task 6 (frontend). `DisableUpdate` model importable from `app.models.user`.

- [ ] **Step 1: Add `DisableUpdate` to `app/models/user.py`**

```python
class DisableUpdate(BaseModel):
    disabled: bool
```

Full file after this change (append at end, after `UserLogin`):

```python
from pydantic import BaseModel, EmailStr
from typing import Optional

class UserCreate(BaseModel):
    name: str                
    email: EmailStr
    password: str

class AdminUserCreate(BaseModel):
    name: str                
    email: EmailStr
    role: Optional[str] = "user"

class PasswordChange(BaseModel):
    old_password: str
    new_password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class DisableUpdate(BaseModel):
    disabled: bool
```

- [ ] **Step 2: Import it and add the route in `app/api/auth.py`**

Update the import line near the top:

```python
from app.models.user import UserCreate, UserLogin, AdminUserCreate, PasswordChange, DisableUpdate
```

Append the route:

```python
@router.put("/auth/admin/users/{email}/disable")
def admin_set_disabled(email: str, update: DisableUpdate, admin_user = Depends(get_current_admin)):
    if email == admin_user["email"]:
        raise HTTPException(status_code=400, detail="Cannot perform this action on your own account.")

    result = users.update_one(
        {"email": email},
        {"$set": {"disabled": update.disabled}}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    return {"msg": f"User {email} {'disabled' if update.disabled else 'enabled'}"}
```

- [ ] **Step 3: Verify manually**

```bash
curl -X PUT http://localhost:8000/auth/admin/users/test@example.com/disable \
  -H "Authorization: Bearer <admin token>" \
  -H "Content-Type: application/json" \
  -d '{"disabled": true}'
```

Expected: 200 `{"msg":"User test@example.com disabled"}`. Confirm login for that user now returns 403 (reuses Task 1's check). Re-enable with `{"disabled": false}` and confirm login works again.

Test self-guard with the admin's own email → expect 400.

- [ ] **Step 4: Commit**

```bash
git add BackEnd/app/models/user.py BackEnd/app/api/auth.py
git commit -m "feature: admin disable/enable user endpoint"
```

---

### Task 4: Delete endpoint

**Files:**
- Modify: `BackEnd/app/api/auth.py` — add new route.

**Interfaces:**
- Consumes: `get_current_admin`.
- Produces: `DELETE /auth/admin/users/{email}` → `{"msg": str}`, used by Task 7 (frontend).

- [ ] **Step 1: Add the route**

Append to `BackEnd/app/api/auth.py`:

```python
OWNER_EMAIL = "tanaymukker@gmail.com"

@router.delete("/auth/admin/users/{email}")
def admin_delete_user(email: str, admin_user = Depends(get_current_admin)):
    if email == admin_user["email"]:
        raise HTTPException(status_code=400, detail="Cannot perform this action on your own account.")

    if email == OWNER_EMAIL:
        raise HTTPException(status_code=403, detail="This account cannot be deleted.")

    result = users.delete_one({"email": email})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    return {"msg": f"User {email} deleted"}
```

- [ ] **Step 2: Verify manually**

```bash
curl -X DELETE http://localhost:8000/auth/admin/users/test@example.com \
  -H "Authorization: Bearer <admin token>"
```

Expected: 200 `{"msg":"User test@example.com deleted"}`. Confirm the user is gone from `db.users.find()` in mongosh.

Test guards:
- Delete with the admin's own email in the URL → expect 400.
- Delete with `tanaymukker@gmail.com` → expect 403 "This account cannot be deleted."
- Delete a nonexistent email → expect 404.

- [ ] **Step 3: Commit**

```bash
git add BackEnd/app/api/auth.py
git commit -m "feature: admin delete user endpoint"
```

---

### Task 5: Frontend — disabled field + Reset Password action

**Files:**
- Modify: `FrontEnd/pages/admin.tsx`

**Interfaces:**
- Consumes: `POST {API_URL}/auth/admin/users/{email}/reset-password` from Task 2.
- Produces: `UserData` type now includes `disabled: boolean` — consumed by Tasks 6-7 for row-level guard logic.

- [ ] **Step 1: Extend the `UserData` type**

In `FrontEnd/pages/admin.tsx`, update:

```typescript
type UserData = {
  name?: string;
  email: string;
  role: string;
  disabled?: boolean;
};
```

(Backend `get_all_users` doesn't return `disabled` yet — that's fixed in Task 6's backend touch-up below, since the field naturally belongs with the disable feature. For now the frontend type just needs to exist.)

- [ ] **Step 2: Add the `handleResetPassword` function**

Add alongside `handleRoleChange`:

```typescript
const handleResetPassword = async (email: string) => {
  if (!confirm(`Reset password for ${email}? This will invalidate their current password.`)) return;

  try {
    const res = await fetch(`${API_URL}/auth/admin/users/${email}/reset-password`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to reset password");

    alert(`New temporary password for ${email}:\n\n${data.temp_password}\n\nCopy this now — it will not be shown again. The user must change it on next login.`);
  } catch (err: any) {
    alert(err.message);
  }
};
```

- [ ] **Step 3: Add the Reset Password button to the table row**

In the Action `<td>` (around line 261-277), add a Reset Password button before the existing role-change button, hidden for the admin's own row. Replace the entire Action `<td>` block with:

```tsx
<td className="p-4 text-right space-x-2 whitespace-nowrap">
  {u.email !== currentUserEmail && (
    <button
      onClick={() => handleResetPassword(u.email)}
      className="text-xs font-bold px-3 py-1.5 rounded-lg border text-amber-600 border-amber-200 hover:bg-amber-50 transition-all"
    >
      Reset Password
    </button>
  )}
  {u.email !== "tanaymukker@gmail.com" && (
    <button
      onClick={() => handleRoleChange(u.email, u.role)}
      className={`text-xs font-bold px-3 py-1.5 rounded-lg border transition-all ${
        u.role === "admin"
          ? "text-red-600 border-red-200 hover:bg-red-50"
          : "text-blue-600 border-blue-200 hover:bg-blue-50"
      }`}
    >
      {u.role === "admin" ? "Revoke Admin" : "Make Admin"}
    </button>
  )}
  {u.email === "tanaymukker@gmail.com" && (
    <span className="text-[10px] text-gray-500 font-bold uppercase tracking-widest">Protected</span>
  )}
</td>
```

This introduces `currentUserEmail` — add it near the existing `token`/`role` reads at the top of the component:

```typescript
const currentUserEmail = typeof window !== "undefined" ? localStorage.getItem("email") : null;
```

Check whether `email` is already stored in `localStorage` at login time (see `FrontEnd/pages/login.tsx` or wherever the login response is handled) — if not, this task must also add `localStorage.setItem("email", data.<email field>)` there, using whatever the login response actually returns (note: current `/auth/login` response in `auth.py` doesn't include the user's email — add `"email": user.email` to that response as part of this step, in `BackEnd/app/api/auth.py`'s `login()` return dict).

- [ ] **Step 4: Verify manually**

Run both servers (`uvicorn app.main:app --reload` in `BackEnd/`, `npm run dev` in `FrontEnd/`). Log in as admin, open Access Management. Click "Reset Password" on a non-self, non-owner row — confirm the alert shows a temp password, and that the target user's next login requires a password change with that new password. Confirm the button is absent on your own row.

- [ ] **Step 5: Commit**

```bash
git add FrontEnd/pages/admin.tsx BackEnd/app/api/auth.py
git commit -m "feature: admin reset password UI"
```

---

### Task 6: Frontend + backend — Disable/Enable action

**Files:**
- Modify: `BackEnd/app/api/auth.py` — include `disabled` in `get_all_users` response.
- Modify: `FrontEnd/pages/admin.tsx`

**Interfaces:**
- Consumes: `PUT {API_URL}/auth/admin/users/{email}/disable` from Task 3; `currentUserEmail` from Task 5.
- Produces: nothing new consumed by later tasks.

- [ ] **Step 1: Include `disabled` in `get_all_users`**

In `BackEnd/app/api/auth.py`, update `get_all_users`:

```python
@router.get("/auth/admin/users")
def get_all_users(admin_user = Depends(get_current_admin)):
    all_users = users.find({})
    result = []
    for u in all_users:
        result.append({
            "name": u.get("name"),
            "email": u.get("email"),
            "role": u.get("role", "user"),
            "disabled": u.get("disabled", False)
        })
    return result
```

- [ ] **Step 2: Add `handleToggleDisabled` in `admin.tsx`**

```typescript
const handleToggleDisabled = async (email: string, currentlyDisabled: boolean) => {
  const action = currentlyDisabled ? "enable" : "disable";
  if (!confirm(`Are you sure you want to ${action} ${email}?`)) return;

  try {
    const res = await fetch(`${API_URL}/auth/admin/users/${email}/disable`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ disabled: !currentlyDisabled }),
    });

    if (!res.ok) {
      const data = await res.json();
      throw new Error(data.detail || `Failed to ${action} user`);
    }

    fetchUsers();
  } catch (err: any) {
    alert(err.message);
  }
};
```

- [ ] **Step 3: Add the Disable/Enable button and a status badge**

In the Role `<td>` (around line 252-260), add a disabled-status badge next to the role badge:

```tsx
<td className="p-4">
  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border ${
    u.role === "admin"
      ? "bg-blue-50 text-blue-700 border-blue-200"
      : "bg-gray-100 text-gray-600 border-gray-200"
  }`}>
    {u.role}
  </span>
  {u.disabled && (
    <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border bg-red-50 text-red-700 border-red-200">
      Disabled
    </span>
  )}
</td>
```

In the Action `<td>` from Task 5, add the toggle button after Reset Password, still guarded by `u.email !== currentUserEmail`:

```tsx
{u.email !== currentUserEmail && (
  <button
    onClick={() => handleToggleDisabled(u.email, !!u.disabled)}
    className={`text-xs font-bold px-3 py-1.5 rounded-lg border transition-all ${
      u.disabled
        ? "text-green-600 border-green-200 hover:bg-green-50"
        : "text-orange-600 border-orange-200 hover:bg-orange-50"
    }`}
  >
    {u.disabled ? "Enable" : "Disable"}
  </button>
)}
```

- [ ] **Step 4: Verify manually**

In the browser, disable a non-self user, confirm the "Disabled" badge appears and the button flips to "Enable". Confirm that user's login now fails with the disabled message. Re-enable and confirm login works again. Confirm the owner row still shows the Disable button (owner is not exempt from disable).

- [ ] **Step 5: Commit**

```bash
git add BackEnd/app/api/auth.py FrontEnd/pages/admin.tsx
git commit -m "feature: admin disable/enable user UI"
```

---

### Task 7: Frontend — Delete action

**Files:**
- Modify: `FrontEnd/pages/admin.tsx`

**Interfaces:**
- Consumes: `DELETE {API_URL}/auth/admin/users/{email}` from Task 4; `currentUserEmail` from Task 5.
- Produces: nothing new consumed by later tasks (final task).

- [ ] **Step 1: Add `handleDeleteUser`**

```typescript
const handleDeleteUser = async (email: string) => {
  if (!confirm(`Permanently delete ${email}? This cannot be undone.`)) return;

  try {
    const res = await fetch(`${API_URL}/auth/admin/users/${email}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!res.ok) {
      const data = await res.json();
      throw new Error(data.detail || "Failed to delete user");
    }

    fetchUsers();
  } catch (err: any) {
    alert(err.message);
  }
};
```

- [ ] **Step 2: Add the Delete button**

In the Action `<td>`, add after the Disable/Enable button, guarded against both self and the owner account:

```tsx
{u.email !== currentUserEmail && u.email !== "tanaymukker@gmail.com" && (
  <button
    onClick={() => handleDeleteUser(u.email)}
    className="text-xs font-bold px-3 py-1.5 rounded-lg border text-red-700 border-red-300 hover:bg-red-50 transition-all"
  >
    Delete
  </button>
)}
```

- [ ] **Step 3: Verify manually**

Create a throwaway test user via "Provision New Account", confirm Delete removes it from the ledger and from `db.users.find()` in mongosh. Confirm the Delete button is absent on both your own row and the owner row (`tanaymukker@gmail.com`), even though Disable/Reset Password remain visible on the owner row.

- [ ] **Step 4: Commit**

```bash
git add FrontEnd/pages/admin.tsx
git commit -m "feature: admin delete user UI"
```

---

## Self-Review Notes

- Spec coverage: reset-password (Tasks 2, 5), disable/enable (Tasks 1, 3, 6), delete (Task 4, 7), self-targeting guard (all backend tasks + `currentUserEmail` checks), owner exemption from delete only (Task 4, 7), login rejection (Task 1) — all covered.
- Task 5 surfaces a real gap: the login response currently has no `email` field, so the frontend can't know "who am I" for the self-targeting UI guard without either decoding the JWT or adding `email` to the login response. Plan fixes this by adding `"email": user.email` to the login response as part of Task 5 — flagged inline rather than left as a TODO.
