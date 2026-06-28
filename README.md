# Medical Telegram Data Warehouse

An end-to-end data pipeline for Ethiopian medical Telegram channels using ELT architecture.

## Project Overview

This project builds a data platform that scrapes, stores, and analyzes data from public Telegram channels selling medical and pharmaceutical products in Ethiopia.

**Key Features:**
- Automated Telegram scraping with Telethon
- Data lake storage with date-partitioned JSON files
- Image download and organization
- Comprehensive logging and error handling
- Per-channel image download limits


## Project Structure
```
medical-telegram-warehouse/
├── src/
│ └── scraper.py # Telegram scraper
├── data/
│ └── raw/
│ ├── telegram_messages/ # JSON files by date/channel
│ └── images/ # Downloaded images by channel
├── logs/
│ └── scraper_*.log # Scraping logs
├── tests/
│ └── test_scraper.py # Unit tests
├── medical_warehouse/ # dbt project
│ ├── models/
│ │ ├── staging/ # Cleaned data models
│ │ └── marts/ # Star schema (dimensions + facts)
│ └── tests/ # Custom data tests
├── api/ # FastAPI application
├── scripts/
│ ├── load_data_lake_to_postgres.py # Load data lake to PostgreSQL
├── .env # Environment variables
├── docker-compose.yml # Container orchestration
├── requirements.txt # Python dependencies
└── README.md

text
```

## Data Pipeline Results

### Data Scraping and Collection 

**Scraped Channels:**
- CheMed (Medical)
- Lobelia Cosmetics (Cosmetics)
- Tikvah Pharma (Pharmaceutical)
- Doctors Online (Other)

**Data Collected:**
- **Total messages:** 3,076 messages
- **Channels:** 4 channels
- **Images:** Downloaded per channel limit (150 images/channel)

**Fields Extracted:**
- message_id, date, text, views, forwards, media info
- Images downloaded to: `data/raw/images/{channel}/{message_id}.jpg`
- Raw JSON stored in: `data/raw/telegram_messages/YYYY-MM-DD/channel.json`

**Data Quality:**
- Invalid messages filtered (TOS violations, empty messages)
- Per-channel image limit: 150 images
- Comprehensive logging implemented

---

### Data Modeling and Transformation 

**ETL Process:**
1. Raw data loaded to PostgreSQL `raw.telegram_messages`
2. dbt staging cleaned and validated data
3. Star schema built in dbt marts

**Star Schema Results:**

| Table | Description | Row Count |
|-------|-------------|-----------|
| `dim_channels` | Channel metadata with type classification | 4 |
| `dim_dates` | Date attributes (day, month, year, weekend) | 198 |
| `fct_messages` | Message metrics linked to dimensions | 2,420 |

**Data Classification:**
- **Channel Types:** Medical, Pharmaceutical, Cosmetic, Other
- **Date Range:** 198 unique dates with full calendar attributes
- **Messages Ready for Analytics:** 2,420

**Data Quality Tests:**
-  19/19 tests passing
- Unique and not-null constraints
- Relationship validations
- Custom tests: no future messages, positive views, valid channel types
---

## Setup Instructions

### 1. Prerequisites

- Python 3.11+
- Docker Desktop (for PostgreSQL)
- Telegram API credentials ([my.telegram.org](https://my.telegram.org))

### 2. Clone and Setup

```bash
# Clone repository
git clone https://github.com/meronsisay/medical-telegram-warehouse.git
cd medical-telegram-warehouse

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# 3. Configure Environment
# create .env file 
  # Telegram API
  - API_ID=your_api_id
  - API_HASH=your_api_hash

  # PostgreSQL (for Docker)
  - DB_HOST=localhost
  - DB_PORT=5432
  - DB_NAME=telegram_warehouse
  - DB_USER=postgres
  - DB_PASSWORD=postgres

# Start PostgreSQL with Docker
docker-compose up -d postgres

# Scrape Telegram channels
python src/scraper.py

# Load data from data lake to PostgreSQL
python scripts/load_to_postgres.py

# Run dbt transformations
cd medical_warehouse
dbt run
dbt test

# Generate documentation
dbt docs generate
dbt docs serve