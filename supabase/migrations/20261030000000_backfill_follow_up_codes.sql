-- Give older follow-up records without a human-readable code a stable FU ID.
-- New records receive codes in create_follow_up().
-- Older check-ins were incorrectly marked Completed before physician review.
UPDATE public.follow_ups AS follow_up
SET status = 'Scheduled',
    updated_at = now()
FROM public.examinations AS examination
WHERE follow_up.follow_up_examination_id = examination.examination_id
  AND follow_up.status = 'Completed'
  AND examination.status IN ('Pending', 'In Progress', 'Awaiting X-Ray', 'X-Ray Ready');

WITH existing_max AS (
    SELECT
        substring(follow_up_code FROM '^FU-([0-9]{4})-') AS code_year,
        MAX(substring(follow_up_code FROM '^FU-[0-9]{4}-([0-9]+)$')::integer) AS max_number
    FROM public.follow_ups
    WHERE follow_up_code ~ '^FU-[0-9]{4}-[0-9]+$'
    GROUP BY 1
), missing AS (
    SELECT
        follow_up_id,
        EXTRACT(YEAR FROM created_at)::integer AS code_year,
        ROW_NUMBER() OVER (
            PARTITION BY EXTRACT(YEAR FROM created_at)
            ORDER BY created_at, follow_up_id
        ) AS row_number
    FROM public.follow_ups
    WHERE follow_up_code IS NULL OR btrim(follow_up_code) = ''
), assigned AS (
    SELECT
        missing.follow_up_id,
        'FU-' || missing.code_year::text || '-' ||
        LPAD((COALESCE(existing_max.max_number, 0) + missing.row_number)::text, 5, '0') AS follow_up_code
    FROM missing
    LEFT JOIN existing_max
        ON existing_max.code_year = missing.code_year::text
)
UPDATE public.follow_ups AS follow_up
SET follow_up_code = assigned.follow_up_code
FROM assigned
WHERE follow_up.follow_up_id = assigned.follow_up_id;
