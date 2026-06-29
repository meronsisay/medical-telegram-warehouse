/*
Fact table for YOLO image detection results.
Links image analysis to messages.
*/

WITH image_detections AS (
    SELECT
        message_id,
        channel_username,
        image_category,
        total_objects,
        is_promotional,
        is_product_display,
        is_lifestyle,
        is_other,
        unique_classes_detected,
        avg_confidence,
        top_detected_class,
        top_confidence
    FROM {{ ref('stg_yolo_results') }}
)

SELECT
    id.message_id,
    f.channel_key,
    f.date_key,
    f.view_count,
    f.has_image,
    id.image_category,
    id.total_objects,
    id.is_promotional,
    id.is_product_display,
    id.is_lifestyle,
    id.is_other,
    id.unique_classes_detected,
    id.avg_confidence,
    id.top_detected_class,
    id.top_confidence,
    -- Classification for quick filtering
    CASE 
        WHEN id.is_promotional = 1 THEN 'Promotional (Person + Product)'
        WHEN id.is_product_display = 1 THEN 'Product Display'
        WHEN id.is_lifestyle = 1 THEN 'Lifestyle (Person only)'
        WHEN id.is_other = 1 THEN 'Other'
        ELSE 'Uncategorized'
    END AS image_category_label
FROM image_detections id
LEFT JOIN {{ ref('fct_messages') }} f
    ON id.message_id = f.message_id
WHERE f.message_id IS NOT NULL