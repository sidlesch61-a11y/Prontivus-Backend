# 🚨 EMERGENCY DATABASE SCHEMA FIX

## 📊 **ISSUES IDENTIFIED:**

### 1. **Prescriptions Table**
- **Problem:** `record_id` has `NOT NULL` constraint but needs to be optional
- **Error:** `null value in column "record_id" violates not-null constraint`
- **Impact:** Cannot create prescriptions without linking to medical records

### 2. **Appointments Table**
- **Problem:** `status` column is ENUM type but SQLAlchemy model uses VARCHAR
- **Error:** `operator does not exist: appointmentstatus = character varying`
- **Impact:** Cannot create or query appointments

---

## 🔧 **FIX PROCEDURE:**

### **Step 1: Wait for Deployment**

Monitor Render deployment at:
```
https://dashboard.render.com/
```

Look for this message in logs:
```
==> Your service is live 🎉
Available at https://prontivus-backend-wnw2.onrender.com
```

**⏱️ Typical deployment time: 2-3 minutes**

---

### **Step 2: Execute Emergency Fixes**

#### **Option A - Using cURL (Recommended):**

```bash
# Fix 1: Make prescriptions.record_id nullable
curl -X POST "https://prontivus-backend-wnw2.onrender.com/api/v1/emergency/fix-prescription-record-id"

# Wait 2 seconds
sleep 2

# Fix 2: Convert appointments.status to VARCHAR
curl -X POST "https://prontivus-backend-wnw2.onrender.com/api/v1/emergency/fix-appointment-status-enum"
```

#### **Option B - Using Swagger UI:**

1. Go to: https://prontivus-backend-wnw2.onrender.com/docs
2. Scroll to **"emergency"** section
3. Execute these endpoints in order:
   - `POST /api/v1/emergency/fix-prescription-record-id`
   - `POST /api/v1/emergency/fix-appointment-status-enum`

#### **Option C - Using PowerShell:**

```powershell
# Fix 1
Invoke-RestMethod -Method POST -Uri "https://prontivus-backend-wnw2.onrender.com/api/v1/emergency/fix-prescription-record-id"

# Fix 2
Invoke-RestMethod -Method POST -Uri "https://prontivus-backend-wnw2.onrender.com/api/v1/emergency/fix-appointment-status-enum"
```

---

### **Step 3: Verify Success**

Each endpoint should return:
```json
{
  "success": true,
  "message": "✅ Successfully fixed...",
  "next_steps": [...]
}
```

---

### **Step 4: Test Functionality**

#### **Test Prescriptions:**
1. Go to: https://prontivus-frontend-ten.vercel.app/app/prescriptions
2. Click "New Prescription"
3. Fill in medication details
4. Click "Create"
5. **Expected:** ✅ Prescription created successfully

#### **Test Appointments:**
1. Go to: https://prontivus-frontend-ten.vercel.app/app/appointments
2. Click "New Appointment"
3. Fill in appointment details
4. Click "Create"
5. **Expected:** ✅ Appointment created successfully

---

## 🔍 **WHAT THESE FIXES DO:**

### **Fix 1: Prescriptions**
```sql
ALTER TABLE prescriptions 
ALTER COLUMN record_id DROP NOT NULL;
```
- Makes `record_id` optional (nullable)
- Allows prescriptions to exist independently
- Maintains referential integrity when linked

### **Fix 2: Appointments**
```sql
ALTER TABLE appointments 
ALTER COLUMN status TYPE VARCHAR 
USING status::text;

DROP TYPE IF EXISTS appointmentstatus CASCADE;
```
- Converts ENUM to VARCHAR for flexibility
- Removes type mismatch errors
- Preserves all existing data

---

## ⚠️ **IF FIXES FAIL:**

### **Manual PostgreSQL Fix:**

1. Access Render PostgreSQL shell:
   ```bash
   # From Render dashboard, go to database → Connect → External Connection
   ```

2. Execute SQL:
   ```sql
   -- Fix 1
   ALTER TABLE prescriptions ALTER COLUMN record_id DROP NOT NULL;
   
   -- Fix 2
   ALTER TABLE appointments ALTER COLUMN status DROP DEFAULT;
   ALTER TABLE appointments ALTER COLUMN status TYPE VARCHAR USING status::text;
   ALTER TABLE appointments ALTER COLUMN status SET NOT NULL;
   ALTER TABLE appointments ALTER COLUMN status SET DEFAULT 'scheduled';
   DROP TYPE IF EXISTS appointmentstatus CASCADE;
   ```

---

## ✅ **POST-FIX CLEANUP:**

After confirming both fixes work:

1. **Delete emergency endpoint file:**
   ```bash
   rm backend/app/api/v1/emergency_fix.py
   ```

2. **Remove import from main.py:**
   ```python
   # Remove this line:
   from app.api.v1 import emergency_fix
   app.include_router(emergency_fix.router, prefix="/api/v1", tags=["Emergency"])
   ```

3. **Commit and deploy cleanup:**
   ```bash
   git add -A
   git commit -m "chore: remove emergency fix endpoints after successful schema fixes"
   git push
   ```

---

## 📝 **NOTES:**

- These fixes are **permanent** database schema changes
- **Safe to run** - they won't break existing data
- **Idempotent** - running them multiple times won't cause issues
- Fixes apply to **production database** on Render
- No need to run migrations after these fixes

---

## 🆘 **SUPPORT:**

If you encounter any issues:
1. Check Render logs for detailed error messages
2. Verify database connection is healthy
3. Ensure emergency endpoints are deployed and accessible
4. Contact support if manual SQL fix is needed

---

**Last Updated:** 2025-10-11
**Version:** 1.0
**Status:** Ready to Execute

