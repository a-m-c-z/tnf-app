import sqlite3
import statistics

def init_db():
    """Initialize the database and create tables if they don't exist"""
    conn = sqlite3.connect('ratings.db')
    c = conn.cursor()
    
    # Players table
    c.execute('''CREATE TABLE IF NOT EXISTS players
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  name TEXT UNIQUE)''')
    
    # Ratings table
    c.execute('''CREATE TABLE IF NOT EXISTS ratings
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  player_id INTEGER,
                  defensive_workrate INTEGER,
                  attacking_workrate INTEGER,
                  fitness INTEGER,
                  passing_possession INTEGER,
                  defending_tackles INTEGER,
                  shooting INTEGER,
                  physicality INTEGER,
                  pace INTEGER,
                  goalkeeping INTEGER,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (player_id) REFERENCES players(id))''')
    
    conn.commit()
    conn.close()

def add_players_from_list(player_names):
    """Add multiple players from a list"""
    conn = sqlite3.connect('ratings.db')
    c = conn.cursor()
    
    for name in player_names:
        try:
            c.execute("INSERT INTO players (name) VALUES (?)", (name,))
        except sqlite3.IntegrityError:
            pass  # Player already exists, skip
    
    conn.commit()
    conn.close()

def get_players():
    """Get all players"""
    conn = sqlite3.connect('ratings.db')
    c = conn.cursor()
    c.execute("SELECT id, name FROM players ORDER BY name")
    players = c.fetchall()
    conn.close()
    return players

def get_player_by_id(player_id):
    """Get a single player by ID"""
    conn = sqlite3.connect('ratings.db')
    c = conn.cursor()
    c.execute("SELECT id, name FROM players WHERE id = ?", (player_id,))
    player = c.fetchone()
    conn.close()
    return player

def add_rating(player_id, ratings):
    """Add a rating for a player"""
    conn = sqlite3.connect('ratings.db')
    c = conn.cursor()
    c.execute('''INSERT INTO ratings 
                 (player_id, defensive_workrate, attacking_workrate,
                  fitness, passing_possession, defending_tackles, shooting,
                  physicality, pace, goalkeeping)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (player_id,
               ratings['defensive_workrate'],
               ratings['attacking_workrate'], 
               ratings['fitness'],
               ratings['passing_possession'], 
               ratings['defending_tackles'],
               ratings['shooting'], 
               ratings['physicality'], 
               ratings['pace'],
               ratings['goalkeeping']))
    conn.commit()
    conn.close()

def get_average_ratings():
    """Get average ratings for all players"""
    conn = sqlite3.connect('ratings.db')
    c = conn.cursor()
    c.execute('''SELECT p.name,
                        ROUND(AVG(r.defensive_workrate), 1) as def_work,
                        ROUND(AVG(r.attacking_workrate), 1) as att_work,
                        ROUND(AVG(r.fitness), 1) as fitness,
                        ROUND(AVG(r.passing_possession), 1) as passing,
                        ROUND(AVG(r.defending_tackles), 1) as defending,
                        ROUND(AVG(r.shooting), 1) as shooting,
                        ROUND(AVG(r.physicality), 1) as physicality,
                        ROUND(AVG(r.pace), 1) as pace,
                        ROUND(AVG(r.goalkeeping), 1) as goalkeeping,
                        COUNT(r.id) as num_ratings
                 FROM players p
                 LEFT JOIN ratings r ON p.id = r.player_id
                 GROUP BY p.id
                 ORDER BY p.name''')
    results = c.fetchall()
    conn.close()
    return results

def filter_outliers_for_player(ratings_data, z_threshold=2.0):
    """
    Filter outlier ratings using Z-score method.
    
    Args:
        ratings_data: List of rating tuples (each has 9 attribute values)
        z_threshold: Z-score threshold (2.0 = outside 95% of normal distribution)
    
    Returns:
        Filtered list excluding outliers
    """
    if len(ratings_data) < 5:  # Don't filter if too few ratings
        return ratings_data
    
    # Calculate overall average for each rating (across all 9 attributes)
    rating_averages = [sum(r) / len(r) for r in ratings_data]
    
    try:
        # Calculate mean and standard deviation
        mean = statistics.mean(rating_averages)
        stdev = statistics.stdev(rating_averages)
        
        if stdev == 0:  # All ratings are identical
            return ratings_data
        
        # Filter out ratings that are more than z_threshold std devs from mean
        filtered_ratings = []
        for i, rating in enumerate(ratings_data):
            z_score = abs(rating_averages[i] - mean) / stdev
            if z_score < z_threshold:  # Keep ratings within threshold
                filtered_ratings.append(rating)
        
        # Only return filtered list if we're keeping at least 75% of ratings
        # This prevents removing too much data
        if len(filtered_ratings) >= len(ratings_data) * 0.75:
            return filtered_ratings
        else:
            return ratings_data
            
    except statistics.StatisticsError:
        # Not enough variance in data
        return ratings_data

def get_average_ratings_filtered(filter_outliers=True):
    """
    Get average ratings for all players with optional outlier filtering.
    
    Args:
        filter_outliers: If True, exclude statistical outliers from averages
    """
    conn = sqlite3.connect('ratings.db')
    c = conn.cursor()
    
    # Get all players
    c.execute("SELECT id, name FROM players ORDER BY name")
    players = c.fetchall()
    
    results = []
    
    for player_id, player_name in players:
        # Get all ratings for this player
        c.execute('''SELECT defensive_workrate, attacking_workrate,
                            fitness, passing_possession, defending_tackles, 
                            shooting, physicality, pace, goalkeeping
                     FROM ratings 
                     WHERE player_id = ?''', (player_id,))
        ratings = c.fetchall()
        
        if not ratings:
            # No ratings for this player
            results.append((player_name, None, None, None, None, None, None, None, None, None, 0))
            continue
        
        if filter_outliers and len(ratings) >= 5:
            # Filter outliers for players with at least 5 ratings
            ratings = filter_outliers_for_player(ratings)
        
        # Calculate averages from the (possibly filtered) ratings
        num_ratings = len(ratings)
        averages = [
            round(sum(r[i] for r in ratings) / num_ratings, 1)
            for i in range(9)
        ]
        results.append((player_name, *averages, num_ratings))
    
    conn.close()
    return results

def get_player_ratings(player_id):
    """Get all individual ratings for a specific player"""
    conn = sqlite3.connect('ratings.db')
    c = conn.cursor()
    c.execute('''SELECT rater_name, defensive_workrate, attacking_workrate,
                        fitness, passing_possession, defending_tackles, 
                        shooting, physicality, pace, goalkeeping, timestamp
                 FROM ratings 
                 WHERE player_id = ?
                 ORDER BY timestamp DESC''', (player_id,))
    results = c.fetchall()
    conn.close()
    return results