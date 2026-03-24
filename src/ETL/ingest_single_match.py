from ..utils.fetch_matches import fetch_match_data
import pandas as pd
from ..utils.db_connection import DotaDB

def ingest_single_match(match_id, db):
    match_data = fetch_match_data(match_id)
    if not match_data:
        print(f"Failed to fetch match {match_id}")
        return
    
    with db.transaction():
        db.insert_ignore(extract_match_row(match_data), "matches", ["match_id"])
        db.insert_ignore(extract_picks_bans(match_data), "picks_bans", ['hero_id'])
        db.insert_ignore(pd.DataFrame(get_teams_from_match(match_data).values()), "teams", ["team_id"])
        db.insert_ignore(get_players_from_match(match_data), "players", ["player_id"])


def get_players_from_match(match_data):
    radiant_team_id = match_data.get("radiant_team_id")
    dire_team_id = match_data.get("dire_team_id")
    players = []
    for p in match_data.get("players", []):
        p = {
            "player_id": p.get("account_id"),
            "team_id": radiant_team_id if p.get("isRadiant") else dire_team_id,
            "player_name": p.get("personaname"),
            "hero_id": p.get("hero_id"),
            "kills": p.get("hero_kills"),
            "deaths": p.get("deaths"),
            "assists": p.get("assists"),
            # more to be added as needed
        }
    return pd.DataFrame(players)

def get_teams_from_match(match_data):
    teams = {}
    for team in ["radiant", "dire"]:
        team_id = match_data.get(f"{team}_team_id")
        if team_id:
            teams[team_id] = {
                "team_id": team_id,
                "team_name": match_data.get(f"{team}_name"),
                # more to be added as needed
            }
    return teams

def extract_match_row(data):
    return pd.DataFrame([data])

def extract_picks_bans(match_data):
    picks_bans = []
    for pb in match_data.get("picks_bans", []):
        picks_bans.append({
            "match_id": match_data.get("match_id"),
            "hero_id": pb.get("hero_id"),
            "is_pick": pb.get("is_pick"),
            "order": pb.get("order"),
        })
    return pd.DataFrame(picks_bans)

