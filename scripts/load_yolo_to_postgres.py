"""
Load YOLO detection results from CSV files to PostgreSQL.
"""

import os
import pandas as pd
from sqlalchemy import create_engine, text
import dotenv

dotenv.load_dotenv()


class YOLOLoader:
    """Load YOLO results from CSV to PostgreSQL."""

    def __init__(self):
        """Initialize database connection."""
        self.engine = create_engine(
            f"postgresql://{os.getenv('DB_USER', 'postgres')}:{os.getenv('DB_PASSWORD', 'postgres')}"
            f"@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5433')}/{os.getenv('DB_NAME', 'telegram_warehouse')}"
        )
        print(" Database connection established")

    def create_yolo_tables(self):
        """Create YOLO result tables if they don't exist."""
        print(" Creating YOLO tables...")

        with self.engine.connect() as conn:
            # Create summary table
            conn.execute(text("""
                CREATE SCHEMA IF NOT EXISTS raw;

                CREATE TABLE IF NOT EXISTS raw.yolo_results_summary (
                    message_id BIGINT PRIMARY KEY,
                    channel_username VARCHAR(100),
                    image_path VARCHAR(500),
                    image_category VARCHAR(50),
                    total_objects INTEGER,
                    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_yolo_summary_channel 
                    ON raw.yolo_results_summary(channel_username);
                CREATE INDEX IF NOT EXISTS idx_yolo_summary_category 
                    ON raw.yolo_results_summary(image_category);
            """))

            # Create detailed table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS raw.yolo_results_detailed (
                    id SERIAL PRIMARY KEY,
                    message_id BIGINT,
                    detected_class VARCHAR(50),
                    confidence_score FLOAT,
                    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (message_id) REFERENCES raw.yolo_results_summary(message_id)
                );

                CREATE INDEX IF NOT EXISTS idx_yolo_detailed_message 
                    ON raw.yolo_results_detailed(message_id);
                CREATE INDEX IF NOT EXISTS idx_yolo_detailed_class 
                    ON raw.yolo_results_detailed(detected_class);
            """))

            conn.commit()
            print(" YOLO tables created")

    def load_summary(self, csv_path: str = "./data/processed/yolo_results/yolo_results.csv"):
        if not os.path.exists(csv_path):
            print(f" Summary CSV not found: {csv_path}")
            return 0

        df = pd.read_csv(csv_path)
        
        # Clear existing data manually while keeping the table structure and indexes intact
        with self.engine.connect() as conn:
            conn.execute(text("TRUNCATE TABLE raw.yolo_results_summary CASCADE;"))
            conn.commit()

        # Change to append
        df.to_sql(
            'yolo_results_summary',
            self.engine,
            schema='raw',
            if_exists='append',
            index=False
        )
        print(f" Loaded {len(df)} rows to raw.yolo_results_summary")
        return len(df)

    def load_detailed(self, csv_path: str = "./data/processed/yolo_results/detailed_yolo_results.csv"):
        """Load YOLO detailed detections to PostgreSQL."""
        if not os.path.exists(csv_path):
            print(f"   Detailed CSV not found: {csv_path}")
            print("Run src/yolo_detect.py first!")
            return 0

        print(f" Reading detailed from: {csv_path}")
        df = pd.read_csv(csv_path)
        print(f" Found {len(df)} individual detections")

        # --- FIX APPLIED HERE ---
        # Clear existing data manually using TRUNCATE CASCADE to protect downstream views
        with self.engine.connect() as conn:
            conn.execute(text("TRUNCATE TABLE raw.yolo_results_detailed CASCADE;"))
            conn.commit()

        # Switch 'replace' to 'append' so the structural framework isn't dropped
        df.to_sql(
            'yolo_results_detailed',
            self.engine,
            schema='raw',
            if_exists='append',
            index=False
        )
        # ------------------------

        print(f" Loaded {len(df)} rows to raw.yolo_results_detailed")
        return len(df)

    def verify_load(self):
        """Verify data was loaded correctly."""
        print("\n Verifying load...")

        with self.engine.connect() as conn:
            # Check summary count
            result = conn.execute(text("SELECT COUNT(*) FROM raw.yolo_results_summary"))
            summary_count = result.fetchone()[0]

            # Check detailed count
            result = conn.execute(text("SELECT COUNT(*) FROM raw.yolo_results_detailed"))
            detailed_count = result.fetchone()[0]

            # Check category distribution
            result = conn.execute(text("""
                SELECT 
                    image_category,
                    COUNT(*) as count
                FROM raw.yolo_results_summary
                GROUP BY image_category
                ORDER BY count DESC
            """))
            categories = result.fetchall()

            print(f"   Summary: {summary_count} rows")
            print(f"   Detailed: {detailed_count} rows")
            print("\n   Category Distribution:")
            for category, count in categories:
                print(f"      {category}: {count}")

            return summary_count, detailed_count

    def close(self):
        """Close connection."""
        self.engine.dispose()
        print(" Connection closed")


def main():
    """Load YOLO results to PostgreSQL."""
    print("=" * 60)
    print(" YOLO RESULTS TO POSTGRESQL LOADER")
    print("=" * 60)

    loader = YOLOLoader()

    try:
        # Create tables
        loader.create_yolo_tables()

        # Load data
        summary_count = loader.load_summary()
        detailed_count = loader.load_detailed()

        if summary_count > 0 and detailed_count > 0:
            # Verify
            loader.verify_load()
            print("\n YOLO results loaded to PostgreSQL successfully!")
        else:
            print("\n No data loaded. Make sure YOLO detection ran successfully.")

    except Exception as e:
        print(f" Failed to load YOLO results: {e}")
        raise
    finally:
        loader.close()


if __name__ == "__main__":
    main()
