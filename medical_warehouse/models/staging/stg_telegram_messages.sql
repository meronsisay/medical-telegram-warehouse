/*
Staging model for telegram messages.
Cleans and standardizes raw data.
*/

WITH source AS (
    SELECT
        message_id,
        channel_username,
        channel_name,
        message_date,
        message_text,
        views,
        forwards,
        has_media,
        media_type,
        image_path,
        message_url,
        raw_data
    FROM raw.telegram_messages
),

cleaned AS (
    SELECT
        message_id,
        channel_username,
        channel_name,
        message_date::TIMESTAMP AS message_date,
        COALESCE(TRIM(message_text), '') AS message_text,
        COALESCE(views, 0) AS views,
        COALESCE(forwards, 0) AS forwards,
        has_media,
        media_type,
        image_path,
        message_url,
        LENGTH(COALESCE(TRIM(message_text), '')) AS message_length,
        has_media AS has_image,
        raw_data
    FROM source
    WHERE message_text IS NOT NULL 
      AND message_text != ''
      -- Filter out Terms of Service violation messages
      AND message_text NOT LIKE '%violated Telegram%Terms of Service%'
      AND message_text NOT LIKE '%can’t be displayed%'
)

SELECT 
    message_id,
    channel_username,
    channel_name,
    message_date,
    message_text,
    views,
    forwards,
    has_media,
    media_type,
    image_path,
    message_url,
    message_length,
    has_image,
    raw_data
FROM cleaned