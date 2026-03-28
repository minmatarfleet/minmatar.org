-- PI: by user — primary name, roster char count, implied gross ISK from tribe activity
-- (activity quantity is PI tax at customs; gross ≈ tax / pi_tax_rate, default 1%).
WITH params AS (
    SELECT 'industry' AS tribe_slug,
        'Planetary Interaction' AS tribe_group_name,
        0.01 AS pi_tax_rate
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
pi_tax_by_user AS (
    SELECT
        tar.user_id,
        SUM(tar.quantity) / p.pi_tax_rate AS isk_pi_30d_estimate
    FROM tribes_tribegroupactivityrecord tar
    CROSS JOIN params p
    INNER JOIN tribes_tribegroupactivity tga ON tga.id = tar.tribe_group_activity_id
        AND tga.is_active = 1
        AND tga.activity_type = 'planetary_interaction'
    INNER JOIN tribes_tribegroup tg ON tg.id = tga.tribe_group_id
        AND tg.is_active = 1
        AND tg.name = (SELECT tribe_group_name FROM params)
    INNER JOIN tribes_tribe t ON t.id = tg.tribe_id
        AND t.is_active = 1
        AND t.slug = (SELECT tribe_slug FROM params)
    INNER JOIN eveonline_evecorporationwalletjournalentry j
        ON j.corporation_id = CAST(SUBSTRING_INDEX(tar.reference_id, '-', 1) AS UNSIGNED)
        AND j.division = CAST(
            SUBSTRING_INDEX(SUBSTRING_INDEX(tar.reference_id, '-', 2), '-', -1) AS UNSIGNED
        )
        AND j.ref_id = CAST(SUBSTRING_INDEX(tar.reference_id, '-', -1) AS UNSIGNED)
        AND j.ref_type IN ('planetary_export_tax', 'planetary_import_tax')
    WHERE tar.reference_type = 'EveCorporationWalletJournalEntry'
        AND tar.unit = 'ISK'
        AND tar.user_id IS NOT NULL
        AND j.date >= DATE_SUB(NOW(), INTERVAL 30 DAY)
    GROUP BY tar.user_id
)
SELECT
    COALESCE(MAX(pc.character_name), MAX(r.character_name), '') AS primary_character_name,
    COUNT(DISTINCT r.character_pk) AS number_of_characters,
    COALESCE(MAX(pt.isk_pi_30d_estimate), 0) AS isk_pi_30d_estimate
FROM roster r
LEFT JOIN pi_tax_by_user pt ON pt.user_id = r.user_id
LEFT JOIN eveonline_eveplayer ep ON ep.user_id = r.user_id
LEFT JOIN eveonline_evecharacter pc ON pc.id = ep.primary_character_id
GROUP BY r.user_id
ORDER BY isk_pi_30d_estimate DESC;
