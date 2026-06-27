"""
Telegram Medical Channel Scraper
Extracts messages, downloads images, and stores data in a data lake.

Requirements:
- Telethon library for Telegram API
- Python-dotenv for environment variables
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import dotenv
from telethon import TelegramClient, errors
from telethon.tl.types import Message, MessageMediaPhoto

# Load environment variables
dotenv.load_dotenv()

# ============================================
# IMAGE DOWNLOAD LIMIT PER CHANNEL (CHANGE THIS)
# ============================================
MAX_IMAGES_PER_CHANNEL = 150  # Set to 0 for unlimited

# ============================================
# LOGGING SETUP
# ============================================
LOG_DIR = Path("./logs")
LOG_DIR.mkdir(exist_ok=True)

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# File handler - logs to a dated file
log_file = LOG_DIR / f"scraper_{datetime.now().strftime('%Y%m%d')}.log"
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.INFO)

# Console handler - shows output in terminal
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Format for logs
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)


# ============================================
# TELEGRAM SCRAPER CLASS
# ============================================
class TelegramScraper:
    """
    Scrapes messages and images from public Telegram channels.

    Features:
    - Extracts message ID, date, text, views, forwards, media info
    - Downloads images to organized folders
    - Stores data in partitioned JSON files
    - Comprehensive logging
    """

    def __init__(
        self,
        api_id: int,
        api_hash: str,
        channels: List[str],
        data_dir: str = "./data/raw",
        limit: int = 1000,
    ):
        """
        Initialize the scraper.

        Args:
            api_id: Telegram API ID (from my.telegram.org)
            api_hash: Telegram API hash (from my.telegram.org)
            channels: List of channel usernames to scrape
            data_dir: Root directory for storing data
            limit: Maximum messages per channel
        """
        self.api_id = api_id
        self.api_hash = api_hash
        self.channels = channels
        self.limit = limit

        # Set up directory structure
        self.data_dir = Path(data_dir)
        self.messages_dir = self.data_dir / "telegram_messages"
        self.images_dir = self.data_dir / "images"

        # Create directories
        self.messages_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)

        # Initialize Telegram client
        self.client = TelegramClient(
            "scraper_session", self.api_id, self.api_hash  # Session file name
        )

        # Track statistics
        self.stats = {
            "channels_scraped": 0,
            "total_messages": 0,
            "total_images": 0,
            "errors": [],
        }

        # ============================================
        # PER-CHANNEL IMAGE TRACKING (ADD THIS)
        # ============================================
        self.images_per_channel = {}

    # ============================================
    # CONNECTION METHODS
    # ============================================
    async def connect(self) -> None:
        """Connect to Telegram API and authenticate."""
        try:
            await self.client.connect()
            if not await self.client.is_user_authorized():
                logger.info("First time running. Please authenticate...")
                await self.client.start()
                logger.info("Authentication successful!")
            else:
                logger.info("Already authenticated.")
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect from Telegram API."""
        await self.client.disconnect()
        logger.info("Disconnected from Telegram.")

    # ============================================
    # SCRAPING METHODS
    # ============================================
    async def scrape_channel(self, channel: str) -> List[Dict[str, Any]]:
        """
        Scrape all messages from a single channel.

        Args:
            channel: Channel username (e.g., "CheMed")

        Returns:
            List of message dictionaries
        """
        messages = []
        date_str = datetime.now().strftime("%Y-%m-%d")

        try:
            logger.info(f" Scraping channel: {channel}")

            # Get the channel entity
            entity = await self.client.get_entity(channel)
            channel_title = entity.title if hasattr(entity, "title") else channel

            # Iterate through messages
            async for msg in self.client.iter_messages(entity, limit=self.limit):
                # Extract message data
                msg_data = {
                    "message_id": msg.id,
                    "channel_username": channel,
                    "channel_name": channel_title,
                    "message_date": msg.date.isoformat() if msg.date else None,
                    "message_text": msg.text or "",
                    "views": getattr(msg, "views", 0),
                    "forwards": getattr(msg, "forwards", 0),
                    "has_media": bool(msg.media),
                    "media_type": (
                        self._get_media_type(msg.media) if msg.media else None
                    ),
                    "image_path": None,
                    "message_url": f"https://t.me/{channel}/{msg.id}",
                    # Preserve original API data
                    "raw_data": {
                        "id": msg.id,
                        "date": str(msg.date) if msg.date else None,
                        "text": msg.text,
                        "media": str(msg.media) if msg.media else None,
                    },
                }

                # Download image if present
                if msg.media and isinstance(msg.media, MessageMediaPhoto):
                    image_path = await self._download_image(msg, channel)
                    if image_path:
                        msg_data["image_path"] = str(image_path)
                        self.stats["total_images"] += 1

                messages.append(msg_data)

                # Log progress
                if len(messages) % 100 == 0:
                    logger.info(f"  Scraped {len(messages)} messages from {channel}")

                # Rate limiting - be nice to Telegram
                await asyncio.sleep(0.5)

            logger.info(f" Scraped {len(messages)} messages from {channel}")

            # Save to JSON file
            if messages:
                self._save_messages(messages, channel, date_str)
                self.stats["channels_scraped"] += 1
                self.stats["total_messages"] += len(messages)

        except errors.FloodWaitError as e:
            logger.warning(f"Rate limited on {channel}. Waiting {e.seconds}s...")
            await asyncio.sleep(e.seconds)
            # Retry after waiting
            return await self.scrape_channel(channel)

        except Exception as e:
            error_msg = f"Error scraping {channel}: {str(e)}"
            logger.error(error_msg)
            self.stats["errors"].append(error_msg)

        return messages

    def _get_media_type(self, media) -> Optional[str]:
        """Determine the type of media in a message."""
        if isinstance(media, MessageMediaPhoto):
            return "photo"
        return "other" if media else None

    # ============================================
    # IMAGE DOWNLOAD (PER-CHANNEL LIMIT)
    # ============================================
    async def _download_image(self, message: Message, channel: str) -> Optional[Path]:
        """
        Download image from a message with per-channel limit.

        Args:
            message: Telegram message object
            channel: Channel username

        Returns:
            Path to downloaded image or None if failed
        """
        try:
            # ============================================
            # PER-CHANNEL LIMIT CHECK
            # ============================================
            # Initialize channel count if not exists
            if channel not in self.images_per_channel:
                self.images_per_channel[channel] = 0

            # Check per-channel limit
            if (
                MAX_IMAGES_PER_CHANNEL > 0
                and self.images_per_channel[channel] >= MAX_IMAGES_PER_CHANNEL
            ):
                logger.info(f" Reached limit ({MAX_IMAGES_PER_CHANNEL}) for {channel}")
                return None

            # Create channel directory
            channel_dir = self.images_dir / channel
            channel_dir.mkdir(exist_ok=True)

            # Define image path: data/raw/images/{channel}/{message_id}.jpg
            image_path = channel_dir / f"{message.id}.jpg"

            # Skip if already exists
            if image_path.exists():
                logger.debug(f"Image already exists: {image_path}")
                return image_path

            # Download the image
            logger.debug(f"Downloading image: {image_path}")
            downloaded = await self.client.download_media(
                message.media, str(image_path)
            )

            if downloaded:
                logger.info(f" Downloaded: {image_path}")
                # ============================================
                # INCREMENT PER-CHANNEL COUNTER
                # ============================================
                self.images_per_channel[channel] += 1
                return image_path
            else:
                logger.warning(f"Failed to download image for message {message.id}")
                return None

        except Exception as e:
            logger.error(f"Error downloading image for {message.id}: {e}")
            return None

    # ============================================
    # DATA STORAGE
    # ============================================
    def _save_messages(self, messages: List[Dict], channel: str, date: str) -> None:
        """
        Save messages to a partitioned JSON file.
        Structure: data/raw/telegram_messages/YYYY-MM-DD/channel.json
        """
        # Create date partition directory
        date_dir = self.messages_dir / date
        date_dir.mkdir(exist_ok=True)

        # Save individual channel file
        file_path = date_dir / f"{channel}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "channel": channel,
                    "scrape_date": date,
                    "message_count": len(messages),
                    "messages": messages,
                },
                f,
                indent=2,
                ensure_ascii=False,
            )

        logger.info(f" Saved to: {file_path}")

        # Also append to daily combined file
        self._append_to_combined(messages, channel, date)

    def _append_to_combined(
        self, messages: List[Dict], channel: str, date: str
    ) -> None:
        """Append to a combined daily file for easier access."""
        combined_path = self.messages_dir / f"{date}_all_channels.json"

        # Load existing data if file exists
        if combined_path.exists():
            with open(combined_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {"date": date, "channels": {}}

        # Add/update channel data
        data["channels"][channel] = {
            "scrape_date": date,
            "message_count": len(messages),
            "messages": messages,
        }

        # Save back
        with open(combined_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # ============================================
    # MAIN SCRAPING METHOD
    # ============================================
    async def scrape_all(self) -> Dict[str, Any]:
        """
        Scrape all configured channels.

        Returns:
            Dictionary with scraping statistics
        """
        logger.info("=" * 60)
        logger.info(" STARTING TELEGRAM SCRAPER")
        logger.info(f" Channels: {', '.join(self.channels)}")
        logger.info(f" Limit per channel: {self.limit}")
        if MAX_IMAGES_PER_CHANNEL > 0:
            logger.info(f"  Max images per channel: {MAX_IMAGES_PER_CHANNEL}")
        else:
            logger.info(" Images: Unlimited")
        logger.info("=" * 60)

        start_time = datetime.now()

        # Scrape each channel
        for channel in self.channels:
            await self.scrape_channel(channel)

        # Calculate duration
        duration = (datetime.now() - start_time).total_seconds()

        # Save summary
        summary = {
            "scrape_date": datetime.now().isoformat(),
            "duration_seconds": duration,
            "channels": self.channels,
            "channels_scraped": self.stats["channels_scraped"],
            "total_messages": self.stats["total_messages"],
            "total_images": self.stats["total_images"],
            "images_per_channel": self.images_per_channel,
            "max_images_per_channel": MAX_IMAGES_PER_CHANNEL,
            "errors": self.stats["errors"],
        }

        # Save summary to file
        summary_path = (
            self.messages_dir
            / f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        # Log summary
        logger.info("=" * 60)
        logger.info(" SCRAPING COMPLETE")
        logger.info(
            f" Channels scraped: {self.stats['channels_scraped']}/{len(self.channels)}"
        )
        logger.info(f" Total messages: {self.stats['total_messages']}")
        logger.info(f"  Total images: {self.stats['total_images']}")
        if MAX_IMAGES_PER_CHANNEL > 0:
            logger.info(f"  Max per channel: {MAX_IMAGES_PER_CHANNEL}")
        logger.info(f" Duration: {duration:.1f} seconds")

        # Show per-channel image counts
        if self.images_per_channel:
            logger.info("  Images per channel:")
            for channel, count in self.images_per_channel.items():
                logger.info(f"    - {channel}: {count}")

        if self.stats["errors"]:
            logger.warning(f" {len(self.stats['errors'])} errors occurred")
            for error in self.stats["errors"]:
                logger.warning(f"  - {error}")

        logger.info(f"  Summary saved to: {summary_path}")
        logger.info("=" * 60)

        return summary


# ============================================
# MAIN ENTRY POINT
# ============================================
async def main():
    """Run the scraper."""
    # Load credentials from environment
    api_id = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")

    if not api_id or not api_hash:
        logger.error(
            " Missing credentials! Set TELEGRAM_API_ID and TELEGRAM_API_HASH in .env"
        )
        return

    # Define channels to scrape
    channels = ["CheMed123", "tikvahpharma", "lobelia4cosmetics", "Thequorachannel"]

    # Create scraper instance
    scraper = TelegramScraper(
        api_id=int(api_id),
        api_hash=api_hash,
        channels=channels,
        data_dir="./data/raw",
        limit=1000,
    )

    try:
        # Connect and scrape
        await scraper.connect()

    except Exception as e:
        logger.error(f" Scraping failed: {e}")
        raise
    finally:
        await scraper.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
