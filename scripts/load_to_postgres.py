"""
Load data from data lake (JSON) into PostgreSQL raw schema.
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

import psycopg2
from psycopg2.extras import execute_values
import dotenv

dotenv.load_dotenv()


class DataLakeLoader:
    """Load data from data lake to PostgreSQL."""

    def __init__(self):
        """Initialize database connection."""
        self.conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5433"),
            dbname=os.getenv("DB_NAME", "telegram_warehouse"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "postgres")
        )
        self.conn.autocommit = False
        self.cursor = self.conn.cursor()

    def create_raw_table(self):
        """Create raw.telegram_messages table if not exists."""
        print("Creating raw table...")

        self.cursor.execute("""
            CREATE SCHEMA IF NOT EXISTS raw;

            CREATE TABLE IF NOT EXISTS raw.telegram_messages (
                message_id BIGINT PRIMARY KEY,
                channel_username VARCHAR(100),
                channel_name VARCHAR(200),
                message_date TIMESTAMP,
                message_text TEXT,
                views INTEGER,
                forwards INTEGER,
                has_media BOOLEAN,
                media_type VARCHAR(50),
                image_path VARCHAR(500),
                message_url VARCHAR(500),
                raw_data JSONB,
                loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data_lake_path VARCHAR(500)
            );

            CREATE INDEX IF NOT EXISTS idx_raw_channel 
                ON raw.telegram_messages(channel_username);
            CREATE INDEX IF NOT EXISTS idx_raw_date 
                ON raw.telegram_messages(message_date);
        """)
        self.conn.commit()
        print(" Raw table created")

    def load_from_data_lake(self, data_lake_dir: str = "./data/raw"):
        """Load data from data lake to PostgreSQL."""
        data_lake = Path(data_lake_dir)
        messages_lake = data_lake / "telegram_messages"

        if not messages_lake.exists():
            print(f"Data lake not found at {messages_lake}")
            return

        print(f"Reading from data lake: {messages_lake}")

        # Get all JSON files (excluding summary files)
        json_files = list(messages_lake.glob("**/*.json"))
        json_files = [
            f for f in json_files 
            if "summary" not in f.name and "all_channels" not in f.name
        ]

        if not json_files:
            print(" No data lake files found!")
            return

        total_loaded = 0

        for file_path in json_files:
            print(f"\nProcessing: {file_path}")

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                if 'messages' not in data:
                    continue

                messages = data['messages']
                channel = data.get('channel', 'unknown')

                rows = []
                for msg in messages:
                    raw_data = msg.get('raw_data', {})
                    date_str = msg.get('message_date')
                    if date_str:
                        try:
                            message_date = datetime.fromisoformat(
                                date_str.replace('Z', '+00:00')
                            )
                        except:
                            message_date = None
                    else:
                        message_date = None

                    rows.append((
                        msg.get('message_id'),
                        msg.get('channel_username', channel),
                        msg.get('channel_name', ''),
                        message_date,
                        msg.get('message_text', ''),
                        msg.get('views', 0),
                        msg.get('forwards', 0),
                        msg.get('has_media', False),
                        msg.get('media_type'),
                        msg.get('image_path'),
                        msg.get('message_url'),
                        json.dumps(raw_data),
                        str(file_path)
                    ))

                if rows:
                    execute_values(
                        self.cursor,
                        """
                        INSERT INTO raw.telegram_messages (
                            message_id, channel_username, channel_name,
                            message_date, message_text, views, forwards,
                            has_media, media_type, image_path, message_url,
                            raw_data, data_lake_path
                        )
                        VALUES %s
                        ON CONFLICT (message_id) DO UPDATE SET
                            views = EXCLUDED.views,
                            forwards = EXCLUDED.forwards,
                            loaded_at = CURRENT_TIMESTAMP
                        """,
                        rows,
                        page_size=1000
                    )

                    self.conn.commit()
                    total_loaded += len(rows)
                    print(f"   Loaded {len(rows)} messages")

            except Exception as e:
                print(f"  Error loading {file_path}: {e}")
                self.conn.rollback()

        print(f"\nTotal messages loaded: {total_loaded}")
        self.show_stats()

    def show_stats(self):
        """Show data lake statistics."""
        self.cursor.execute("""
            SELECT 
                COUNT(*) as total_messages,
                COUNT(DISTINCT channel_username) as total_channels,
                MIN(message_date) as earliest,
                MAX(message_date) as latest
            FROM raw.telegram_messages
        """)
        result = self.cursor.fetchone()
        print(f"\nPostgreSQL Raw Table Stats:")
        print(f"   Total messages: {result[0]:,}")
        print(f"   Channels: {result[1]}")
        print(f"   Date range: {result[2]} to {result[3]}")

    def close(self):
        """Close database connection."""
        self.cursor.close()
        self.conn.close()


def main():
    """Load data from data lake to PostgreSQL."""
    print("=" * 60)
    print(" DATA LAKE TO POSTGRESQL LOADER")
    print("=" * 60)

    loader = DataLakeLoader()

    try:
        loader.create_raw_table()
        loader.load_from_data_lake()
        print("\n Data lake loaded to PostgreSQL!")
    except Exception as e:
        print(f"Failed: {e}")
        raise
    finally:
        loader.close()


if __name__ == "__main__":
    main()
