from flask import Flask, render_template, request, redirect, url_for, make_response, session, jsonify
import database
import random
import json
import os
from datetime import date, timedelta
from functools import wraps
from pulp import LpMinimize, LpProblem, LpVariable, lpSum, LpBinary, value

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-me')

# ── Config ────────────────────────────────────────────────────────────────────
SHOW_RESULTS   = True
MIN_RATINGS_TO_VIEW = 0
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

PLAYERS = [
    'Alex', 'Gibbo', 'Paolo', 'Laff', 'Fenton', 'Jonny', 'Tom', 'Ed',
    'Scott', 'Kev', 'Adam', 'Ilya', 'Shaun', 'Luke', 'Kieran', 'Farrar',
    'Jon', 'Baker Jr', 'Paul D', 'Wysocki', 'Gareth', 'Harry Bass', 'Si',
    'Dave', 'Evan', 'Ethan',
]

database.init_db()
database.add_players_from_list(PLAYERS)


# ── Gameweek helpers ──────────────────────────────────────────────────────────

def get_current_gameweek_key(for_date=None):
    """
    Return 'GW-YYYY' string for the NEXT Tuesday relative to for_date.
    If for_date IS a Tuesday, that Tuesday is used (same day counts as next).
    Wednesday through Monday → assign to the following Tuesday.
    """
    d = for_date or date.today()
    # weekday(): Monday=0 … Sunday=6  →  Tuesday=1
    days_until_tuesday = (1 - d.weekday()) % 7
    if days_until_tuesday == 0:
        # Today is Tuesday
        target = d
    else:
        target = d + timedelta(days=days_until_tuesday)

    # Count which Tuesday of the year this is
    year_start = date(target.year, 1, 1)
    # Find first Tuesday of the year
    days_to_first_tuesday = (1 - year_start.weekday()) % 7
    first_tuesday = year_start + timedelta(days=days_to_first_tuesday)

    gw_number = ((target - first_tuesday).days // 7) + 1
    return f"{gw_number}-{target.year}"


# ── Auth ──────────────────────────────────────────────────────────────────────

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    """Default page is now the team picker."""
    return redirect(url_for('team_picker'))


@app.route('/rate')
def rate_index():
    players = database.get_players()
    random.shuffle(players)
    rated_players = json.loads(request.cookies.get('rated_players', '[]'))
    can_view_results = SHOW_RESULTS and len(rated_players) >= MIN_RATINGS_TO_VIEW
    progress_percent = int((len(rated_players) / MIN_RATINGS_TO_VIEW * 100)) if MIN_RATINGS_TO_VIEW > 0 else 100
    return render_template('index.html', players=players, rated_players=rated_players,
                           show_results=can_view_results,
                           ratings_count=len(rated_players),
                           min_required=MIN_RATINGS_TO_VIEW,
                           progress_percent=progress_percent)


@app.route('/rate/<int:player_id>')
def rate_player(player_id):
    player = database.get_player_by_id(player_id)
    if not player:
        return redirect(url_for('rate_index'))
    rated_players = json.loads(request.cookies.get('rated_players', '[]'))
    already_rated = player_id in rated_players
    return render_template('rate.html', player=player, already_rated=already_rated)


@app.route('/submit_rating/<int:player_id>', methods=['POST'])
def submit_rating(player_id):
    rated_players = json.loads(request.cookies.get('rated_players', '[]'))
    if player_id in rated_players:
        return "You have already rated this player!", 400
    try:
        ratings = {
            'defensive_workrate': int(request.form['defensive_workrate']),
            'attacking_workrate': int(request.form['attacking_workrate']),
            'fitness':            int(request.form['fitness']),
            'passing_possession': int(request.form['passing_possession']),
            'defending_tackles':  int(request.form['defending_tackles']),
            'shooting':           int(request.form['shooting']),
            'physicality':        int(request.form['physicality']),
            'pace':               int(request.form['pace']),
            'goalkeeping':        int(request.form['goalkeeping']),
        }
        database.add_rating(player_id, ratings)
        rated_players.append(player_id)
        response = make_response(redirect(url_for('thank_you', player_id=player_id)))
        response.set_cookie('rated_players', json.dumps(rated_players), max_age=60*60*24*365)
        return response
    except (ValueError, KeyError) as e:
        return f"Invalid rating data: {e}", 400


@app.route('/thank_you/<int:player_id>')
def thank_you(player_id):
    player = database.get_player_by_id(player_id)
    rated_players = json.loads(request.cookies.get('rated_players', '[]'))
    can_view_results = SHOW_RESULTS and len(rated_players) >= MIN_RATINGS_TO_VIEW
    return render_template('thank_you.html', player=player,
                           show_results=can_view_results,
                           ratings_count=len(rated_players),
                           min_required=MIN_RATINGS_TO_VIEW)


@app.route('/results')
def results():
    if not SHOW_RESULTS:
        return "<h1>Results hidden</h1>", 403
    rated_players = json.loads(request.cookies.get('rated_players', '[]'))
    if len(rated_players) < MIN_RATINGS_TO_VIEW:
        return redirect(url_for('rate_index'))
    averages = database.get_average_ratings_filtered(filter_outliers=True)
    return render_template('results.html', averages=averages)


@app.route('/player/<int:player_id>')
def player_detail(player_id):
    player = database.get_player_by_id(player_id)
    if not player:
        return redirect(url_for('rate_index'))
    ratings  = database.get_player_ratings(player_id)
    averages = database.get_average_ratings()
    player_avg = next((a for a in averages if a[0] == player[1]), None)
    return render_template('player_detail.html', player=player,
                           ratings=ratings, averages=player_avg)


@app.route('/clear_cookies')
def clear_cookies():
    response = make_response(redirect(url_for('rate_index')))
    response.set_cookie('rated_players', '', max_age=0)
    return response


# ── Team Picker ───────────────────────────────────────────────────────────────

@app.route('/team_picker')
def team_picker():
    players = database.get_players()
    gw_key  = get_current_gameweek_key()
    existing = database.get_gameweek_teams(gw_key)
    return render_template('team_picker.html', players=players,
                           teams=None, error=None,
                           gameweek_key=gw_key, existing=existing)


@app.route('/generate_teams', methods=['POST'])
def generate_teams():
    selected_player_ids = request.form.getlist('players')
    if len(selected_player_ids) != 10:
        players = database.get_players()
        gw_key  = get_current_gameweek_key()
        return render_template('team_picker.html',
                               players=players, teams=None,
                               error=f"Please select exactly 10 players (you selected {len(selected_player_ids)})",
                               gameweek_key=gw_key, existing=None)

    averages = database.get_average_ratings_filtered(filter_outliers=True)
    player_data = []
    for player_id_str in selected_player_ids:
        player_id  = int(player_id_str)
        player     = database.get_player_by_id(player_id)
        player_avg = next((avg for avg in averages if avg[0] == player[1]), None)

        if player_avg and player_avg[10] > 0:
            def_attrs = [player_avg[1] or 5.0, player_avg[5] or 5.0,
                         player_avg[7] or 5.0, player_avg[9] or 5.0, player_avg[3] or 5.0]
            att_attrs = [player_avg[2] or 5.0, player_avg[4] or 5.0,
                         player_avg[6] or 5.0, player_avg[3] or 5.0, player_avg[8] or 5.0]
            defender_rating = sum(def_attrs) / len(def_attrs)
            attacker_rating = sum(att_attrs) / len(att_attrs)
            all_attrs = [player_avg[i] for i in range(1, 10) if player_avg[i]]
            overall_rating = sum(all_attrs) / len(all_attrs) if all_attrs else 5.0
        else:
            defender_rating = attacker_rating = overall_rating = 5.0

        player_data.append({
            'id': player_id,
            'name': player[1],
            'defender_rating': defender_rating + random.uniform(-0.5, 0.5),
            'attacker_rating': attacker_rating + random.uniform(-0.5, 0.5),
            'overall_rating':  overall_rating,
            'original_def':    defender_rating,
            'original_att':    attacker_rating,
        })

    teams = balance_teams_ilp(player_data)
    teams['bibs']    = assign_positions(teams['bibs'])
    teams['colours'] = assign_positions(teams['colours'])
    teams['selected_ids'] = selected_player_ids

    gw_key = get_current_gameweek_key()
    players = database.get_players()
    return render_template('team_picker.html',
                           players=players, teams=teams, error=None,
                           gameweek_key=gw_key, existing=None)


@app.route('/confirm_teams', methods=['POST'])
def confirm_teams():
    """Save the current teams to the database for this gameweek."""
    gw_key      = request.form.get('gameweek_key')
    bibs_json   = request.form.get('bibs_json')
    colours_json= request.form.get('colours_json')
    bibs_avg    = float(request.form.get('bibs_avg', 0))
    colours_avg = float(request.form.get('colours_avg', 0))

    bibs    = json.loads(bibs_json)
    colours = json.loads(colours_json)

    database.save_gameweek_teams(gw_key, bibs, colours, bibs_avg, colours_avg)
    return redirect(url_for('team_picker') + f'?confirmed={gw_key}')


# ── Admin ─────────────────────────────────────────────────────────────────────

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin'))
        error = 'Incorrect password.'
    return render_template('admin_login.html', error=error)


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))


@app.route('/admin')
@admin_required
def admin():
    from datetime import datetime
    year = int(request.args.get('year', datetime.now().year))
    gameweeks = database.get_all_gameweeks()
    # filter to this year
    gw_this_year = [gw for gw in gameweeks if gw['gameweek_key'].endswith(f'-{year}')]
    all_players  = database.get_players()
    stats        = database.get_season_stats(year)
    current_gw   = get_current_gameweek_key()
    return render_template('admin.html',
                           gameweeks=gw_this_year,
                           all_players=all_players,
                           stats=stats,
                           year=year,
                           current_gw=current_gw)


@app.route('/admin/save_result', methods=['POST'])
@admin_required
def save_result():
    gw_key         = request.form.get('gameweek_key')
    result         = request.form.get('result')
    goal_difference= request.form.get('goal_difference', '')
    motm_player_id = request.form.get('motm_player_id') or None
    database.save_gameweek_result(gw_key, result, goal_difference, motm_player_id)
    return redirect(url_for('admin'))


# ── ILP helpers ───────────────────────────────────────────────────────────────

def balance_teams_ilp(players):
    n    = len(players)
    prob = LpProblem("Team_Balancing", LpMinimize)
    x    = {i: LpVariable(f"player_{i}", cat=LpBinary) for i in range(n)}
    diff_def = LpVariable("diff_defender", lowBound=0)
    diff_att = LpVariable("diff_attacker", lowBound=0)

    prob += lpSum([x[i] for i in range(n)]) == 5

    bibs_def   = lpSum([players[i]['defender_rating'] * x[i] for i in range(n)])
    colours_def = lpSum([players[i]['defender_rating'] * (1 - x[i]) for i in range(n)])
    bibs_att   = lpSum([players[i]['attacker_rating'] * x[i] for i in range(n)])
    colours_att = lpSum([players[i]['attacker_rating'] * (1 - x[i]) for i in range(n)])

    prob += diff_def >= bibs_def - colours_def
    prob += diff_def >= colours_def - bibs_def
    prob += diff_att >= bibs_att - colours_att
    prob += diff_att >= colours_att - bibs_att
    prob += diff_def + diff_att
    prob.solve()

    bibs, colours = [], []
    for i in range(n):
        entry = {
            'name':       players[i]['name'],
            'avg_rating': players[i]['overall_rating'],
            'def_rating': players[i]['original_def'],
            'att_rating': players[i]['original_att'],
        }
        (bibs if value(x[i]) == 1 else colours).append(entry)

    return {
        'bibs': bibs, 'colours': colours,
        'bibs_avg':      sum(p['avg_rating'] for p in bibs)    / len(bibs),
        'colours_avg':   sum(p['avg_rating'] for p in colours) / len(colours),
        'bibs_def_avg':  sum(p['def_rating'] for p in bibs)    / len(bibs),
        'colours_def_avg': sum(p['def_rating'] for p in colours) / len(colours),
        'bibs_att_avg':  sum(p['att_rating'] for p in bibs)    / len(bibs),
        'colours_att_avg': sum(p['att_rating'] for p in colours) / len(colours),
    }


def assign_positions(players):
    sorted_players = sorted(players, key=lambda p: p['def_rating'] - p['att_rating'], reverse=True)
    for i in range(2):
        sorted_players[i]['position'] = 'DEF'
    sorted_players[-1]['position'] = 'FWD'
    for i in range(2, 4):
        sorted_players[i]['position'] = 'MID'
    return players


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

@app.route('/migrate-db')
def migrate_db():
    import shutil, os
    src = '/app/ratings.db'  # Railway puts your repo files here
    dst = os.environ.get('DB_PATH', '/data/ratings.db')
    if os.path.exists(src):
        shutil.copy2(src, dst)
        return f"Copied {src} to {dst} ✅"
    return f"Source not found at {src} ❌"