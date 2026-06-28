/*
Test: Channel types are valid.
*/
SELECT
    channel_key,
    channel_type
FROM {{ ref('dim_channels') }}
WHERE channel_type NOT IN ('Medical', 'Pharmaceutical', 'Cosmetics', 'Other')