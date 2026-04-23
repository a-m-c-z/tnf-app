"""
Script to reset the database (WARNING: Deletes all data!)
Usage: python reset_database.py
"""
import os
import database

def reset_database():
    """Delete database and recreate fresh"""
    
    print("\n⚠️  WARNING: This will delete ALL ratings data!")
    confirm = input("Are you sure? Type 'YES' to confirm: ").strip()
    
    if confirm != 'YES':
        print("Reset cancelled.")
        return
    
    # Delete database file if it exists
    if os.path.exists('ratings.db'):
        os.remove('ratings.db')
        print("✓ Deleted old database")
    
    # Recreate database
    database.init_db()
    print("✓ Created fresh database")
    
    # Add players from app.py
    try:
        from app import PLAYERS
        database.add_players_from_list(PLAYERS)
        print(f"✓ Added {len(PLAYERS)} players")
        print("\nDatabase reset complete!")
        print("\n📝 IMPORTANT: To clear browser cookies, visit:")
        print("   http://localhost:5000/clear_cookies")
        print("   (or tell your friends to visit: YOUR_NGROK_URL/clear_cookies)")
    except ImportError:
        print("✓ Database created (run app.py to add players)")
        print("\n📝 IMPORTANT: To clear browser cookies, visit:")
        print("   http://localhost:5000/clear_cookies")

if __name__ == "__main__":
    reset_database()