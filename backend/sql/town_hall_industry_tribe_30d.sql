-- Industry (order tool): by roster user — primary name, char count, delivered units,
-- estimated margin ISK and order-value ISK (qty × per-unit targets; 30d; edit params).
-- Orders must be tagged via industry_industryorder_tribe_groups to the tribe group in params.
WITH params AS (
    SELECT 'industry' AS tribe_slug,
        'Subcapital' AS tribe_group_name
),
roster AS (
    SELECT DISTINCT
        ec.id AS character_pk,
        ec.character_id AS eve_character_id,
        ec.character_name,
        tgm.user_id
    FROM tribes_tribegroupmembershipcharacter tgmcc
    INNER JOIN tribes_tribegroupmembership tgm
        ON tgm.id = tgmcc.membership_id
        AND tgm.status = 'active'
    INNER JOIN tribes_tribegroup tg
        ON tg.id = tgm.tribe_group_id
        AND tg.is_active = 1
        AND tg.name = (SELECT tribe_group_name FROM params)
    INNER JOIN tribes_tribe t
        ON t.id = tg.tribe_id
        AND t.is_active = 1
        AND t.slug = (SELECT tribe_slug FROM params)
    INNER JOIN eveonline_evecharacter ec ON ec.id = tgmcc.character_id
        AND ec.user_id = tgm.user_id
        AND ec.user_id IS NOT NULL
),
deliveries_by_user AS (
    SELECT
        r.user_id,
        SUM(a.quantity) AS delivered_units,
        SUM(
            a.quantity * COALESCE(
                a.target_estimated_margin,
                i.target_estimated_margin,
                0
            )
        ) AS isk_margin_estimate,
        SUM(
            a.quantity * COALESCE(
                a.target_unit_price,
                i.target_unit_price,
                0
            )
        ) AS isk_order_value_estimate
    FROM industry_industryorderitemassignment a
    INNER JOIN industry_industryorderitem i ON i.id = a.order_item_id
    INNER JOIN industry_industryorder o ON o.id = i.order_id
    INNER JOIN industry_industryorder_tribe_groups oxt ON oxt.industryorder_id = o.id
    INNER JOIN tribes_tribegroup tg2 ON tg2.id = oxt.tribegroup_id
        AND tg2.is_active = 1
        AND tg2.name = (SELECT tribe_group_name FROM params)
    INNER JOIN tribes_tribe t2 ON t2.id = tg2.tribe_id
        AND t2.is_active = 1
        AND t2.slug = (SELECT tribe_slug FROM params)
    INNER JOIN roster r ON r.character_pk = a.character_id
    WHERE a.delivered_at IS NOT NULL
        AND a.delivered_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
    GROUP BY r.user_id
)
SELECT
    COALESCE(MAX(pc.character_name), MAX(r.character_name), '') AS primary_character_name,
    COUNT(DISTINCT r.character_pk) AS number_of_characters,
    COALESCE(MAX(d.delivered_units), 0) AS delivered_units,
    COALESCE(MAX(d.isk_margin_estimate), 0) AS isk_margin_estimate,
    COALESCE(MAX(d.isk_order_value_estimate), 0) AS isk_order_value_estimate
FROM roster r
LEFT JOIN deliveries_by_user d ON d.user_id = r.user_id
LEFT JOIN eveonline_eveplayer ep ON ep.user_id = r.user_id
LEFT JOIN eveonline_evecharacter pc ON pc.id = ep.primary_character_id
GROUP BY r.user_id
ORDER BY isk_margin_estimate DESC;
