"""
Seed the local database with 20 fake retrospective gameweeks (year 2025)
so features like player "form" can be tested without waiting for real
match data to accumulate.

Uses random combinations of the real (non-guest) player roster, with a
random result and occasional Man of the Match for each gameweek.

Usage: python seed_fake_gameweeks.py
"""
import random

import database
from app import PLAYERS  # noqa: F401  (importing app.py also runs init_db() + seeds players)

YEAR = 2025
NUM_GAMEWEEKS = 20


def seed_fake_gameweeks():
    all_players = database.get_players()
    roster = [(pid, name) for pid, name in all_players if name not in database.GUEST_NAMES]
    name_to_id = {name: pid for pid, name in roster}
    roster_names = list(name_to_id.keys())

    if len(roster_names) < 10:
        print(f"Need at least 10 non-guest players, found {len(roster_names)}. Aborting.")
        return

    for gw_number in range(1, NUM_GAMEWEEKS + 1):
        gw_key = f"{gw_number}-{YEAR}"

        selected = random.sample(roster_names, 10)
        random.shuffle(selected)
        bibs_names, colours_names = selected[:5], selected[5:]

        result = random.choices(
            ['bibs_win', 'colours_win', 'draw'],
            weights=[0.42, 0.42, 0.16]
        )[0]
        goal_difference = random.randint(1, 5) if result != 'draw' else ''
        motm_player_id = name_to_id[random.choice(selected)] if random.random() < 0.8 else None

        database.save_gameweek_teams_manual(gw_key, bibs_names, colours_names)
        database.save_gameweek_result(gw_key, result, goal_difference, motm_player_id)

        print(f"GW {gw_key}: {bibs_names} vs {colours_names} -> {result}")

    print(f"\n✓ Seeded {NUM_GAMEWEEKS} fake gameweeks for {YEAR}.")
    print(f"  View them at /admin?year={YEAR} or /standings?year={YEAR}")


if __name__ == "__main__":
    seed_fake_gameweeks()
