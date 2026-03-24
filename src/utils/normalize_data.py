import pandas as pd
import json


def extract_player_stats(match_json):
    match_id = match_json.get("match_id")
    players = match_json.get("players", [])

    rows = []
    for player in players:
        benchmarks = player.get("benchmarks")
        row = {
            "match_id": match_id,
            "account_id": player.get("account_id"),
            "hero_id": player.get("hero_id"),
            "kills": player.get("kills"),
            "deaths": player.get("deaths"),
            "assists": player.get("assists"),
            "last_hits": player.get("last_hits"),
            "denies": player.get("denies"),
            "gold_per_min": player.get("gold_per_min"),
            "xp_per_min": player.get("xp_per_min"),
            "level": player.get("level"),
            "net_worth": player.get("net_worth"),
            "item_0": player.get("item_0"),
            "item_1": player.get("item_1"),
            "item_2": player.get("item_2"),
            "item_3": player.get("item_3"),
            "item_4": player.get("item_4"),
            "item_5": player.get("item_5"),
            "aghanims_scepter": player.get("aghanims_scepter"),
            "aghanims_shard": player.get("aghanims_shard"),
            "moonshard": player.get("moonshard"),
            "hero_damage": player.get("hero_damage"),
            "tower_damage": player.get("tower_damage"),
            "hero_healing": player.get("hero_healing"),
            "gold": player.get("gold"),
            "gold_spent": player.get("gold_spent"),
            "kills_per_min": player.get("kills_per_min"),
            "last_hits_per_min": benchmarks.get("last_hits_per_min").get("raw"),
            "hero_damage_per_min": benchmarks.get("hero_damage_per_min").get("raw"),
            "hero_healing_per_min": benchmarks.get("hero_healing_per_min").get("raw"),
        }
        rows.append(row)

    return pd.DataFrame(rows)
