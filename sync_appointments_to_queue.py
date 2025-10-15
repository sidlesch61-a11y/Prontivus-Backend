"""
Sync all today's appointments to queue_status table.
Reset queue status based on appointment status.
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def sync_queue():
    database_url = os.getenv("DATABASE_URL")
    if "postgresql+asyncpg://" in database_url:
        database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    
    print("🔗 Connecting to database...")
    conn = await asyncpg.connect(database_url)
    print("✅ Connected!\n")
    
    print("🔄 Syncing appointments to queue...")
    print("=" * 80)
    
    # Get all today's appointments
    appointments = await conn.fetch("""
        SELECT a.id as appointment_id, a.patient_id, a.doctor_id, a.clinic_id, 
               a.start_time, a.status as apt_status, p.name as patient_name
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id
        WHERE a.start_time >= CURRENT_DATE
        AND a.start_time < CURRENT_DATE + INTERVAL '1 day'
        ORDER BY a.start_time;
    """)
    
    print(f"Found {len(appointments)} appointments for today\n")
    
    synced = 0
    updated = 0
    
    for apt in appointments:
        # Check if queue entry exists
        existing = await conn.fetchrow("""
            SELECT id, status FROM queue_status WHERE appointment_id = $1;
        """, apt['appointment_id'])
        
        # Determine queue status from appointment status
        if apt['apt_status'] in ['completed', 'cancelled']:
            queue_status = 'completed'
        elif apt['apt_status'] in ['in_progress', 'checked_in']:
            queue_status = 'in_progress'
        else:  # scheduled, confirmed
            queue_status = 'waiting'
        
        if existing:
            # Update existing queue entry status
            if existing['status'] != queue_status:
                await conn.execute("""
                    UPDATE queue_status 
                    SET status = $1, updated_at = NOW()
                    WHERE id = $2;
                """, queue_status, existing['id'])
                print(f"  ✅ Updated: {apt['patient_name']:<30} | {existing['status']} → {queue_status}")
                updated += 1
            else:
                print(f"  ✓ OK: {apt['patient_name']:<30} | {queue_status}")
        else:
            # Create new queue entry
            await conn.execute("""
                INSERT INTO queue_status (
                    id, appointment_id, patient_id, doctor_id, clinic_id,
                    status, priority, created_at, updated_at
                ) VALUES (
                    gen_random_uuid(), $1, $2, $3, $4, $5, 0, NOW(), NOW()
                );
            """, apt['appointment_id'], apt['patient_id'], apt['doctor_id'], 
            apt['clinic_id'], queue_status)
            print(f"  ✅ Created: {apt['patient_name']:<30} | {queue_status}")
            synced += 1
    
    print(f"\n✅ Sync complete!")
    print(f"  • Created: {synced} new queue entries")
    print(f"  • Updated: {updated} existing entries")
    
    # Show final queue status
    print(f"\n🎯 Final Queue Status:")
    print("=" * 80)
    
    queue = await conn.fetch("""
        SELECT q.status, q.priority, p.name as patient_name, a.start_time
        FROM queue_status q
        JOIN patients p ON q.patient_id = p.id
        JOIN appointments a ON q.appointment_id = a.id
        WHERE q.created_at >= CURRENT_DATE
        ORDER BY 
            CASE q.status 
                WHEN 'waiting' THEN 1 
                WHEN 'in_progress' THEN 2 
                WHEN 'completed' THEN 3 
            END,
            q.priority DESC, 
            a.start_time ASC;
    """)
    
    waiting = [q for q in queue if q['status'] == 'waiting']
    in_progress = [q for q in queue if q['status'] == 'in_progress']
    completed = [q for q in queue if q['status'] == 'completed']
    
    print(f"\n⏳ WAITING ({len(waiting)}):")
    for q in waiting:
        priority_text = "🚨 URGENT" if q['priority'] > 0 else "Normal"
        time_str = q['start_time'].strftime('%H:%M') if q['start_time'] else 'N/A'
        print(f"  • {q['patient_name']:<30} | {time_str} | {priority_text}")
    
    print(f"\n🩺 IN PROGRESS ({len(in_progress)}):")
    for q in in_progress:
        time_str = q['start_time'].strftime('%H:%M') if q['start_time'] else 'N/A'
        print(f"  • {q['patient_name']:<30} | {time_str}")
    
    print(f"\n✅ COMPLETED ({len(completed)}):")
    for q in completed:
        time_str = q['start_time'].strftime('%H:%M') if q['start_time'] else 'N/A'
        print(f"  • {q['patient_name']:<30} | {time_str}")
    
    await conn.close()
    print("\n✅ Done!")

if __name__ == "__main__":
    print("=" * 80)
    print("  Sync Appointments to Queue")
    print("=" * 80)
    print()
    
    asyncio.run(sync_queue())

