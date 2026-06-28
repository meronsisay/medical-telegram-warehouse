/*
Test: All views are non-negative.
*/
SELECT
    message_id,
    views
FROM {{ ref('stg_telegram_messages') }}
WHERE views < 0