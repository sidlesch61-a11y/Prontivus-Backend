"""
Security System Setup Script
Applies best practices configuration to Prontivus Medical System
"""

import asyncio
import sys
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.db.session import get_db_session
from app.models import User, Clinic
from app.core.security_config import UserRole, SecurityPolicy, RolePermissions


class SecuritySetup:
    """Setup and configure security system with best practices."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.results = {
            "users_checked": 0,
            "2fa_required": [],
            "2fa_recommended": [],
            "role_issues": [],
            "success": []
        }
    
    async def check_2fa_status(self, user: User) -> bool:
        """Check if user has 2FA enabled."""
        # In production, check TwoFASecret table
        # For now, return False to show what needs to be done
        return False
    
    async def audit_users(self):
        """Audit all users and check security compliance."""
        print("\n" + "="*60)
        print("SECURITY AUDIT - Checking User Compliance")
        print("="*60 + "\n")
        
        result = await self.db.execute(select(User))
        users = result.scalars().all()
        
        for user in users:
            self.results["users_checked"] += 1
            
            # Check 2FA requirement
            requires_2fa = SecurityPolicy.requires_2fa(user.role)
            has_2fa = await self.check_2fa_status(user)
            
            if requires_2fa and not has_2fa:
                self.results["2fa_required"].append({
                    "email": user.email,
                    "name": user.name,
                    "role": user.role
                })
                print(f"⚠️  {user.role.upper()} - {user.email}")
                print(f"    Missing: 2FA (REQUIRED)")
            
            elif user.role.lower() == UserRole.SECRETARY and not has_2fa:
                self.results["2fa_recommended"].append({
                    "email": user.email,
                    "name": user.name,
                    "role": user.role
                })
                print(f"ℹ️  {user.role.upper()} - {user.email}")
                print(f"    Recommended: Enable 2FA")
            
            else:
                print(f"✅ {user.role.upper()} - {user.email}")
                self.results["success"].append(user.email)
        
        print("\n" + "-"*60)
    
    async def display_recommendations(self):
        """Display security recommendations."""
        print("\n" + "="*60)
        print("SECURITY RECOMMENDATIONS")
        print("="*60 + "\n")
        
        if self.results["2fa_required"]:
            print("🔴 CRITICAL - 2FA Required (Must Enable):")
            print("-" * 60)
            for user in self.results["2fa_required"]:
                print(f"  • {user['role'].upper()}: {user['name']} ({user['email']})")
            print()
        
        if self.results["2fa_recommended"]:
            print("🟡 RECOMMENDED - 2FA Suggested:")
            print("-" * 60)
            for user in self.results["2fa_recommended"]:
                print(f"  • {user['role'].upper()}: {user['name']} ({user['email']})")
            print()
        
        if self.results["success"]:
            print(f"✅ {len(self.results['success'])} user(s) compliant")
            print()
    
    async def display_permission_matrix(self):
        """Display permission matrix for all roles."""
        print("\n" + "="*60)
        print("PERMISSION MATRIX")
        print("="*60 + "\n")
        
        roles = [UserRole.PATIENT, UserRole.SECRETARY, UserRole.DOCTOR, 
                UserRole.ADMIN, UserRole.SUPERADMIN]
        
        # Group permissions by category
        categories = {
            "Patients": ["patients.read", "patients.write", "patients.delete"],
            "Appointments": ["appointments.read", "appointments.write", "appointments.manage"],
            "Medical Records": ["medical_records.read", "medical_records.write", "medical_records.lock"],
            "Prescriptions": ["prescriptions.read", "prescriptions.write", "prescriptions.sign"],
            "Billing": ["billing.read", "billing.write", "billing.process"],
            "Users": ["users.read", "users.write", "users.manage_roles"],
            "Settings": ["settings.read", "settings.write"],
        }
        
        for category, permissions in categories.items():
            print(f"\n{category}:")
            print("-" * 60)
            
            for perm in permissions:
                action = perm.split(".")[-1]
                print(f"  {action.ljust(20)}", end="")
                
                for role in roles:
                    has_perm = RolePermissions.has_permission(role.value, perm)
                    symbol = "✅" if has_perm else "❌"
                    print(f"{symbol}", end="  ")
                
                print()
    
    async def generate_setup_instructions(self):
        """Generate step-by-step setup instructions."""
        print("\n" + "="*60)
        print("SETUP INSTRUCTIONS")
        print("="*60 + "\n")
        
        print("IMMEDIATE ACTIONS (Week 1):")
        print("-" * 60)
        print("1. Enable 2FA for all Admins and Doctors")
        if self.results["2fa_required"]:
            print("   Affected users:")
            for user in self.results["2fa_required"]:
                print(f"   • {user['email']}")
        print()
        
        print("2. Review and verify all user roles")
        print("   • Ensure doctors don't have admin privileges unnecessarily")
        print("   • Ensure secretaries don't have medical record access")
        print()
        
        print("3. Create backup admin account (if only 1 admin exists)")
        result = await self.db.execute(
            select(User).where(User.role.in_(["admin", "superadmin"]))
        )
        admins = result.scalars().all()
        if len(admins) < 2:
            print("   ⚠️  WARNING: Only 1 admin account found!")
            print("   → Create a backup admin account immediately")
        else:
            print(f"   ✅ {len(admins)} admin accounts found")
        print()
        
        print("\nRECOMMENDED ACTIONS (Month 1):")
        print("-" * 60)
        print("4. Enable 2FA for Secretaries (recommended)")
        if self.results["2fa_recommended"]:
            print("   Affected users:")
            for user in self.results["2fa_recommended"]:
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
    
    async def display_summary(self):
        """Display summary of audit results."""
        print("\n" + "="*60)
        print("AUDIT SUMMARY")
        print("="*60 + "\n")
        
        print(f"Total Users Checked: {self.results['users_checked']}")
        print(f"✅ Compliant: {len(self.results['success'])}")
        print(f"🔴 Require 2FA: {len(self.results['2fa_required'])}")
        print(f"🟡 Recommend 2FA: {len(self.results['2fa_recommended'])}")
        
        compliance_rate = (len(self.results['success']) / 
                          max(self.results['users_checked'], 1)) * 100
        print(f"\nCompliance Rate: {compliance_rate:.1f}%")
        
        if compliance_rate == 100:
            print("🎉 All users are compliant with security policies!")
        elif compliance_rate >= 80:
            print("🟡 Good security posture. Address remaining items.")
        else:
            print("🔴 Security improvements needed. Follow recommendations above.")


async def main():
    """Run security setup and audit."""
    print("\n" + "="*60)
    print("PRONTIVUS MEDICAL SYSTEM")
    print("Security Configuration & Audit Tool")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # Get database session
    async for db in get_db_session():
        setup = SecuritySetup(db)
        
        # Run audit
        await setup.audit_users()
        
        # Display results
        await setup.display_recommendations()
        await setup.display_permission_matrix()
        await setup.generate_setup_instructions()
        await setup.display_summary()
        
        print("\n" + "="*60)
        print("For detailed documentation, see:")
        print("  • SYSTEM_ACCESS_RIGHTS_GUIDE.md")
        print("  • ACCESS_RIGHTS_QUICK_REFERENCE.md")
        print("  • USER_SETUP_TEMPLATES.md")
        print("="*60 + "\n")
        
        break


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nAudit cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Error running audit: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

