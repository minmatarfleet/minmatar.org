-- PI by month: roster chars with PI wallet lines — distinct payers per month, implied gross ISK (tax / pi_tax_rate).
WITH params AS (
    SELECT 'industry' AS tribe_slug,
        'Planetary Interaction' AS tribe_group_name,
        0.01 AS pi_tax_rate
),
roster AS (
    SELECT DISTINCT ec.character_id AS eve_character_id
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
    DATE_FORMAT(j.date, '%Y-%m') AS report_month,
    COUNT(DISTINCT j.first_party_id) AS total_characters,
    SUM(j.amount) / p.pi_tax_rate AS total_estimate
FROM roster r
CROSS JOIN params p
INNER JOIN eveonline_evecorporationwalletjournalentry j
    ON j.first_party_id = r.eve_character_id
    AND j.ref_type IN ('planetary_export_tax', 'planetary_import_tax')
    AND j.date >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)
GROUP BY DATE_FORMAT(j.date, '%Y-%m')
ORDER BY report_month;
