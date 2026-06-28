/*
Dimension table for channels.
*/

WITH channel_stats AS (
    SELECT
        channel_username,
        channel_name,
        MIN(message_date) AS first_post_date,
        MAX(message_date) AS last_post_date,
        COUNT(*) AS total_posts,
        AVG(views) AS avg_views,
        CASE
            WHEN LOWER(channel_name) LIKE '%chemed%' 
              OR LOWER(channel_username) LIKE '%chemed%'
             THEN 'Medical'
            WHEN LOWER(channel_name) LIKE '%pharma%' 
              OR LOWER(channel_username) LIKE '%pharma%'
             THEN 'Pharmaceutical'
            WHEN LOWER(channel_name) LIKE '%lobelia%' 
              OR LOWER(channel_username) LIKE '%lobelia%'
             THEN 'Cosmetics'
            ELSE 'Other'
        END AS channel_type
    FROM {{ ref('stg_telegram_messages') }}
    GROUP BY 1, 2
)

SELECT
    ROW_NUMBER() OVER (ORDER BY channel_username) AS channel_key,
    channel_username,
    channel_name,
    channel_type,
    first_post_date,
    last_post_date,
    total_posts,
    avg_views
FROM channel_stats