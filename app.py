from flask import Flask, render_template, request, redirect, url_for, make_response
import database
import random
import json
from pulp import LpMaximize, LpMinimize, LpProblem, LpVariable, lpSum, LpBinary, value

app = Flask(__name__)

# RESULTS VISIBILITY TOGGLE
# Set to True to show results (with rating requirement), False to completely hide
SHOW_RESULTS = True

# MINIMUM RATINGS REQUIRED TO VIEW RESULTS
# Users must rate this many players before they can see results
# Set to 0 to allow anyone to view results immediately
MIN_RATINGS_TO_VIEW = 0

PLAYERS = [
    'Alex',
    'Gibbo',
    'Paolo',
    'Laff',
    'Fenton',
    'Jonny',
    'Tom',
    'Ed',
    'Scott',
    'Kev',
    'Adam',
    'Ilya',
    'Shaun',
    'Luke',
    'Kieran',
    'Farrar',
    'Jon',
    'Baker Jr',
    'Paul D',
    'Wysocki',
    'Gareth',
    'Harry Bass',
    'Si',
    'Dave',
    'Evan',
    'Ethan',
]

# Initialize database and add players on startup
database.init_db()
database.add_players_from_list(PLAYERS)

@app.route('/')
def index():
    """Home page - shows all players to rate"""
    players = database.get_players()
    # Randomize the order each time the page loads
    random.shuffle(players)
    
    # Get list of already rated players
    rated_players = request.cookies.get('rated_players', '[]')
    rated_players = json.loads(rated_players)
    
    # Debug output
    print(f"DEBUG: User has rated {len(rated_players)} players")
    print(f"DEBUG: MIN_RATINGS_TO_VIEW = {MIN_RATINGS_TO_VIEW}")
    print(f"DEBUG: SHOW_RESULTS = {SHOW_RESULTS}")
    
    # Check if user has rated enough players to view results
    can_view_results = SHOW_RESULTS and len(rated_players) >= MIN_RATINGS_TO_VIEW
    print(f"DEBUG: can_view_results = {can_view_results}")
    
    # Calculate progress percentage
    progress_percent = int((len(rated_players) / MIN_RATINGS_TO_VIEW * 100)) if MIN_RATINGS_TO_VIEW > 0 else 100
    
    return render_template('index.html', players=players, rated_players=rated_players, 
                         show_results=can_view_results, 
                         ratings_count=len(rated_players),
                         min_required=MIN_RATINGS_TO_VIEW,
                         progress_percent=progress_percent)

@app.route('/rate/<int:player_id>')
def rate_player(player_id):
    """Rating form for a specific player"""
    player = database.get_player_by_id(player_id)
    if not player:
        return redirect(url_for('index'))
    
    # Check if this player has already been rated by this browser
    rated_players = request.cookies.get('rated_players', '[]')
    rated_players = json.loads(rated_players)
    
    already_rated = player_id in rated_players
    
    return render_template('rate.html', player=player, already_rated=already_rated)

@app.route('/submit_rating/<int:player_id>', methods=['POST'])
def submit_rating(player_id):
    """Handle rating submission"""
    # Check if already rated
    rated_players = request.cookies.get('rated_players', '[]')
    rated_players = json.loads(rated_players)
    
    if player_id in rated_players:
        return "You have already rated this player!", 400
    
    try:
        print("Form data received:", request.form)
        
        ratings = {
            'defensive_workrate': int(request.form['defensive_workrate']),
            'attacking_workrate': int(request.form['attacking_workrate']),
            'fitness': int(request.form['fitness']),
            'passing_possession': int(request.form['passing_possession']),
            'defending_tackles': int(request.form['defending_tackles']),
            'shooting': int(request.form['shooting']),
            'physicality': int(request.form['physicality']),
            'pace': int(request.form['pace']),
            'goalkeeping': int(request.form['goalkeeping'])
        }
        
        database.add_rating(player_id, ratings)
        
        # Add this player to the rated list
        rated_players.append(player_id)
        
        # Create response with cookie
        response = make_response(redirect(url_for('thank_you', player_id=player_id)))
        response.set_cookie('rated_players', json.dumps(rated_players), max_age=60*60*24*365)  # 1 year
        
        return response
    except (ValueError, KeyError) as e:
        print(f"Error: {e}")
        return f"Invalid rating data: {e}", 400

@app.route('/thank_you/<int:player_id>')
def thank_you(player_id):
    """Thank you page after submitting rating"""
    player = database.get_player_by_id(player_id)
    
    # Check if user can now view results
    rated_players = request.cookies.get('rated_players', '[]')
    rated_players = json.loads(rated_players)
    can_view_results = SHOW_RESULTS and len(rated_players) >= MIN_RATINGS_TO_VIEW
    
    return render_template('thank_you.html', player=player, 
                         show_results=can_view_results,
                         ratings_count=len(rated_players),
                         min_required=MIN_RATINGS_TO_VIEW)

@app.route('/results')
def results():
    """View all average ratings"""
    # Check if results are enabled globally
    if not SHOW_RESULTS:
        return """
        <html>
        <head><title>Results Hidden</title></head>
        <body style="font-family: Arial; text-align: center; padding: 100px;">
            <h1>🔒 Results Are Currently Hidden</h1>
            <p style="color: #666; font-size: 18px;">The results will be revealed soon!</p>
            <a href="/" style="color: #007bff; text-decoration: none;">← Back to ratings</a>
        </body>
        </html>
        """, 403
    
    # Check if user has rated enough players
    rated_players = request.cookies.get('rated_players', '[]')
    rated_players = json.loads(rated_players)
    num_rated = len(rated_players)
    
    if num_rated < MIN_RATINGS_TO_VIEW:
        remaining = MIN_RATINGS_TO_VIEW - num_rated
        return f"""
        <html>
        <head><title>More Ratings Required</title></head>
        <body style="font-family: Arial; text-align: center; padding: 100px;">
            <h1>📊 Almost There!</h1>
            <p style="color: #666; font-size: 18px;">
                You need to rate at least <strong>{MIN_RATINGS_TO_VIEW} players</strong> to view results.
            </p>
            <p style="color: #007bff; font-size: 24px; margin: 30px 0;">
                You've rated: <strong>{num_rated}/{MIN_RATINGS_TO_VIEW}</strong>
            </p>
            <p style="color: #666; font-size: 18px;">
                Only <strong>{remaining} more</strong> to go!
            </p>
            <a href="/" style="display: inline-block; margin-top: 20px; padding: 12px 24px; 
                          background-color: #28a745; color: white; text-decoration: none; 
                          border-radius: 4px;">Rate More Players</a>
        </body>
        </html>
        """, 403
    
    # Use filtered averages to remove outliers
    averages = database.get_average_ratings_filtered(filter_outliers=True)
    return render_template('results.html', averages=averages)

@app.route('/player/<int:player_id>')
def player_detail(player_id):
    """View detailed ratings for a specific player"""
    player = database.get_player_by_id(player_id)
    if not player:
        return redirect(url_for('index'))
    
    ratings = database.get_player_ratings(player_id)
    averages = database.get_average_ratings()
    
    # Find this player's averages
    player_avg = next((a for a in averages if a[0] == player[1]), None)
    
    return render_template('player_detail.html', player=player, 
                         ratings=ratings, averages=player_avg)

@app.route('/clear_cookies')
def clear_cookies():
    """Clear the rated players cookie - useful after database reset"""
    response = make_response(redirect(url_for('index')))
    response.set_cookie('rated_players', '', max_age=0)  # Delete cookie
    return response

@app.route('/team_picker')
def team_picker():
    """Team picker page"""
    players = database.get_players()
    return render_template('team_picker.html', players=players, teams=None, error=None)

@app.route('/generate_teams', methods=['POST'])
def generate_teams():
    """Generate balanced teams using ILP"""
    selected_player_ids = request.form.getlist('players')
    
    # Validate selection
    if len(selected_player_ids) != 10:
        players = database.get_players()
        return render_template('team_picker.html', 
                             players=players, 
                             teams=None, 
                             error=f"Please select exactly 10 players (you selected {len(selected_player_ids)})")
    
    # Get player ratings (with outlier filtering)
    averages = database.get_average_ratings_filtered(filter_outliers=True)
    
    # Build player data with randomised ratings
    player_data = []
    for player_id_str in selected_player_ids:
        player_id = int(player_id_str)
        player = database.get_player_by_id(player_id)
        
        # Find average rating for this player
        player_avg = next((avg for avg in averages if avg[0] == player[1]), None)
        
        if player_avg and player_avg[10] > 0:  # Has ratings
            # Extract individual attributes
            # avg[1]=def_work, avg[2]=att_work, avg[3]=fitness, avg[4]=passing,
            # avg[5]=defending, avg[6]=shooting, avg[7]=physicality, avg[8]=pace, avg[9]=gk
            
            # DEFENDER RATING: defensive workrate, defending, physicality, goalkeeping, fitness
            defender_attrs = [
                player_avg[1] if player_avg[1] else 5.0,  # def workrate
                player_avg[5] if player_avg[5] else 5.0,  # defending
                player_avg[7] if player_avg[7] else 5.0,  # physicality
                player_avg[9] if player_avg[9] else 5.0,  # goalkeeping
                player_avg[3] if player_avg[3] else 5.0   # fitness
            ]
            defender_rating = sum(defender_attrs) / len(defender_attrs)
            
            # ATTACKER RATING: attacking workrate, passing, shooting, fitness, pace
            attacker_attrs = [
                player_avg[2] if player_avg[2] else 5.0,  # att workrate
                player_avg[4] if player_avg[4] else 5.0,  # passing
                player_avg[6] if player_avg[6] else 5.0,  # shooting
                player_avg[3] if player_avg[3] else 5.0,  # fitness
                player_avg[8] if player_avg[8] else 5.0   # pace
            ]
            attacker_rating = sum(attacker_attrs) / len(attacker_attrs)
            
            # Overall rating (for display)
            all_attrs = [player_avg[i] for i in range(1, 10) if player_avg[i]]
            overall_rating = sum(all_attrs) / len(all_attrs) if all_attrs else 5.0
        else:
            defender_rating = 5.0
            attacker_rating = 5.0
            overall_rating = 5.0
        
        # Add random variance (+/- 0.5 rating points)
        randomized_def = defender_rating + random.uniform(-0.5, 0.5)
        randomized_att = attacker_rating + random.uniform(-0.5, 0.5)
        
        player_data.append({
            'id': player_id,
            'name': player[1],
            'defender_rating': randomized_def,
            'attacker_rating': randomized_att,
            'overall_rating': overall_rating,
            'original_def': defender_rating,
            'original_att': attacker_rating
        })
    
    # Use ILP to balance teams
    teams = balance_teams_ilp(player_data)

    teams['bibs']    = assign_positions(teams['bibs'])
    teams['colours'] = assign_positions(teams['colours'])
    
    # Prepare data for template
    teams['selected_ids'] = selected_player_ids
    
    players = database.get_players()
    return render_template('team_picker.html', 
                         players=players, 
                         teams=teams, 
                         error=None)

def balance_teams_ilp(players):
    """Use Integer Linear Programming to create balanced teams on defender and attacker ratings"""
    n = len(players)
    
    # Create the problem
    prob = LpProblem("Team_Balancing", LpMinimize)
    
    # Decision variables: x[i] = 1 if player i is in team bibs, 0 if in colours
    x = {i: LpVariable(f"player_{i}", cat=LpBinary) for i in range(n)}
    
    # Variables for the differences
    diff_def = LpVariable("diff_defender", lowBound=0)
    diff_att = LpVariable("diff_attacker", lowBound=0)
    
    # Constraint: Each team must have exactly 5 players
    prob += lpSum([x[i] for i in range(n)]) == 5
    
    # Calculate team ratings for defenders
    bibs_def = lpSum([players[i]['defender_rating'] * x[i] for i in range(n)])
    colours_def = lpSum([players[i]['defender_rating'] * (1 - x[i]) for i in range(n)])
    
    # Calculate team ratings for attackers
    bibs_att = lpSum([players[i]['attacker_rating'] * x[i] for i in range(n)])
    colours_att = lpSum([players[i]['attacker_rating'] * (1 - x[i]) for i in range(n)])
    
    # Constraints for defender difference
    prob += diff_def >= bibs_def - colours_def
    prob += diff_def >= colours_def - bibs_def
    
    # Constraints for attacker difference
    prob += diff_att >= bibs_att - colours_att
    prob += diff_att >= colours_att - bibs_att
    
    # Objective: Minimize sum of both differences (equal weight to defending and attacking)
    prob += diff_def + diff_att
    
    # Solve
    prob.solve()
    
    # Extract results
    bibs = []
    colours = []
    
    for i in range(n):
        if value(x[i]) == 1:
            bibs.append({
                'name': players[i]['name'],
                'avg_rating': players[i]['overall_rating'],
                'def_rating': players[i]['original_def'],
                'att_rating': players[i]['original_att']
            })
        else:
            colours.append({
                'name': players[i]['name'],
                'avg_rating': players[i]['overall_rating'],
                'def_rating': players[i]['original_def'],
                'att_rating': players[i]['original_att']
            })
    
    # Calculate team averages
    bibs_avg = sum(p['avg_rating'] for p in bibs) / len(bibs)
    colours_avg = sum(p['avg_rating'] for p in colours) / len(colours)
    
    bibs_def_avg = sum(p['def_rating'] for p in bibs) / len(bibs)
    colours_def_avg = sum(p['def_rating'] for p in colours) / len(colours)
    
    bibs_att_avg = sum(p['att_rating'] for p in bibs) / len(bibs)
    colours_att_avg = sum(p['att_rating'] for p in colours) / len(colours)
    
    return {
        'bibs': bibs,
        'colours': colours,
        'bibs_avg': bibs_avg,
        'colours_avg': colours_avg,
        'bibs_def_avg': bibs_def_avg,
        'colours_def_avg': colours_def_avg,
        'bibs_att_avg': bibs_att_avg,
        'colours_att_avg': colours_att_avg
    }


def assign_positions(players):
    """
    Assign DEF / MID / FWD to 5 players based on their def/att ratings.
    Formation: 2 DEF, 2 MID, 1 FWD
    """
    # Sort players by defensive strength (def - att)
    sorted_players = sorted(players, key=lambda p: p['def_rating'] - p['att_rating'], reverse=True)

    # Top 2 → DEF
    for i in range(2):
        sorted_players[i]['position'] = 'DEF'

    # Bottom 1 → FWD (most attacking)
    sorted_players[-1]['position'] = 'FWD'

    # Middle 2 → MID
    for i in range(2, 4):
        sorted_players[i]['position'] = 'MID'

    return players


if __name__ == '__main__':
    # host='0.0.0.0' allows external connections (needed for ngrok)
    # debug=True gives helpful error messages
    app.run(debug=True, host='0.0.0.0', port=5000)