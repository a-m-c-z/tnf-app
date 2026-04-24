import sqlite3
import statistics
import os

DB_PATH = os.environ.get('DB_PATH', 'ratings.db')


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS players
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT UNIQUE)''')

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

    # Gameweek teams storage
    c.execute('''CREATE TABLE IF NOT EXISTS gameweek_teams
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  gameweek_key TEXT UNIQUE,
                  bibs_players TEXT,
                  colours_players TEXT,
                  bibs_avg REAL,
                  colours_avg REAL,
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')

    # Gameweek results
    c.execute('''CREATE TABLE IF NOT EXISTS gameweek_results
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  gameweek_key TEXT UNIQUE,
                  result TEXT,
                  goal_difference INTEGER,
                  motm_player_id INTEGER,
                  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (motm_player_id) REFERENCES players(id))''')

    conn.commit()
    conn.close()


def add_players_from_list(player_names):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for name in player_names:
        try:
            c.execute("INSERT INTO players (name) VALUES (?)", (name,))
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    conn.close()


def get_players():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name FROM players ORDER BY name")
    players = c.fetchall()
    conn.close()
    return players


def get_player_by_id(player_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name FROM players WHERE id = ?", (player_id,))
    player = c.fetchone()
    conn.close()
    return player


def add_rating(player_id, ratings):
    conn = sqlite3.connect(DB_PATH)
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
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
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
                 ORDER BY p.name''')
    results = c.fetchall()
    conn.close()
    return results


def filter_outliers_for_player(ratings_data, z_threshold=2.0):
    if len(ratings_data) < 5:
        return ratings_data
    rating_averages = [sum(r) / len(r) for r in ratings_data]
    try:
        mean = statistics.mean(rating_averages)
        stdev = statistics.stdev(rating_averages)
        if stdev == 0:
            return ratings_data
        filtered_ratings = []
        for i, rating in enumerate(ratings_data):
            z_score = abs(rating_averages[i] - mean) / stdev
            if z_score < z_threshold:
                filtered_ratings.append(rating)
        if len(filtered_ratings) >= len(ratings_data) * 0.75:
            return filtered_ratings
        else:
            return ratings_data
    except statistics.StatisticsError:
        return ratings_data


def get_average_ratings_filtered(filter_outliers=True):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name FROM players ORDER BY name")
    players = c.fetchall()
    results = []
    for player_id, player_name in players:
        c.execute('''SELECT defensive_workrate, attacking_workrate,
                            fitness, passing_possession, defending_tackles,
                            shooting, physicality, pace, goalkeeping
                     FROM ratings WHERE player_id = ?''', (player_id,))
        ratings = c.fetchall()
        if not ratings:
            results.append((player_name, None, None, None, None, None, None, None, None, None, 0))
            continue
        if filter_outliers and len(ratings) >= 5:
            ratings = filter_outliers_for_player(ratings)
        num_ratings = len(ratings)
        averages = [
            round(sum(r[i] for r in ratings) / num_ratings, 1)
            for i in range(9)
        ]
        results.append((player_name, *averages, num_ratings))
    conn.close()
    return results


def get_player_ratings(player_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT defensive_workrate, attacking_workrate,
                        fitness, passing_possession, defending_tackles,
                        shooting, physicality, pace, goalkeeping, timestamp
                 FROM ratings WHERE player_id = ?
                 ORDER BY timestamp DESC''', (player_id,))
    results = c.fetchall()
    conn.close()
    return results


# ── Gameweek helpers ──────────────────────────────────────────────────────────

def save_gameweek_teams(gameweek_key, bibs, colours, bibs_avg, colours_avg):
    """Persist confirmed teams for a gameweek (upsert)."""
    import json
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO gameweek_teams
                     (gameweek_key, bibs_players, colours_players, bibs_avg, colours_avg, updated_at)
                 VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                 ON CONFLICT(gameweek_key) DO UPDATE SET
                     bibs_players   = excluded.bibs_players,
                     colours_players = excluded.colours_players,
                     bibs_avg       = excluded.bibs_avg,
                     colours_avg    = excluded.colours_avg,
                     updated_at     = CURRENT_TIMESTAMP''',
              (gameweek_key,
               json.dumps(bibs),
               json.dumps(colours),
               bibs_avg,
               colours_avg))
    conn.commit()
    conn.close()


def get_gameweek_teams(gameweek_key):
    import json
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT bibs_players, colours_players, bibs_avg, colours_avg FROM gameweek_teams WHERE gameweek_key = ?',
              (gameweek_key,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {
        'bibs': json.loads(row[0]),
        'colours': json.loads(row[1]),
        'bibs_avg': row[2],
        'colours_avg': row[3],
    }


def get_all_gameweeks():
    """Return all gameweeks with their teams and results, ordered by key."""
    import json
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT gt.gameweek_key,
                        gt.bibs_players, gt.colours_players,
                        gt.bibs_avg, gt.colours_avg,
                        gr.result, gr.goal_difference, gr.motm_player_id,
                        p.name as motm_name
                 FROM gameweek_teams gt
                 LEFT JOIN gameweek_results gr ON gt.gameweek_key = gr.gameweek_key
                 LEFT JOIN players p ON gr.motm_player_id = p.id
                 ORDER BY gt.gameweek_key''')
    rows = c.fetchall()
    conn.close()
    result = []
    for row in rows:
        result.append({
            'gameweek_key': row[0],
            'bibs': json.loads(row[1]),
            'colours': json.loads(row[2]),
            'bibs_avg': row[3],
            'colours_avg': row[4],
            'result': row[5],
            'goal_difference': row[6],
            'motm_player_id': row[7],
            'motm_name': row[8],
        })
    return result


def save_gameweek_result(gameweek_key, result, goal_difference, motm_player_id):
    """Upsert match result for a gameweek."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO gameweek_results
                     (gameweek_key, result, goal_difference, motm_player_id, updated_at)
                 VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                 ON CONFLICT(gameweek_key) DO UPDATE SET
                     result           = excluded.result,
                     goal_difference  = excluded.goal_difference,
                     motm_player_id   = excluded.motm_player_id,
                     updated_at       = CURRENT_TIMESTAMP''',
              (gameweek_key, result, goal_difference if goal_difference != '' else None, motm_player_id if motm_player_id else None))
    conn.commit()
    conn.close()


def get_season_stats(year=None):
    """
    Compute per-player season stats from gameweek data.
    Returns a dict keyed by player name.
    """
    import json
    from datetime import datetime
    if year is None:
        year = datetime.now().year

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT gt.gameweek_key,
                        gt.bibs_players, gt.colours_players,
                        gr.result, gr.goal_difference, gr.motm_player_id,
                        p.name as motm_name
                 FROM gameweek_teams gt
                 LEFT JOIN gameweek_results gr ON gt.gameweek_key = gr.gameweek_key
                 LEFT JOIN players p ON gr.motm_player_id = p.id
                 WHERE gt.gameweek_key LIKE ?''', (f'%-{year}',))
    rows = c.fetchall()
    conn.close()

    # player_name -> stats dict
    stats = {}

    def ensure(name):
        if name not in stats:
            stats[name] = {
                'games': 0, 'wins': 0, 'losses': 0, 'draws': 0,
                'motm': 0, 'win_streak': 0, 'loss_streak': 0,
                '_cur_win_streak': 0, '_cur_loss_streak': 0,
                'partnerships': {},   # partner_name -> {wins, games}
            }

    for row in rows:
        gw_key = row[0]
        bibs = json.loads(row[1])
        colours = json.loads(row[2])
        result = row[3]      # 'bibs_win' / 'colours_win' / 'draw' / None
        motm_player_id = row[5]
        motm_name = row[6]

        bibs_names = [p['name'] for p in bibs]
        colours_names = [p['name'] for p in colours]

        for name in bibs_names + colours_names:
            ensure(name)

        if motm_name:
            ensure(motm_name)
            stats[motm_name]['motm'] += 1

        if result is None:
            continue

        def update_players(team_names, won, drew):
            for name in team_names:
                ensure(name)
                stats[name]['games'] += 1
                if drew:
                    stats[name]['draws'] += 1
                    stats[name]['_cur_win_streak'] = 0
                    stats[name]['_cur_loss_streak'] = 0
                elif won:
                    stats[name]['wins'] += 1
                    stats[name]['_cur_win_streak'] += 1
                    stats[name]['_cur_loss_streak'] = 0
                    stats[name]['win_streak'] = max(
                        stats[name]['win_streak'],
                        stats[name]['_cur_win_streak']
                    )
                else:
                    stats[name]['losses'] += 1
                    stats[name]['_cur_loss_streak'] += 1
                    stats[name]['_cur_win_streak'] = 0
                    stats[name]['loss_streak'] = max(
                        stats[name]['loss_streak'],
                        stats[name]['_cur_loss_streak']
                    )
            # Partnership tracking (only count wins)
            if won and not drew:
                for i, name in enumerate(team_names):
                    for j, partner in enumerate(team_names):
                        if i != j:
                            if partner not in stats[name]['partnerships']:
                                stats[name]['partnerships'][partner] = {'wins': 0, 'games': 0}
                            stats[name]['partnerships'][partner]['wins'] += 1
            # Track games for partnerships regardless
            for i, name in enumerate(team_names):
                for j, partner in enumerate(team_names):
                    if i != j:
                        if partner not in stats[name]['partnerships']:
                            stats[name]['partnerships'][partner] = {'wins': 0, 'games': 0}
                        stats[name]['partnerships'][partner]['games'] += 1

        bibs_won = result == 'bibs_win'
        colours_won = result == 'colours_win'
        drew = result == 'draw'

        update_players(bibs_names, bibs_won, drew)
        update_players(colours_names, colours_won, drew)

    # Clean up internal streak trackers
    for name in stats:
        stats[name].pop('_cur_win_streak', None)
        stats[name].pop('_cur_loss_streak', None)

    # Compute win/loss percentages
    for name in stats:
        g = stats[name]['games']
        stats[name]['win_pct'] = round(stats[name]['wins'] / g * 100, 1) if g > 0 else 0
        stats[name]['loss_pct'] = round(stats[name]['losses'] / g * 100, 1) if g > 0 else 0

    # Best/worst partnerships (min 3 games together)
    for name in stats:
        partners = stats[name]['partnerships']
        eligible = {p: v for p, v in partners.items() if v['games'] >= 3}
        if eligible:
            best = max(eligible, key=lambda p: eligible[p]['wins'] / eligible[p]['games'])
            worst = min(eligible, key=lambda p: eligible[p]['wins'] / eligible[p]['games'])
            stats[name]['best_partner'] = best
            stats[name]['best_partner_win_pct'] = round(eligible[best]['wins'] / eligible[best]['games'] * 100, 1)
            stats[name]['worst_partner'] = worst
            stats[name]['worst_partner_win_pct'] = round(eligible[worst]['wins'] / eligible[worst]['games'] * 100, 1)
        else:
            stats[name]['best_partner'] = None
            stats[name]['worst_partner'] = None
            stats[name]['best_partner_win_pct'] = 0
            stats[name]['worst_partner_win_pct'] = 0

    return stats


def delete_gameweek(gameweek_key):
    """Delete a gameweek and its result entirely."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM gameweek_results WHERE gameweek_key = ?', (gameweek_key,))
    c.execute('DELETE FROM gameweek_teams WHERE gameweek_key = ?', (gameweek_key,))
    conn.commit()
    conn.close()


def save_gameweek_teams_manual(gameweek_key, bibs_names, colours_names):
    """
    Save a retrospective gameweek given just player names.
    Looks up ratings to compute averages; falls back to 5.0 if no ratings found.
    """
    import json
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    def avg_for(name):
        c.execute('''SELECT AVG(defensive_workrate + attacking_workrate + fitness +
                                passing_possession + defending_tackles + shooting +
                                physicality + pace + goalkeeping) / 9.0
                     FROM ratings r
                     JOIN players p ON r.player_id = p.id
                     WHERE p.name = ?''', (name,))
        row = c.fetchone()
        return round(row[0], 2) if row and row[0] else 5.0

    bibs    = [{'name': n, 'avg_rating': avg_for(n), 'def_rating': 5.0, 'att_rating': 5.0} for n in bibs_names]
    colours = [{'name': n, 'avg_rating': avg_for(n), 'def_rating': 5.0, 'att_rating': 5.0} for n in colours_names]

    bibs_avg    = sum(p['avg_rating'] for p in bibs)    / len(bibs)    if bibs    else 5.0
    colours_avg = sum(p['avg_rating'] for p in colours) / len(colours) if colours else 5.0

    c.execute('''INSERT INTO gameweek_teams
                     (gameweek_key, bibs_players, colours_players, bibs_avg, colours_avg, updated_at)
                 VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                 ON CONFLICT(gameweek_key) DO UPDATE SET
                     bibs_players    = excluded.bibs_players,
                     colours_players = excluded.colours_players,
                     bibs_avg        = excluded.bibs_avg,
                     colours_avg     = excluded.colours_avg,
                     updated_at      = CURRENT_TIMESTAMP''',
              (gameweek_key, json.dumps(bibs), json.dumps(colours), bibs_avg, colours_avg))
    conn.commit()
    conn.close()