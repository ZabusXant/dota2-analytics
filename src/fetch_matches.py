import requests
import json
import time
import os

from utils.logger import root_logger as logger


def read_match_ids(file_path):
    with open(file_path, 'r') as f:
        return [line.strip() for line in f if line.strip().isdigit()]


def match_already_ingested(match_id, output_dir):
    return os.path.exists(os.path.join(output_dir, f"match_{match_id}.json"))


def fetch_match_data(match_id, max_retries=3, backoff_factor=2):
    url = f"https://api.opendota.com/api/matches/{match_id}"
    attempt = 0

    while attempt < max_retries:
        response = requests.get(url)
        status = response.status_code

        if status == 200:
            return response.json()
        elif 500 <= status < 600:
            wait_time = backoff_factor ** attempt
            logger.warning(f"Server error {status} for match {match_id}. Retrying in {wait_time}s...")
            time.sleep(wait_time)
            attempt += 1
        else:
            logger.error(f"Non-retryable error {status} for match {match_id}. Skipping.")
            return None

    logger.error(f"Failed to fetch match {match_id} after {max_retries} retries.")
    return None


def save_match_data(match_data, match_id, output_dir):
    with open(os.path.join(output_dir, f"match_{match_id}.json"), 'w') as f:
        json.dump(match_data, f, indent=2)


def ingest_matches(match_list_file, output_dir):
    match_ids = read_match_ids(match_list_file)
    for match_id in match_ids:
        if match_already_ingested(match_id, output_dir):
            logger.debug(f"Skipping match {match_id} (already ingested)")
            continue
        match_data = fetch_match_data(match_id)
        if match_data:
            save_match_data(match_data, match_id, output_dir)
            logger.info(f"Ingested match {match_id}")
        else:
            logger.error(f"Failed to fetch match {match_id}")


if __name__ == "__main__":
    ingest_matches("data/match_ids.txt", "data/raw_data/matches")
