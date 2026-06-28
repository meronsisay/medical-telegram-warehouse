/*
Fact table for messages.
*/

WITH messages AS (
    SELECT
        stg.message_id,
        stg.channel_username,
        stg.message_date,
        stg.message_text,
        stg.views,
        stg.forwards,
        stg.has_media,
        stg.image_path,
        stg.message_length,
        stg.has_image,
        channels.channel_key,
        dates.date_key
    FROM {{ ref('stg_telegram_messages') }} stg
    LEFT JOIN {{ ref('dim_channels') }} channels
        ON stg.channel_username = channels.channel_username
    LEFT JOIN {{ ref('dim_dates') }} dates
        ON DATE(stg.message_date) = dates.full_date
)

SELECT
    message_id,
    channel_key,
    date_key,
    message_text,
    message_length,
    views AS view_count,
    forwards AS forward_count,
    has_image,
    image_path,
    has_media AS has_media_flag
FROM messages