-- Mining: tribe-group totals by month, last 12 months (report_month: MariaDB dislikes alias year_month).
WITH params AS (
    SELECT 'industry' AS tribe_slug,
        'Mining' AS tribe_group_name
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
    DATE_FORMAT(e.date, '%Y-%m') AS report_month,
    SUM(e.quantity * COALESCE(et.volume, 0)) AS total_volume_m3,
    SUM(e.quantity * COALESCE(emp.average_price, 0)) AS total_isk_ore_market_estimate
FROM roster r
INNER JOIN eveonline_evecharacterminingentry e
    ON e.character_id = r.character_pk
    AND e.date >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)
INNER JOIN eveuniverse_evetype et ON et.id = e.eve_type_id
LEFT JOIN eveuniverse_evemarketprice emp ON emp.eve_type_id = e.eve_type_id
GROUP BY DATE_FORMAT(e.date, '%Y-%m')
ORDER BY report_month;
