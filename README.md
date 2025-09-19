# Dota 2 Match Analytics Pipeline

This project is a modular data engineering pipeline for extracting and normalizing structured insights from parsed Dota 2 match data. It is designed to simulate a modern analytics stack using open-source tools and local development for the time being.

## 📦 Current Features

- ✅ Normalizes player-level statistics from parsed match JSON files
- ✅ Outputs structured tables for player performance
- ✅ Separation of raw and processed data
- ✅ Modular transformation logic for future expansion

## 🧠 Project Structure

```
Dota Data/
├── data/
│   ├── raw/
│   │   └── matches/
│   │       └── <match_id>.json
│   └── processed_data/
│       └── <match_id>/
│           ├── players.parquet
│           ├── match.parquet
│           ├── draft.parquet
│           └── ...
├── notebooks/
│   └── test_files/
├── src/
│   ├── normalize_data.py
│   └── utils/
│       └── fetch_matches.py
├── env/
├── .gitignore
└── README.md
```

## 🧪 How to Use

1. Place parsed match JSON files in `data/raw_data/`
2. Run normalization functions from `src/normalize_data.py`
3. Outputs will be saved in `data/processed_data/<match_id>/`

## 🚀 Future Plans

- Add draft, match, objective, and teamfight normalization
- Integrate time-series metrics (net worth, XP, last hits per minute)
- Simulate tournament-level analytics with team mapping
- Explore enrichment via OpenDota metadata (heroes, items)
- Package pipeline for reproducible ingestion and analysis

---

