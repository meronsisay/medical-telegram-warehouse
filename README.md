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
│ ├── scraper.py # Telegram scraper
│ ├── yolo_detect.py # YOLO object detection
│ └── pipeline.py # Dagster pipeline definition
├── data/
│ └── raw/
│ ├── telegram_messages/ # JSON files by date/channel
│ └── images/ # Downloaded images by channel
├── data/processed/yolo_results/ # YOLO detection results
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
│ ├── main.py # App setup
│ ├── database.py # Database connection
│ ├── schemas.py # Pydantic models
│ └── endpoints.py # API endpoints
├── scripts/
│ ├── load_to_postgres.py # Load data lake to PostgreSQL
│ └── load_yolo_to_postgres.py # Load YOLO results to PostgreSQL
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

### YOLO Image Analysis 

| Category | Count | Avg Views |
|----------|-------|-----------|
| **Promotional** (person + product) | 20 | **15,590** |
| Other | 306 | 9,690 |
| Lifestyle (person only) | 161 | 7,105 |
| Product Display | 313 | **595** |

**Key Insight:** Promotional posts get **26x more views** than product displays! 

**Channel Visual Strategy:**

| Channel | Strategy |
|---------|----------|
| Lobelia | Product-focused (165 product shots) |
| tikva Pharma | Mixed (108 product + 54 lifestyle) |
| CheMed | People-focused (51 lifestyle) |
| Doctors Online | Promotional (10 promo images) |

###  Analytical API 
**Endpoints:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/reports/top-products` | GET | Most mentioned terms/products |
| `/api/channels/{name}/activity` | GET | Channel posting trends |
| `/api/search/messages` | GET | Search messages by keyword |
| `/api/reports/visual-content` | GET | Image usage statistics |
| `/api/channels` | GET | List all channels |

**API Documentation:** `http://localhost:8000/docs` (auto-generated OpenAPI)

---

### Pipeline Orchestration 

**Dagster Pipeline:**

| Step | Description |
|------|-------------|
| `scrape_telegram_data` | Scrape messages and images from Telegram |
| `load_raw_to_postgres` | Load raw data to PostgreSQL |
| `run_yolo_enrichment` | Run YOLO object detection |
| `run_dbt_transformations` | Execute dbt models |
| `notify_completion` | Log pipeline completion |

**Schedules:**
- **Daily:** Runs at 8:00 AM UTC
- **Weekly:** Full refresh every Sunday

**UI:** `http://localhost:3000` (Dagster dashboard)

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

# Run Pipeline

# Start PostgreSQL
docker-compose up -d postgres

# Option A: Run individual steps
python src/scraper.py
python scripts/load_to_postgres.py
python src/yolo_detect.py
python scripts/load_yolo_to_postgres.py
cd medical_warehouse && dbt run && dbt test

# Option B: Run automated pipeline with Dagster
dagster dev -f src/pipeline.py
# Open http://localhost:3000 and launch the job

# Start API
uvicorn api.main:app --reload --host localhost --port 8000