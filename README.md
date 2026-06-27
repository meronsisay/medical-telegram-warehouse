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
├── api/ # FastAPI application
├── scripts/ # Utility scripts
├── .env # Environment variables
├── requirements.txt # Python dependencies
└── README.md
```


## Setup Instructions

### 1. Prerequisites

- Python 3.11+
- Telegram API credentials ([my.telegram.org](https://my.telegram.org))
- PostgreSQL (for later tasks)

### 2. Clone and Setup

```bash
# Clone repository
git clone https://github.com/yourusername/medical-telegram-warehouse.git
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

# run
python src/scraper.py
