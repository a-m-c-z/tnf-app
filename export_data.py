"""
Script to export rating data to CSV or view in terminal
Usage: python export_data.py
"""
import sqlite3
import csv
from datetime import datetime

def export_to_csv():
    """Export all ratings to a CSV file"""
    conn = sqlite3.connect('ratings.db')
    c = conn.cursor()
    
    # Get all ratings with player names
    c.execute('''SELECT p.name, 
                        r.defensive_workrate, r.attacking_workrate, r.fitness,
                        r.passing_possession, r.defending_tackles, r.shooting,
                        r.physicality, r.pace, r.goalkeeping, r.timestamp
                 FROM ratings r
                 JOIN players p ON r.player_id = p.id
                 ORDER BY r.timestamp DESC''')
    
    ratings = c.fetchall()
    conn.close()
    
    if not ratings:
        print("No ratings in database yet!")
        return
    
    # Create filename with timestamp
    filename = f"ratings_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Player', 'Def Work', 'Att Work', 'Fitness',
                        'Passing', 'Defending', 'Shooting', 'Physicality', 
                        'Pace', 'Goalkeeping', 'Timestamp'])
        writer.writerows(ratings)
    
    print(f"✓ Exported {len(ratings)} ratings to {filename}")

def view_summary():
    """Display summary statistics in terminal"""
    conn = sqlite3.connect('ratings.db')
    c = conn.cursor()
    
    # Get player count
    c.execute("SELECT COUNT(*) FROM players")
    player_count = c.fetchone()[0]
    
    # Get rating count
    c.execute("SELECT COUNT(*) FROM ratings")
    rating_count = c.fetchone()[0]
    
    # Get average ratings
    c.execute('''SELECT p.name,
                        ROUND(AVG(r.defensive_workrate), 1),
                        ROUND(AVG(r.attacking_workrate), 1),
                        ROUND(AVG(r.fitness), 1),
                        ROUND(AVG(r.passing_possession), 1),
                        ROUND(AVG(r.defending_tackles), 1),
                        ROUND(AVG(r.shooting), 1),
                        ROUND(AVG(r.physicality), 1),
                        ROUND(AVG(r.pace), 1),
                        ROUND(AVG(r.goalkeeping), 1),
                        COUNT(r.id) as num_ratings
                 FROM players p
                 LEFT JOIN ratings r ON p.id = r.player_id
                 GROUP BY p.id
                 ORDER BY num_ratings DESC, p.name''')
    
    averages = c.fetchall()
    conn.close()
    
    print("\n" + "="*80)
    print(f"RATING SUMMARY - {player_count} Players, {rating_count} Total Ratings")
    print("="*80)
    
    if not averages:
        print("No data yet!")
        return
    
    # Print header
    print(f"\n{'Player':<15} {'Ratings':<8} {'DefW':<6} {'AttW':<6} {'Fit':<6} "
          f"{'Pass':<6} {'Def':<6} {'Shot':<6} {'Phys':<6} {'Pace':<6} {'GK':<6}")
    print("-"*85)
    
    # Print each player
    for avg in averages:
        name = avg[0][:14]  # Truncate long names
        ratings = avg[10]
        
        if ratings > 0:
            # Format each stat to be exactly 6 characters wide
            stats = []
            for i in range(1, 10):
                val = avg[i] if avg[i] else '-'
                stats.append(f"{val:<6}")
            print(f"{name:<15} {ratings:<8} {''.join(stats)}")
        else:
            print(f"{name:<15} {ratings:<8} {'No ratings yet'}")
    
    print("\n")

def view_recent_ratings(limit=10):
    """Display most recent ratings"""
    conn = sqlite3.connect('ratings.db')
    c = conn.cursor()
    
    c.execute('''SELECT p.name, r.timestamp
                 FROM ratings r
                 JOIN players p ON r.player_id = p.id
                 ORDER BY r.timestamp DESC
                 LIMIT ?''', (limit,))
    
    recent = c.fetchall()
    conn.close()
    
    if not recent:
        print("No ratings yet!")
        return
    
    print(f"\n{'='*60}")
    print(f"RECENT RATINGS (Last {min(limit, len(recent))})")
    print(f"{'='*60}")
    
    for player, timestamp in recent:
        print(f"{timestamp:<20} Rating submitted for {player}")
    
    print()

def main():
    """Main menu"""
    print("\n⚽ Football Rating Database Tool\n")
    print("1. View summary in terminal")
    print("2. View recent ratings")
    print("3. Export all data to CSV")
    print("4. View detailed player stats")
    print("5. Exit")
    
    choice = input("\nSelect option (1-5): ").strip()
    
    if choice == '1':
        view_summary()
    elif choice == '2':
        num = input("How many recent ratings? (default 10): ").strip()
        limit = int(num) if num.isdigit() else 10
        view_recent_ratings(limit)
    elif choice == '3':
        export_to_csv()
    elif choice == '4':
        view_player_details()
    elif choice == '5':
        print("Goodbye!")
        return
    else:
        print("Invalid option!")
        return
    
    # Ask if they want to do more
    again = input("\nDo something else? (y/n): ").strip().lower()
    if again == 'y':
        main()

def view_player_details():
    """View detailed stats for a specific player"""
    conn = sqlite3.connect('ratings.db')
    c = conn.cursor()
    
    # List all players
    c.execute("SELECT id, name FROM players ORDER BY name")
    players = c.fetchall()
    
    print("\nPlayers:")
    for i, (pid, name) in enumerate(players, 1):
        print(f"{i}. {name}")
    
    choice = input("\nSelect player number: ").strip()
    
    try:
        idx = int(choice) - 1
        player_id, player_name = players[idx]
    except (ValueError, IndexError):
        print("Invalid selection!")
        conn.close()
        return
    
    # Get all ratings for this player
    c.execute('''SELECT defensive_workrate, attacking_workrate,
                        fitness, passing_possession, defending_tackles, 
                        shooting, physicality, pace, goalkeeping, timestamp
                 FROM ratings 
                 WHERE player_id = ?
                 ORDER BY timestamp DESC''', (player_id,))
    
    ratings = c.fetchall()
    conn.close()
    
    if not ratings:
        print(f"\n{player_name} has no ratings yet!")
        return
    
    print(f"\n{'='*80}")
    print(f"DETAILED RATINGS FOR {player_name.upper()} ({len(ratings)} ratings)")
    print(f"{'='*80}\n")
    
    attributes = ['DefW', 'AttW', 'Fit', 'Pass', 'Def', 'Shot', 'Phys', 'Pace', 'GK']
    
    for rating in ratings:
        scores = rating[0:9]
        timestamp = rating[9]
        
        print(f"Submitted: {timestamp}")
        print(f"  {' | '.join([f'{attr}: {score}' for attr, score in zip(attributes, scores)])}")
        print()
    
    # Calculate averages
    averages = [sum(r[i] for r in ratings) / len(ratings) for i in range(0, 9)]
    print(f"AVERAGES:")
    print(f"  {' | '.join([f'{attr}: {avg:.1f}' for attr, avg in zip(attributes, averages)])}")
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExiting...")
    except Exception as e:
        print(f"\nError: {e}")