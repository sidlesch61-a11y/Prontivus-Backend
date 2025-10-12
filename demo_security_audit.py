"""
Security System Demo - Shows what the audit tool would display
Run this to see security recommendations without database connection
"""

from datetime import datetime

print("\n" + "="*60)
print("PRONTIVUS MEDICAL SYSTEM")
print("Security Configuration & Audit Tool (DEMO)")
print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*60)

print("\n" + "="*60)
print("SECURITY AUDIT - Checking User Compliance")
print("="*60 + "\n")

# Sample data showing typical users
sample_users = [
    {"email": "admin@clinica.com.br", "name": "Admin Principal", "role": "admin", "has_2fa": False},
    {"email": "dr.silva@clinica.com.br", "name": "Dr. João Silva", "role": "doctor", "has_2fa": False},
    {"email": "dr.santos@clinica.com.br", "name": "Dr. Maria Santos", "role": "doctor", "has_2fa": False},
    {"email": "recepcao@clinica.com.br", "name": "Ana Recepção", "role": "secretary", "has_2fa": False},
]

requires_2fa = []
recommends_2fa = []
compliant = []

for user in sample_users:
    if user["role"] in ["admin", "doctor"] and not user["has_2fa"]:
        requires_2fa.append(user)
        print(f"⚠️  {user['role'].upper()} - {user['email']}")
        print(f"    Missing: 2FA (REQUIRED)")
    elif user["role"] == "secretary" and not user["has_2fa"]:
        recommends_2fa.append(user)
        print(f"ℹ️  {user['role'].upper()} - {user['email']}")
        print(f"    Recommended: Enable 2FA")
    else:
        compliant.append(user)
        print(f"✅ {user['role'].upper()} - {user['email']}")

print("\n" + "-"*60)

print("\n" + "="*60)
print("SECURITY RECOMMENDATIONS")
print("="*60 + "\n")

if requires_2fa:
    print("🔴 CRITICAL - 2FA Required (Must Enable):")
    print("-" * 60)
    for user in requires_2fa:
        print(f"  • {user['role'].upper()}: {user['name']} ({user['email']})")
    print()

if recommends_2fa:
    print("🟡 RECOMMENDED - 2FA Suggested:")
    print("-" * 60)
    for user in recommends_2fa:
        print(f"  • {user['role'].upper()}: {user['name']} ({user['email']})")
    print()

print("\n" + "="*60)
print("PERMISSION MATRIX")
print("="*60 + "\n")

categories = {
    "Patients": ["read", "write", "delete"],
    "Appointments": ["read", "write", "manage"],
    "Medical Records": ["read", "write", "lock"],
    "Prescriptions": ["read", "write", "sign"],
    "Billing": ["read", "write", "process"],
    "Users": ["read", "write", "manage_roles"],
    "Settings": ["read", "write"],
}

roles = ["Patient", "Secretary", "Doctor", "Admin", "Superadmin"]

# Permission mappings
role_perms = {
    "Patient": {
        "Patients": {"read": True, "write": False, "delete": False},
        "Appointments": {"read": True, "write": False, "manage": False},
        "Medical Records": {"read": True, "write": False, "lock": False},
        "Prescriptions": {"read": True, "write": False, "sign": False},
        "Billing": {"read": True, "write": False, "process": False},
        "Users": {"read": False, "write": False, "manage_roles": False},
        "Settings": {"read": False, "write": False},
    },
    "Secretary": {
        "Patients": {"read": True, "write": True, "delete": False},
        "Appointments": {"read": True, "write": True, "manage": True},
        "Medical Records": {"read": False, "write": False, "lock": False},
        "Prescriptions": {"read": False, "write": False, "sign": False},
        "Billing": {"read": True, "write": False, "process": False},
        "Users": {"read": False, "write": False, "manage_roles": False},
        "Settings": {"read": False, "write": False},
    },
    "Doctor": {
        "Patients": {"read": True, "write": True, "delete": False},
        "Appointments": {"read": True, "write": True, "manage": True},
        "Medical Records": {"read": True, "write": True, "lock": True},
        "Prescriptions": {"read": True, "write": True, "sign": True},
        "Billing": {"read": True, "write": False, "process": False},
        "Users": {"read": False, "write": False, "manage_roles": False},
        "Settings": {"read": False, "write": False},
    },
    "Admin": {
        "Patients": {"read": True, "write": True, "delete": True},
        "Appointments": {"read": True, "write": True, "manage": True},
        "Medical Records": {"read": True, "write": True, "lock": True},
        "Prescriptions": {"read": True, "write": True, "sign": True},
        "Billing": {"read": True, "write": True, "process": True},
        "Users": {"read": True, "write": True, "manage_roles": True},
        "Settings": {"read": True, "write": True},
    },
    "Superadmin": {
        "Patients": {"read": True, "write": True, "delete": True},
        "Appointments": {"read": True, "write": True, "manage": True},
        "Medical Records": {"read": True, "write": True, "lock": True},
        "Prescriptions": {"read": True, "write": True, "sign": True},
        "Billing": {"read": True, "write": True, "process": True},
        "Users": {"read": True, "write": True, "manage_roles": True},
        "Settings": {"read": True, "write": True},
    },
}

for category, actions in categories.items():
    print(f"\n{category}:")
    print("-" * 60)
    
    for action in actions:
        print(f"  {action.ljust(20)}", end="")
        
        for role in roles:
            has_perm = role_perms[role][category].get(action, False)
            symbol = "✅" if has_perm else "❌"
            print(f"{symbol}", end="  ")
        
        print()

print("\n" + "="*60)
print("SETUP INSTRUCTIONS")
print("="*60 + "\n")

print("IMMEDIATE ACTIONS (Week 1):")
print("-" * 60)
print("1. Enable 2FA for all Admins and Doctors")
if requires_2fa:
    print("   Affected users:")
    for user in requires_2fa:
        print(f"   • {user['email']}")
print()

print("2. Review and verify all user roles")
print("   • Ensure doctors don't have admin privileges unnecessarily")
print("   • Ensure secretaries don't have medical record access")
print()

print("3. Create backup admin account (if only 1 admin exists)")
admin_count = sum(1 for u in sample_users if u["role"] in ["admin", "superadmin"])
if admin_count < 2:
    print("   ⚠️  WARNING: Only 1 admin account found!")
    print("   → Create a backup admin account immediately")
else:
    print(f"   ✅ {admin_count} admin accounts found")
print()

print("\nRECOMMENDED ACTIONS (Month 1):")
print("-" * 60)
print("4. Enable 2FA for Secretaries (recommended)")
if recommends_2fa:
    print("   Affected users:")
    for user in recommends_2fa:
        print(f"   • {user['email']}")
print()

print("5. Set up audit log review schedule")
print("   • Weekly review of sensitive operations")
print("   • Monthly full audit")
print()

print("6. Train staff on role-specific features")
print("   • Doctors: Ethical locks, digital signatures")
print("   • Secretaries: Appointment management")
print("   • Admins: User management, billing")
print()

print("\nOPTIONAL ACTIONS (Month 2-3):")
print("-" * 60)
print("7. Enable patient portal (gradually)")
print("   • Test with small group first")
print("   • Collect feedback")
print("   • Roll out to all patients")
print()

print("8. Implement quarterly permission reviews")
print("   • Review all user accounts")
print("   • Remove unused accounts")
print("   • Update roles as needed")
print()

print("\n" + "="*60)
print("AUDIT SUMMARY")
print("="*60 + "\n")

total_users = len(sample_users)
compliant_count = len(compliant)
requires_count = len(requires_2fa)
recommends_count = len(recommends_2fa)

print(f"Total Users Checked: {total_users}")
print(f"✅ Compliant: {compliant_count}")
print(f"🔴 Require 2FA: {requires_count}")
print(f"🟡 Recommend 2FA: {recommends_count}")

compliance_rate = (compliant_count / max(total_users, 1)) * 100
print(f"\nCompliance Rate: {compliance_rate:.1f}%")

if compliance_rate == 100:
    print("🎉 All users are compliant with security policies!")
elif compliance_rate >= 80:
    print("🟡 Good security posture. Address remaining items.")
else:
    print("🔴 Security improvements needed. Follow recommendations above.")

print("\n" + "="*60)
print("For detailed documentation, see:")
print("  • SYSTEM_ACCESS_RIGHTS_GUIDE.md")
print("  • ACCESS_RIGHTS_QUICK_REFERENCE.md")
print("  • USER_SETUP_TEMPLATES.md")
print("  • START_HERE_SECURITY.md")
print("  • SECURITY_ROLLOUT_GUIDE.md")
print("="*60 + "\n")

print("📝 NOTE: This is a DEMO version showing sample data.")
print("   To run the full audit with your actual database:")
print("   1. Ensure all Python dependencies are installed")
print("   2. Configure database connection")
print("   3. Run: python setup_security_system.py")
print()

