"""
Reset in_progress queue entries back to waiting status.
This allows the queue to function properly.
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def reset_queue():
    database_url = os.getenv("DATABASE_URL")
    if "postgresql+asyncpg://" in database_url:
        database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    
    print("🔗 Connecting to database...")
    conn = await asyncpg.connect(database_url)
    print("✅ Connected!\n")
    
    print("🔄 Resetting queue status...")
    print("=" * 80)
    
    # Reset all in_progress entries to waiting (except truly completed ones)
    result = await conn.execute("""
        UPDATE queue_status
        SET status = 'waiting',
            called_at = NULL,
            started_at = NULL,
            updated_at = NOW()
        WHERE status = 'in_progress'
        AND created_at >= CURRENT_DATE
        RETURNING id;
    """)
    
    print(f"✅ Reset {result.split()[-1] if result else 0} entries from 'in_progress' to 'waiting'\n")
    
    # Show final queue
    print("🎯 Current Queue Status:")
    print("=" * 80)
    
    queue = await conn.fetch("""
        SELECT q.status, q.priority, p.name as patient_name, a.start_time,
               a.status as appointment_status
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
    if waiting:
        for i, q in enumerate(waiting, 1):
            priority_text = "🚨 URGENT" if q['priority'] > 0 else "Normal"
            time_str = q['start_time'].strftime('%H:%M') if q['start_time'] else 'N/A'
            print(f"  {i}. {q['patient_name']:<30} | {time_str} | {priority_text}")
    else:
        print("  (None)")
    
    print(f"\n🩺 IN PROGRESS ({len(in_progress)}):")
    if in_progress:
        for q in in_progress:
            time_str = q['start_time'].strftime('%H:%M') if q['start_time'] else 'N/A'
            print(f"  • {q['patient_name']:<30} | {time_str}")
    else:
        print("  (None)")
    
    print(f"\n✅ COMPLETED ({len(completed)}):")
    if completed:
        for q in completed:
            time_str = q['start_time'].strftime('%H:%M') if q['start_time'] else 'N/A'
            print(f"  • {q['patient_name']:<30} | {time_str}")
    else:
        print("  (None)")
    
    await conn.close()
    
    print("\n" + "=" * 80)
    print("✅ Queue reset complete!")
    print("=" * 80)
    print("\n🚀 Refresh https://prontivus-frontend-ten.vercel.app/app/atendimento")
    print(f"   You should now see {len(waiting)} patients in the waiting queue!")

if __name__ == "__main__":
    print("=" * 80)
    print("  Reset Queue to Waiting Status")
    print("=" * 80)
    print()
    
    asyncio.run(reset_queue())

