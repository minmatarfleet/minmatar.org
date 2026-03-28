-- Mining: by site user — primary name, roster char count, m³, ore-price ISK (30d; edit params).
WITH params AS (
    SELECT 'industry' AS tribe_slug,
        'Mining' AS tribe_group_name
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
)
SELECT
    COALESCE(MAX(pc.character_name), MAX(r.character_name), '') AS primary_character_name,
    COUNT(DISTINCT r.character_pk) AS number_of_characters,
    COALESCE(SUM(e.quantity * COALESCE(et.volume, 0)), 0) AS volume_m3,
    COALESCE(SUM(e.quantity * COALESCE(emp.average_price, 0)), 0) AS isk_ore_market_estimate
FROM roster r
LEFT JOIN eveonline_eveplayer ep ON ep.user_id = r.user_id
LEFT JOIN eveonline_evecharacter pc ON pc.id = ep.primary_character_id
LEFT JOIN eveonline_evecharacterminingentry e
    ON e.character_id = r.character_pk
    AND e.date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
LEFT JOIN eveuniverse_evetype et ON et.id = e.eve_type_id
LEFT JOIN eveuniverse_evemarketprice emp ON emp.eve_type_id = e.eve_type_id
GROUP BY r.user_id
ORDER BY volume_m3 DESC;
