-- Capital production tribe (Industry order tool): roster users — primary character,
-- committed vs delivered units and ISK (qty × per-unit targets; 30d for delivered).
-- Tribe: slug `industry`, group `Capital Production`. Orders tagged via industry_industryorder_tribe_groups.
--
-- Committed: assignments on roster chars, tagged orders, order still open (fulfilled_at IS NULL).
-- Delivered: fulfillment in last 30 days — assignment.delivered_at if set, else order.fulfilled_at.
WITH params AS (
    SELECT 'industry' AS tribe_slug,
        'Capital Production' AS tribe_group_name
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
tagged_order_assignment AS (
    SELECT
        a.id AS assignment_id,
        a.character_id,
        a.quantity,
        COALESCE(a.target_unit_price, i.target_unit_price, 0) AS unit_price,
        COALESCE(a.target_estimated_margin, i.target_estimated_margin, 0) AS unit_margin,
        o.id AS order_id,
        o.fulfilled_at,
        a.delivered_at
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
),
committed_by_user AS (
    SELECT
        r.user_id,
        SUM(x.quantity) AS committed_units,
        SUM(x.quantity * x.unit_price) AS committed_estimate,
        SUM(x.quantity * x.unit_margin) AS committed_margin
    FROM tagged_order_assignment x
    INNER JOIN roster r ON r.character_pk = x.character_id
    WHERE x.fulfilled_at IS NULL
    GROUP BY r.user_id
),
delivered_by_user AS (
    SELECT
        r.user_id,
        SUM(x.quantity) AS delivered_units,
        SUM(x.quantity * x.unit_price) AS delivered_estimate,
        SUM(x.quantity * x.unit_margin) AS delivered_margin
    FROM tagged_order_assignment x
    INNER JOIN roster r ON r.character_pk = x.character_id
    WHERE (x.delivered_at IS NOT NULL OR x.fulfilled_at IS NOT NULL)
        AND COALESCE(x.delivered_at, x.fulfilled_at) >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
    GROUP BY r.user_id
)
SELECT
    COALESCE(MAX(pc.character_name), MAX(r.character_name), '') AS primary_character,
    COALESCE(MAX(c.committed_units), 0) AS committed_units,
    COALESCE(MAX(d.delivered_units), 0) AS delivered_units,
    COALESCE(MAX(c.committed_estimate), 0) AS committed_estimate,
    COALESCE(MAX(d.delivered_estimate), 0) AS delivered_estimate,
    COALESCE(MAX(c.committed_margin), 0) AS committed_margin,
    COALESCE(MAX(d.delivered_margin), 0) AS delivered_margin
FROM roster r
LEFT JOIN committed_by_user c ON c.user_id = r.user_id
LEFT JOIN delivered_by_user d ON d.user_id = r.user_id
LEFT JOIN eveonline_eveplayer ep ON ep.user_id = r.user_id
LEFT JOIN eveonline_evecharacter pc ON pc.id = ep.primary_character_id
GROUP BY r.user_id
ORDER BY delivered_margin DESC;
