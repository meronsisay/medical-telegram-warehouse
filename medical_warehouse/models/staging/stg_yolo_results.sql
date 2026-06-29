/*
Staging model for YOLO image detection results.
Cleans and aggregates YOLO data for the star schema.
*/

WITH summary AS (
    SELECT
        message_id,
        channel_username,
        image_path,
        image_category,
        total_objects
    FROM {{ source('raw', 'yolo_results_summary') }}
),

detailed AS (
    SELECT
        message_id,
        detected_class,
        confidence_score
    FROM {{ source('raw', 'yolo_results_detailed') }}
    WHERE detected_class != 'none'
),

aggregated AS (
    SELECT
        s.message_id,
        s.channel_username,
        s.image_path,
        s.image_category,
        s.total_objects,
        -- Get the most confident detection
        FIRST_VALUE(d.detected_class) OVER (
            PARTITION BY s.message_id 
            ORDER BY d.confidence_score DESC
        ) AS top_detected_class,
        FIRST_VALUE(d.confidence_score) OVER (
            PARTITION BY s.message_id 
            ORDER BY d.confidence_score DESC
        ) AS top_confidence,
        -- Count unique classes detected
        COUNT(DISTINCT d.detected_class) AS unique_classes_detected,
        -- Average confidence - cast to numeric for proper rounding
        COALESCE(AVG(d.confidence_score)::numeric, 0) AS avg_confidence
    FROM summary s
    LEFT JOIN detailed d ON s.message_id = d.message_id
    GROUP BY 
        s.message_id, 
        s.channel_username, 
        s.image_path, 
        s.image_category, 
        s.total_objects,
        d.detected_class,
        d.confidence_score
)

SELECT DISTINCT
    message_id,
    channel_username,
    image_path,
    image_category,
    total_objects,
    unique_classes_detected,
    -- Round with proper numeric casting
    ROUND(avg_confidence, 4) AS avg_confidence,
    top_detected_class,
    ROUND(top_confidence::numeric, 4) AS top_confidence,
    -- Create category flags
    CASE WHEN image_category = 'promotional' THEN 1 ELSE 0 END AS is_promotional,
    CASE WHEN image_category = 'product_display' THEN 1 ELSE 0 END AS is_product_display,
    CASE WHEN image_category = 'lifestyle' THEN 1 ELSE 0 END AS is_lifestyle,
    CASE WHEN image_category = 'other' THEN 1 ELSE 0 END AS is_other
FROM aggregated