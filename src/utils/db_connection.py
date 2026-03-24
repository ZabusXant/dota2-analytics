import os
import logging
from contextlib import contextmanager
from typing import Optional

import pandas as pd
import json
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Connection config — reads from environment variables.
# Add these to your .env file and load with python-dotenv:
#
#   SNOWFLAKE_ACCOUNT=your_account_identifier   # e.g. xy12345.eu-west-1
#   SNOWFLAKE_USER=your_username
#   SNOWFLAKE_PASSWORD=your_password
#   SNOWFLAKE_WAREHOUSE=your_warehouse
#   SNOWFLAKE_DATABASE=your_database
#   SNOWFLAKE_SCHEMA=your_schema
# ---------------------------------------------------------------------------

def _get_conn_params() -> dict:
    return {
        "account":   os.environ.get("SNOWFLAKE_ACCOUNT"),
        "user":      os.environ.get("SNOWFLAKE_USER"),
        "password":  os.environ.get("SNOWFLAKE_PASSWORD"),
        "warehouse": os.environ.get("SNOWFLAKE_WAREHOUSE"),
        "database":  os.environ.get("SNOWFLAKE_DATABASE"),
        "schema":    os.environ.get("SNOWFLAKE_SCHEMA"),
    }

def _serialize_complex_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Convert any column containing dicts or lists to JSON strings for Snowflake VARIANT compatibility."""
        df = df.copy()
        for col in df.columns:
            if df[col].dtype == object:
                # Check if any value in the column is a dict or list
                sample = df[col].dropna().head(10)
                if any(isinstance(v, (dict, list)) for v in sample):
                    df[col] = df[col].apply(
                        lambda x: json.dumps(x) if isinstance(x, (dict, list)) else x
                    )
        return df


# ---------------------------------------------------------------------------
# Core connector class
# ---------------------------------------------------------------------------

class DotaDB:
    """
    Snowflake connector for the Dota 2 analytics pipeline.
    Uses snowflake-connector-python under the hood.

    Install: pip install snowflake-connector-python[pandas]

    Demo assumptions (all data is immutable — no roster changes, no re-parsing):
      - All tables use insert_ignore: existing rows are never overwritten.
      - upsert() is kept for future use but not called in the demo pipeline.

    Usage:
        # As a context manager (auto-closes connection):
        with DotaDB() as db:
            db.insert_ignore(df_matches, "matches", conflict_columns=["match_id"])

        # Or keep alive across multiple operations:
        db = DotaDB()
        db.insert_ignore(df_teams, "teams", conflict_columns=["team_id"])
        db.insert_ignore(df_players, "players", conflict_columns=["player_id"])
        db.close()
    """

    def __init__(self):
        self._conn = None
        self.connect()

    def connect(self):
        """Open the Snowflake connection."""
        try:
            self._conn = snowflake.connector.connect(**_get_conn_params())
            logger.info("Connected to Snowflake")
        except snowflake.connector.errors.DatabaseError as e:
            logger.error(f"Failed to connect to Snowflake: {e}")
            raise

    def close(self):
        """Close the Snowflake connection."""
        if self._conn and not self._conn.is_closed():
            self._conn.close()
            logger.info("Snowflake connection closed")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        self.close()

    # -----------------------------------------------------------------------
    # Transaction helpers
    # -----------------------------------------------------------------------

    def commit(self):
        self._conn.cursor().execute("COMMIT")

    def rollback(self):
        self._conn.cursor().execute("ROLLBACK")

    @contextmanager
    def transaction(self):
        """
        Context manager for explicit transaction blocks.
        All operations inside succeed or fail together.

        Example:
            with db.transaction():
                db.insert_ignore(df_matches, "matches", conflict_columns=["match_id"])
                db.insert_ignore(df_performances, "match_performances",
                                 conflict_columns=["match_id", "player_id"])
        """
        self._conn.cursor().execute("BEGIN")
        try:
            yield
            self.commit()
        except Exception as e:
            self.rollback()
            logger.error(f"Transaction rolled back due to: {e}")
            raise

    # -----------------------------------------------------------------------
    # Core write operations
    # -----------------------------------------------------------------------

    def insert_ignore(
        self,
        df: pd.DataFrame,
        table: str,
        conflict_columns: list[str],
    ):
        """
        Insert rows from a DataFrame, silently skipping any that already exist.
        This is the standard write method for the demo — all data is immutable.

        Snowflake does not have ON CONFLICT DO NOTHING like PostgreSQL, so this
        is implemented as a MERGE statement that only inserts when the key is
        not already present.

        Args:
            df:               DataFrame to load.
            table:            Target table name.
            conflict_columns: Columns that define uniqueness (the PK/unique constraint).

        Examples:
            db.insert_ignore(df_matches, "matches", conflict_columns=["match_id"])
            db.insert_ignore(df_teams, "teams", conflict_columns=["team_id"])
            db.insert_ignore(df_players, "players", conflict_columns=["player_id"])
            db.insert_ignore(df_heroes, "heroes", conflict_columns=["id"])
            db.insert_ignore(df_performances, "match_performances",
                             conflict_columns=["match_id", "player_id"])
            db.insert_ignore(df_picks_bans, "picks_bans",
                             conflict_columns=["match_id", "hero_id"])
        """
        if df.empty:
            logger.warning(f"Empty DataFrame passed for table '{table}', skipping.")
            return

        # Snowflake requires uppercase column names when using write_pandas
        df = _serialize_complex_columns(df)
        df.columns = [c.upper() for c in df.columns]
        conflict_columns_upper = [c.upper() for c in conflict_columns]
        non_conflict_columns   = [c for c in df.columns if c not in conflict_columns_upper]

        # Stage the data into a temporary table then MERGE into the target
        tmp_table = f"{table.upper()}_TMP"

        # Write to a temp table first
        write_pandas(
            self._conn,
            df,
            tmp_table,
            auto_create_table=True,
            overwrite=True,
            table_type="TEMPORARY",
        )

        # Build the MERGE join condition
        join_condition = " AND ".join(
            [f"target.{c} = source.{c}" for c in conflict_columns_upper]
        )

        # Build the INSERT column/value lists
        all_cols    = ", ".join(df.columns)
        source_cols = ", ".join([f"source.{c}" for c in df.columns])

        merge_sql = f"""
            MERGE INTO {table.upper()} AS target
            USING {tmp_table} AS source
            ON {join_condition}
            WHEN NOT MATCHED THEN
                INSERT ({all_cols})
                VALUES ({source_cols})
        """

        self._conn.cursor().execute(merge_sql)
        logger.info(f"Inserted (ignore conflicts) {len(df)} rows into {table.upper()}")

    def upsert(
        self,
        df: pd.DataFrame,
        table: str,
        conflict_columns: list[str],
        update_columns: Optional[list[str]] = None,
    ):
        """
        Insert rows from a DataFrame, updating on conflict.
        Not used in the demo (all data assumed immutable) but kept for future use,
        e.g. when re-parsing matches or handling roster changes post-demo.

        Args:
            df:               DataFrame to load.
            table:            Target table name.
            conflict_columns: Columns that define uniqueness (the PK/unique constraint).
            update_columns:   Columns to update on conflict. Defaults to all non-conflict columns.
        """
        if df.empty:
            logger.warning(f"Empty DataFrame passed for table '{table}', skipping.")
            return

        df.columns = [c.upper() for c in df.columns]
        conflict_columns_upper = [c.upper() for c in conflict_columns]

        if update_columns is None:
            update_columns = [c for c in df.columns if c not in conflict_columns_upper]
        else:
            update_columns = [c.upper() for c in update_columns]

        tmp_table = f"{table.upper()}_TMP"

        write_pandas(
            self._conn,
            df,
            tmp_table,
            auto_create_table=True,
            overwrite=True,
            table_type="TEMPORARY",
        )

        join_condition  = " AND ".join(
            [f"target.{c} = source.{c}" for c in conflict_columns_upper]
        )
        update_clause   = ", ".join(
            [f"target.{c} = source.{c}" for c in update_columns]
        )
        all_cols        = ", ".join(df.columns)
        source_cols     = ", ".join([f"source.{c}" for c in df.columns])

        merge_sql = f"""
            MERGE INTO {table.upper()} AS target
            USING {tmp_table} AS source
            ON {join_condition}
            WHEN MATCHED THEN
                UPDATE SET {update_clause}
            WHEN NOT MATCHED THEN
                INSERT ({all_cols})
                VALUES ({source_cols})
        """

        self._conn.cursor().execute(merge_sql)
        logger.info(f"Upserted {len(df)} rows into {table.upper()}")

    def delete_rows(self, table: str, where: str, params: tuple):
        """
        Delete rows matching a condition.

        Example:
            db.delete_rows("players", "team_id = %s", (726228,))
        """
        sql = f"DELETE FROM {table.upper()} WHERE {where}"
        self._conn.cursor().execute(sql, params)
        self.commit()
        logger.info(f"Deleted rows from {table.upper()} WHERE {where} — params: {params}")

    # -----------------------------------------------------------------------
    # Read operations
    # -----------------------------------------------------------------------

    def query(self, sql_str: str, params: Optional[tuple] = None) -> pd.DataFrame:
        """
        Run a SELECT query and return results as a DataFrame.

        Example:
            df = db.query("SELECT * FROM players WHERE team_id = %s", (726228,))
        """
        cursor = self._conn.cursor()
        cursor.execute(sql_str, params)
        cols = [desc[0].lower() for desc in cursor.description]
        rows = cursor.fetchall()
        return pd.DataFrame(rows, columns=cols)

    def table_exists(self, table: str) -> bool:
        """Check whether a table exists in the current database/schema."""
        result = self.query(
            "SELECT COUNT(*) AS cnt FROM information_schema.tables "
            "WHERE table_name = %s",
            (table.upper(),),
        )
        return result.iloc[0, 0] > 0

    def get_existing_ids(self, table: str, id_column: str) -> set:
        """
        Fetch the set of existing IDs from a table.
        Use this before your file loop to skip already-ingested records.

        Example:
            ingested = db.get_existing_ids("matches", "match_id")
            new_files = [f for f in files if extract_match_id(f) not in ingested]
        """
        df = self.query(f"SELECT {id_column.upper()} FROM {table.upper()}")
        return set(df[id_column.lower()].tolist())

    # -----------------------------------------------------------------------
    # Dynamic table creation from DataFrames
    # -----------------------------------------------------------------------

    def create_table_from_df(self, df: pd.DataFrame, table: str):
        """
        Dynamically creates a Snowflake table based on DataFrame column names and dtypes.
        Skips creation if the table already exists.
        """
        
        # Mapping from pandas dtypes to Snowflake types
        dtype_map = {
            "int64":   "INT",
            "int32":   "INT",
            "float64": "FLOAT",
            "float32": "FLOAT",
            "bool":    "BOOLEAN",
            "object":  "VARCHAR",
            "datetime64[ns]": "TIMESTAMP",
        }

        columns = []
        for col, dtype in zip(df.columns, df.dtypes):
            sf_type = dtype_map.get(str(dtype), "VARIANT")  # default to VARIANT for unknown/nested
            columns.append(f"{col.upper()} {sf_type}")

        columns_sql = ",\n    ".join(columns)
        sql = f"CREATE TABLE IF NOT EXISTS {table.upper()} (\n    {columns_sql}\n)"

        self.execute(sql)
        logger.info(f"Table {table.upper()} created or already exists")

    # -----------------------------------------------------------------------
    # Utility
    # -----------------------------------------------------------------------

    def execute(self, sql_str: str, params: Optional[tuple] = None):
        """
        Run an arbitrary SQL statement (DDL, TRUNCATE, etc.).

        Example:
            db.execute("TRUNCATE TABLE match_performances")
        """
        self._conn.cursor().execute(sql_str, params)
        self.commit()

    