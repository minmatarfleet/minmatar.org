-- Convert navy destroyer pocket variants → EveFittingRefit on primaries
-- MySQL / MariaDB (production). Review before running.
-- Soft-deletes source fittings after copy; remaps Coercer bare-title FKs.
BEGIN;

-- Remap bare [NVY] Coercer Navy Issue (id=33) → MWD Scram Brawl (id=369)
UPDATE market_evemarketcontract SET fitting_id = 369 WHERE fitting_id = 33;
UPDATE fittings_evedoctrinefitting SET fitting_id = 369 WHERE fitting_id = 33;
UPDATE fittings_evefittingchangerequest SET fitting_id = 369 WHERE fitting_id = 33;
UPDATE fittings_evefitting
SET aliases = CASE
  WHEN aliases IS NULL OR TRIM(aliases) = '' THEN '[NVY] Coercer Navy Issue'
  WHEN LOCATE(LOWER('[NVY] Coercer Navy Issue'), LOWER(aliases)) > 0 THEN aliases
  ELSE CONCAT(aliases, ', [NVY] Coercer Navy Issue')
END
WHERE id = 369;

-- id=376 [NVY] Thrasher Fleet Issue — shield-acs → refit on id=28 [NVY] AC Thrasher Fleet Issue
INSERT INTO fittings_evefittingrefit (base_fitting_id, name, eft_format, description, created_at, updated_at) VALUES (
  28,
  'Shield ACs',
  '[Thrasher Fleet Issue, Shield ACs]

Gyrostabilizer II
Gyrostabilizer II
IFFA Compact Damage Control

5MN Quad LiF Restrained Microwarpdrive
Republic Fleet Medium Shield Extender
Warp Scrambler II

200mm AutoCannon II
200mm AutoCannon II
200mm AutoCannon II
Small Energy Neutralizer II
200mm AutoCannon II
200mm AutoCannon II
200mm AutoCannon II

Small Core Defense Field Extender I
Small EM Shield Reinforcer II
Small Thermal Shield Reinforcer II


Barrage S x2500
Hail S x5000
Nanite Repair Paste x50
Republic Fleet Depleted Uranium S x1000
Republic Fleet EMP S x1000
Republic Fleet Phased Plasma S x1000',
  'Shield autocannon brawler with a neut for cap-dependent targets at scram range. More speed and buffer than the armor AC variant; trades some EHP for mobility.',
  NOW(),
  NOW()
);
UPDATE fittings_evefitting SET deleted = NOW(), deleted_by_cascade = 0 WHERE id = 376 AND deleted IS NULL;

-- id=373 [NVY] Thrasher Fleet Issue — 280mm-acr → refit on id=41 [NVY] Arty Thrasher Fleet Issue
INSERT INTO fittings_evefittingrefit (base_fitting_id, name, eft_format, description, created_at, updated_at) VALUES (
  41,
  '280mm ACR',
  '[Thrasher Fleet Issue, 280mm ACR]

Gyrostabilizer II
Counterbalanced Compact Gyrostabilizer
IFFA Compact Damage Control

5MN Y-T8 Compact Microwarpdrive
Fleeting Compact Stasis Webifier
Initiated Compact Warp Disruptor

280mm Howitzer Artillery II
280mm Howitzer Artillery II
280mm Howitzer Artillery II
[Empty High slot]
280mm Howitzer Artillery II
280mm Howitzer Artillery II
280mm Howitzer Artillery II

Small Transverse Bulkhead II
Small Projectile Collision Accelerator I
Small Ancillary Current Router I


Quake S x1500
Tremor S x1500
Nanite Repair Paste x50
Republic Fleet Depleted Uranium S x1000
Republic Fleet EMP S x1000
Republic Fleet Fusion S x1000
Republic Fleet Phased Plasma S x1000',
  'Standard 280mm artillery kiter with collision accelerator for alpha and range control. Excellent for fighting on your terms; if you get tackled, you die.',
  NOW(),
  NOW()
);
UPDATE fittings_evefitting SET deleted = NOW(), deleted_by_cascade = 0 WHERE id = 373 AND deleted IS NULL;

-- id=374 [NVY] Thrasher Fleet Issue — 280-overdrive → refit on id=41 [NVY] Arty Thrasher Fleet Issue
INSERT INTO fittings_evefittingrefit (base_fitting_id, name, eft_format, description, created_at, updated_at) VALUES (
  41,
  '280 Overdrive',
  '[Thrasher Fleet Issue, 280 Overdrive]

Gyrostabilizer II
Overdrive Injector System II
Damage Control II

5MN Y-T8 Compact Microwarpdrive
Fleeting Compact Stasis Webifier
Warp Disruptor II

280mm Howitzer Artillery II
280mm Howitzer Artillery II
280mm Howitzer Artillery II
[Empty High slot]
280mm Howitzer Artillery II
280mm Howitzer Artillery II
280mm Howitzer Artillery II

Small Transverse Bulkhead II
Small Transverse Bulkhead II
Small Transverse Bulkhead II


Quake S x1500
Tremor S x1500
Nanite Repair Paste x50
Republic Fleet Depleted Uranium S x1000
Republic Fleet EMP S x1000
Republic Fleet Fusion S x1000
Republic Fleet Phased Plasma S x1000',
  'Simpler overdrive artillery kiter with more speed and less alpha than the ACR variant. Good entry 280mm fit for pilots learning Thrasher Fleet Issue kiting.',
  NOW(),
  NOW()
);
UPDATE fittings_evefitting SET deleted = NOW(), deleted_by_cascade = 0 WHERE id = 374 AND deleted IS NULL;

-- id=377 [NVY] Thrasher Fleet Issue — 280-double-web → refit on id=41 [NVY] Arty Thrasher Fleet Issue
INSERT INTO fittings_evefittingrefit (base_fitting_id, name, eft_format, description, created_at, updated_at) VALUES (
  41,
  '280 Double Web',
  '[Thrasher Fleet Issue, 280 Double Web]

Damage Control II
Gyrostabilizer II
Gyrostabilizer II

1MN Afterburner II
Fleeting Compact Stasis Webifier
Fleeting Compact Stasis Webifier

280mm Howitzer Artillery II
280mm Howitzer Artillery II
280mm Howitzer Artillery II
[Empty High slot]
280mm Howitzer Artillery II
280mm Howitzer Artillery II
280mm Howitzer Artillery II

Small Transverse Bulkhead II
Small Transverse Bulkhead II
Small Transverse Bulkhead II


Quake S x1500
Tremor S x1500
Nanite Repair Paste x50
Republic Fleet Depleted Uranium S x1000
Republic Fleet EMP S x1000
Republic Fleet Fusion S x1000
Republic Fleet Phased Plasma S x1000',
  'Dual-web afterburner arty fit for catching kiters and controlling range at artillery optimal. A meme build that turns the tables on other 280mm kiters who rely on keeping you at range.',
  NOW(),
  NOW()
);
UPDATE fittings_evefitting SET deleted = NOW(), deleted_by_cascade = 0 WHERE id = 377 AND deleted IS NULL;

-- id=363 [NVY] Catalyst Navy Issue — saar-web-scram → refit on id=37 [NVY] Blaster Catalyst Navy Issue
INSERT INTO fittings_evefittingrefit (base_fitting_id, name, eft_format, description, created_at, updated_at) VALUES (
  37,
  'SAAR Web Scram',
  '[Catalyst Navy Issue, SAAR Web Scram]

Small Ancillary Armor Repairer
Damage Control II
Vortex Compact Magnetic Field Stabilizer

5MN Y-T8 Compact Microwarpdrive
Warp Scrambler II
Fleeting Compact Stasis Webifier

Light Neutron Blaster II
Light Neutron Blaster II
Light Neutron Blaster II
Small Ghoul Compact Energy Nosferatu
Light Neutron Blaster II
Light Neutron Blaster II
Light Neutron Blaster II

Small Transverse Bulkhead II
Small Transverse Bulkhead II
Small Transverse Bulkhead II


Null S x2500
Void S x5000
Caldari Navy Antimatter Charge S x1000
Nanite Repair Paste x50',
  'Active armor blaster brawler using a SAAR and nosferatu for sustain. More flexible than the plate variant but with a thinner buffer; still beats most destroyers you can land scram and web on.',
  NOW(),
  NOW()
);
UPDATE fittings_evefitting SET deleted = NOW(), deleted_by_cascade = 0 WHERE id = 363 AND deleted IS NULL;

-- id=365 [NVY] Catalyst Navy Issue — 10mn-125mm → refit on id=32 [NVY] 10mn Catalyst Navy Issue
INSERT INTO fittings_evefittingrefit (base_fitting_id, name, eft_format, description, created_at, updated_at) VALUES (
  32,
  '10mn 125mm',
  '[Catalyst Navy Issue, 10mn 125mm]

Damage Control II
Magnetic Field Stabilizer II
Small Ancillary Armor Repairer

10MN Monopropellant Enduring Afterburner
X5 Enduring Stasis Webifier
Warp Disruptor II

125mm Railgun II
125mm Railgun II
125mm Railgun II
[Empty High slot]
125mm Railgun II
125mm Railgun II
125mm Railgun II

Small Transverse Bulkhead II
Small Transverse Bulkhead II
Small Transverse Bulkhead II


Caldari Navy Antimatter Charge S x2000
Caldari Navy Iridium Charge S x2000
Caldari Navy Iron Charge S x2000
Caldari Navy Thorium Charge S x2000
Nanite Repair Paste x120',
  'Faster 10MN rail kiter with T2 125mm rails and a disruptor. Even harder to catch than the 150mm variant but with lower raw DPS; excellent for picking destroyer fights on your terms.',
  NOW(),
  NOW()
);
UPDATE fittings_evefitting SET deleted = NOW(), deleted_by_cascade = 0 WHERE id = 365 AND deleted IS NULL;

-- id=379 [NVY] Cormorant Navy Issue — dual-masb-ions → refit on id=378 [NVY] Cormorant Navy Issue — dual-masb-neutrons
INSERT INTO fittings_evefittingrefit (base_fitting_id, name, eft_format, description, created_at, updated_at) VALUES (
  378,
  'Dual MASB Ions',
  '[Cormorant Navy Issue, Dual MASB Ions]

Damage Control II
Magnetic Field Stabilizer II

1MN Afterburner II
Warp Scrambler II
Medium Ancillary Shield Booster
Medium Ancillary Shield Booster

Light Ion Blaster II
Light Ion Blaster II
Light Ion Blaster II
[Empty High slot]
Light Ion Blaster II
Light Ion Blaster II
Light Ion Blaster II

Small EM Shield Reinforcer I
Small Hybrid Burst Aerator II
Small Thermal Shield Reinforcer I


Null S x2500
Void S x5000
Caldari Navy Antimatter Charge S x1000
Nanite Repair Paste x100
Navy Cap Booster 400 x25',
  'Dual MASB ion blaster brawler with slightly longer reach than the neutron variant. Same burst-shield brawl concept for pilots who prefer ion range and tracking tradeoffs.',
  NOW(),
  NOW()
);
UPDATE fittings_evefitting SET deleted = NOW(), deleted_by_cascade = 0 WHERE id = 379 AND deleted IS NULL;

-- id=368 [NVY] Coercer Navy Issue — ab-scram-brawl → refit on id=369 [NVY] Coercer Navy Issue — mwd-scram-brawl
INSERT INTO fittings_evefittingrefit (base_fitting_id, name, eft_format, description, created_at, updated_at) VALUES (
  369,
  'AB Scram Brawl',
  '[Coercer Navy Issue, AB Scram Brawl]

Damage Control II
Multispectrum Energized Membrane II
400mm Rolled Tungsten Compact Plates
Heat Sink II

1MN Afterburner II
Warp Scrambler II

Dual Light Pulse Laser II
Dual Light Pulse Laser II
Dual Light Pulse Laser II
Small Infectious Scoped Energy Neutralizer
Dual Light Pulse Laser II
Dual Light Pulse Laser II
Dual Light Pulse Laser II

Small Trimark Armor Pump I
Small Trimark Armor Pump I
Small Trimark Armor Pump I


Conflagration S x5
Scorch S x5
Imperial Navy Multifrequency S x5
Nanite Repair Paste x50',
  'Afterburner pulse brawler for tighter range control without MWD signature penalty. Full dual-pulse rack with a neut for cap warfare in straight scram brawls.',
  NOW(),
  NOW()
);
UPDATE fittings_evefitting SET deleted = NOW(), deleted_by_cascade = 0 WHERE id = 368 AND deleted IS NULL;

-- id=372 [NVY] Coercer Navy Issue — web-beams → refit on id=371 [NVY] Coercer Navy Issue — kite-beams
INSERT INTO fittings_evefittingrefit (base_fitting_id, name, eft_format, description, created_at, updated_at) VALUES (
  371,
  'Web Beams',
  '[Coercer Navy Issue, Web Beams]

Heat Sink II
Heat Sink II
Damage Control II
Fourier Compact Tracking Enhancer

Stasis Webifier II
Fleeting Compact Stasis Webifier

Small Focused Beam Laser II
Small Focused Beam Laser II
Small Focused Beam Laser II
[Empty High slot]
Small Focused Beam Laser II
Small Focused Beam Laser II
Small Focused Beam Laser II

Small Processor Overclocking Unit II
Small Transverse Bulkhead I
Small Transverse Bulkhead I


Conflagration S x5
Imperial Navy Multifrequency S x5
Scorch S x5
Nanite Repair Paste x50',
  'Double-web beam fit for catching other kiters and holding them in beam range. A niche meme build that punishes pilots who assume every Coercer is a neut brawler.',
  NOW(),
  NOW()
);
UPDATE fittings_evefitting SET deleted = NOW(), deleted_by_cascade = 0 WHERE id = 372 AND deleted IS NULL;

-- id=370 [NVY] Coercer Navy Issue — locus-pulse → refit on id=371 [NVY] Coercer Navy Issue — kite-beams
INSERT INTO fittings_evefittingrefit (base_fitting_id, name, eft_format, description, created_at, updated_at) VALUES (
  371,
  'Locus Pulse',
  '[Coercer Navy Issue, Locus Pulse]

Heat Sink II
Extruded Compact Heat Sink
Damage Control II
Small Ancillary Armor Repairer

5MN Y-T8 Compact Microwarpdrive
Initiated Compact Warp Disruptor

Small Focused Pulse Laser II
Small Focused Pulse Laser II
Small Focused Pulse Laser II
[Empty High slot]
Small Focused Pulse Laser II
Small Focused Pulse Laser II
Small Focused Pulse Laser II

Small Transverse Bulkhead II
Small Energy Locus Coordinator II
Small Energy Locus Coordinator II


Conflagration S x5
Scorch S x5
Imperial Navy Multifrequency S x5
Nanite Repair Paste x50',
  'Locus coordinator pulse kiter with SAAR for mid-range pressure. Uses tracking and the hull''s neut-adjacent slot layout to fight at pulse falloff while staying mobile.',
  NOW(),
  NOW()
);
UPDATE fittings_evefitting SET deleted = NOW(), deleted_by_cascade = 0 WHERE id = 370 AND deleted IS NULL;

-- id=367 [NVY] Coercer Navy Issue — dual-neuts-no-prop → refit on id=366 [NVY] Coercer Navy Issue — dual-neuts-mwd
INSERT INTO fittings_evefittingrefit (base_fitting_id, name, eft_format, description, created_at, updated_at) VALUES (
  366,
  'Dual Neuts No Prop',
  '[Coercer Navy Issue, Dual Neuts No Prop]

400mm Rolled Tungsten Compact Plates
Damage Control II
Heat Sink II
Multispectrum Coating II

Faint Epsilon Scoped Warp Scrambler
Fleeting Compact Stasis Webifier

Small Focused Pulse Laser II
Small Focused Pulse Laser II
Small Focused Pulse Laser II
Small Energy Neutralizer II
Small Infectious Scoped Energy Neutralizer
Small Focused Pulse Laser II
Small Focused Pulse Laser II

Small Ancillary Current Router II
Small Trimark Armor Pump I
Small Energy Locus Coordinator II


Conflagration S x5
Scorch S x5
Imperial Navy Multifrequency S x5
Nanite Repair Paste x50',
  'Slow brawler with dual neuts, web, and no prop mod. Trades mobility for more tank and control at scram range; ideal when you expect a straight brawl rather than a chase.',
  NOW(),
  NOW()
);
UPDATE fittings_evefitting SET deleted = NOW(), deleted_by_cascade = 0 WHERE id = 367 AND deleted IS NULL;

-- Soft-delete id=375 [NVY] Thrasher Fleet Issue — armour-acs: Near-duplicate of [NVY] AC Thrasher Fleet Issue (id=28)
UPDATE fittings_evefitting SET deleted = NOW(), deleted_by_cascade = 0 WHERE id = 375 AND deleted IS NULL;

-- Soft-delete id=364 [NVY] Catalyst Navy Issue — 10mn-150mm: Near-duplicate of [NVY] 10mn Catalyst Navy Issue (id=32)
UPDATE fittings_evefitting SET deleted = NOW(), deleted_by_cascade = 0 WHERE id = 364 AND deleted IS NULL;

-- Soft-delete id=33 [NVY] Coercer Navy Issue: Bare hull title; contracts/doctrine remapped to MWD Scram Brawl (id=369)
UPDATE fittings_evefitting SET deleted = NOW(), deleted_by_cascade = 0 WHERE id = 33 AND deleted IS NULL;

COMMIT;

-- ---------------------------------------------------------------------------
-- Rename primaries to [PREFIX] [VARIANT] [FULL SHIP NAME]
-- Run after the refit conversion above (or alone if conversion already applied).
-- Keep old titles as aliases so existing contracts still match.
-- ---------------------------------------------------------------------------

-- id=366 → [NVY] 2X Neut Coercer Navy Issue
UPDATE fittings_evefitting
SET name = '[NVY] 2X Neut Coercer Navy Issue',
    aliases = CASE
      WHEN aliases IS NULL OR TRIM(aliases) = '' THEN '[NVY] Coercer Navy Issue — dual-neuts-mwd'
      WHEN LOCATE(LOWER('[NVY] Coercer Navy Issue — dual-neuts-mwd'), LOWER(aliases)) > 0 THEN aliases
      ELSE CONCAT(aliases, ', [NVY] Coercer Navy Issue — dual-neuts-mwd')
    END,
    eft_format = CONCAT('[Coercer Navy Issue, [NVY] 2X Neut Coercer Navy Issue]',
                        SUBSTRING(eft_format, LOCATE('\n', eft_format)))
WHERE id = 366 AND deleted IS NULL;

-- id=369 → [NVY] Pulse Coercer Navy Issue
UPDATE fittings_evefitting
SET name = '[NVY] Pulse Coercer Navy Issue',
    aliases = CASE
      WHEN aliases IS NULL OR TRIM(aliases) = '' THEN '[NVY] Coercer Navy Issue — mwd-scram-brawl, [NVY] Coercer Navy Issue'
      WHEN LOCATE(LOWER('[NVY] Coercer Navy Issue — mwd-scram-brawl'), LOWER(aliases)) > 0 THEN aliases
      ELSE CONCAT(aliases, ', [NVY] Coercer Navy Issue — mwd-scram-brawl')
    END,
    eft_format = CONCAT('[Coercer Navy Issue, [NVY] Pulse Coercer Navy Issue]',
                        SUBSTRING(eft_format, LOCATE('\n', eft_format)))
WHERE id = 369 AND deleted IS NULL;

-- id=371 → [NVY] Beam Coercer Navy Issue
UPDATE fittings_evefitting
SET name = '[NVY] Beam Coercer Navy Issue',
    aliases = CASE
      WHEN aliases IS NULL OR TRIM(aliases) = '' THEN '[NVY] Coercer Navy Issue — kite-beams'
      WHEN LOCATE(LOWER('[NVY] Coercer Navy Issue — kite-beams'), LOWER(aliases)) > 0 THEN aliases
      ELSE CONCAT(aliases, ', [NVY] Coercer Navy Issue — kite-beams')
    END,
    eft_format = CONCAT('[Coercer Navy Issue, [NVY] Beam Coercer Navy Issue]',
                        SUBSTRING(eft_format, LOCATE('\n', eft_format)))
WHERE id = 371 AND deleted IS NULL;

-- id=378 → [NVY] Dual MASB Cormorant Navy Issue
UPDATE fittings_evefitting
SET name = '[NVY] Dual MASB Cormorant Navy Issue',
    aliases = CASE
      WHEN aliases IS NULL OR TRIM(aliases) = '' THEN '[NVY] Cormorant Navy Issue — dual-masb-neutrons'
      WHEN LOCATE(LOWER('[NVY] Cormorant Navy Issue — dual-masb-neutrons'), LOWER(aliases)) > 0 THEN aliases
      ELSE CONCAT(aliases, ', [NVY] Cormorant Navy Issue — dual-masb-neutrons')
    END,
    eft_format = CONCAT('[Cormorant Navy Issue, [NVY] Dual MASB Cormorant Navy Issue]',
                        SUBSTRING(eft_format, LOCATE('\n', eft_format)))
WHERE id = 378 AND deleted IS NULL;

-- id=380 → [NVY] Buffer Cormorant Navy Issue
UPDATE fittings_evefitting
SET name = '[NVY] Buffer Cormorant Navy Issue',
    aliases = CASE
      WHEN aliases IS NULL OR TRIM(aliases) = '' THEN '[NVY] Cormorant Navy Issue — buffer'
      WHEN LOCATE(LOWER('[NVY] Cormorant Navy Issue — buffer'), LOWER(aliases)) > 0 THEN aliases
      ELSE CONCAT(aliases, ', [NVY] Cormorant Navy Issue — buffer')
    END,
    eft_format = CONCAT('[Cormorant Navy Issue, [NVY] Buffer Cormorant Navy Issue]',
                        SUBSTRING(eft_format, LOCATE('\n', eft_format)))
WHERE id = 380 AND deleted IS NULL;

-- id=381 → [NVY] 10mn Cormorant Navy Issue
UPDATE fittings_evefitting
SET name = '[NVY] 10mn Cormorant Navy Issue',
    aliases = CASE
      WHEN aliases IS NULL OR TRIM(aliases) = '' THEN '[NVY] Cormorant Navy Issue — 10mn'
      WHEN LOCATE(LOWER('[NVY] Cormorant Navy Issue — 10mn'), LOWER(aliases)) > 0 THEN aliases
      ELSE CONCAT(aliases, ', [NVY] Cormorant Navy Issue — 10mn')
    END,
    eft_format = CONCAT('[Cormorant Navy Issue, [NVY] 10mn Cormorant Navy Issue]',
                        SUBSTRING(eft_format, LOCATE('\n', eft_format)))
WHERE id = 381 AND deleted IS NULL;

-- id=382 → [NVY] 10mn Rocket Talwar Fleet Issue
UPDATE fittings_evefitting
SET name = '[NVY] 10mn Rocket Talwar Fleet Issue',
    aliases = CASE
      WHEN aliases IS NULL OR TRIM(aliases) = '' THEN '[NVY] Talwar Fleet Issue — 10mn-rocket'
      WHEN LOCATE(LOWER('[NVY] Talwar Fleet Issue — 10mn-rocket'), LOWER(aliases)) > 0 THEN aliases
      ELSE CONCAT(aliases, ', [NVY] Talwar Fleet Issue — 10mn-rocket')
    END,
    eft_format = CONCAT('[Talwar Fleet Issue, [NVY] 10mn Rocket Talwar Fleet Issue]',
                        SUBSTRING(eft_format, LOCATE('\n', eft_format)))
WHERE id = 382 AND deleted IS NULL;
