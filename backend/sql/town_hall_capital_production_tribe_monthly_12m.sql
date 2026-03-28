-- Capital production tribe: delivered units and ISK estimates by calendar month, last 12 months.
-- Roster + orders tagged to `Capital Production` under tribe slug `industry`.
-- “Delivered” timestamp: COALESCE(assignment.delivered_at, order.fulfilled_at).
-- See town_hall_capital_production_tribe_30d.sql for committed/delivered definitions.
WITH params AS (
    SELECT 'industry' AS tribe_slug,
        'Capital Production' AS tribe_group_name
),
roster AS (
    SELECT DISTINCT ec.id AS character_pk
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
)
SELECT
    DATE_FORMAT(
        COALESCE(a.delivered_at, o.fulfilled_at),
        '%Y-%m'
    ) AS report_month,
    SUM(a.quantity) AS total_delivered_units,
    SUM(
        a.quantity * COALESCE(
            a.target_estimated_margin,
            i.target_estimated_margin,
            0
        )
    ) AS total_isk_margin_estimate,
    SUM(
        a.quantity * COALESCE(
            a.target_unit_price,
            i.target_unit_price,
            0
        )
    ) AS total_isk_order_value_estimate
FROM roster r
INNER JOIN industry_industryorderitemassignment a ON a.character_id = r.character_pk
INNER JOIN industry_industryorderitem i ON i.id = a.order_item_id
INNER JOIN industry_industryorder o ON o.id = i.order_id
    AND (a.delivered_at IS NOT NULL OR o.fulfilled_at IS NOT NULL)
    AND COALESCE(a.delivered_at, o.fulfilled_at) >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)
INNER JOIN industry_industryorder_tribe_groups oxt ON oxt.industryorder_id = o.id
INNER JOIN tribes_tribegroup tg2 ON tg2.id = oxt.tribegroup_id
    AND tg2.is_active = 1
    AND tg2.name = (SELECT tribe_group_name FROM params)
INNER JOIN tribes_tribe t2 ON t2.id = tg2.tribe_id
    AND t2.is_active = 1
    AND t2.slug = (SELECT tribe_slug FROM params)
GROUP BY DATE_FORMAT(COALESCE(a.delivered_at, o.fulfilled_at), '%Y-%m')
ORDER BY report_month;
