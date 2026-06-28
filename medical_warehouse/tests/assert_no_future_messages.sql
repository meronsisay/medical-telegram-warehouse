/*
Test: No messages from the future.
*/
SELECT
    message_id,
    message_date
FROM {{ ref('stg_telegram_messages') }}
WHERE message_date > CURRENT_TIMESTAMP