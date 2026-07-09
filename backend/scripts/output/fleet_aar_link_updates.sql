-- Backfill EveFleet.aar_link from Discord #aars forum threads
-- Generated: 2026-07-09T18:48:39.051844+00:00
-- Matches: 114
START TRANSACTION;

-- fleet_id=261 start=2024-01-01T20:58:31+00:00
-- thread: '2024-01-01 New Year, New Citadel!' (1324183055526793236)
-- delta_minutes=538.5 reason=time-only
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1324183055526793236' WHERE id = 261 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=271 start=2024-01-06T17:30:00+00:00
-- thread: '2024-01-06 FL33T eat world' (1193381922206920744)
-- delta_minutes=330.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1193381922206920744' WHERE id = 271 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=274 start=2024-01-07T19:36:25+00:00
-- thread: '2024-01-07  Wake me up inside' (1194086216199577731)
-- delta_minutes=456.4 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1194086216199577731' WHERE id = 274 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=305 start=2024-01-20T17:30:00+00:00
-- thread: '2024-01-20 4 hours of slugging' (1198416673397559357)
-- delta_minutes=330.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1198416673397559357' WHERE id = 305 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=312 start=2024-01-22T01:48:05+00:00
-- thread: '2024-01-21 Militia Fleet' (1198731879159963810)
-- delta_minutes=828.1 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1198731879159963810' WHERE id = 312 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=306 start=2024-01-20T19:15:00+00:00
-- thread: '2024-01-21 Mining Permit' (1198821591606378539)
-- delta_minutes=1005.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1198821591606378539' WHERE id = 306 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=315 start=2024-01-24T23:59:00+00:00
-- thread: '2024-01-24: Carpetbombin CVA structures' (1199897409300471838)
-- delta_minutes=719.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1199897409300471838' WHERE id = 315 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=316 start=2024-01-25T01:41:34+00:00
-- thread: "2024-01-25 CVA's Retaliatory Strike" (1200548419232616468)
-- delta_minutes=618.4 reason=time-only
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1200548419232616468' WHERE id = 316 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=321 start=2024-01-28T16:45:00+00:00
-- thread: '2024-01-28 Three Hundred Men' (1201310329389457548)
-- delta_minutes=285.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1201310329389457548' WHERE id = 321 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=331 start=2024-02-04T20:17:17+00:00
-- thread: '2024-02-04 Provi Shenanagins' (1203812323408478269)
-- delta_minutes=497.3 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1203812323408478269' WHERE id = 331 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=343 start=2024-02-10T03:25:25+00:00
-- thread: '2024-02-10 Uusanen Ihub Defence (and more!)' (1205754924059725885)
-- delta_minutes=514.6 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1205754924059725885' WHERE id = 343 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=347 start=2024-02-11T17:00:00+00:00
-- thread: '2024-02-11 Basics of Bombing - Training Fleet #1' (1206305899157786735)
-- delta_minutes=300.0 reason=time-only
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1206305899157786735' WHERE id = 347 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=349 start=2024-02-13T00:55:55+00:00
-- thread: '2024-02-12 Masochist Structure Bashing' (1206790089263419505)
-- delta_minutes=775.9 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1206790089263419505' WHERE id = 349 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=358 start=2024-02-18T19:36:02+00:00
-- thread: '2024-02-18 Frontline Fleet' (1208894401422827560)
-- delta_minutes=456.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1208894401422827560' WHERE id = 358 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=355 start=2024-02-18T16:48:31+00:00
-- thread: '2024-02-18 Testing Ferox against NOmen, and shooting structures... apparently.' (1208847035458134107)
-- delta_minutes=288.5 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1208847035458134107' WHERE id = 355 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=362 start=2024-02-20T21:59:43+00:00
-- thread: '2024-02-21 Smallgang SIG goes roaming in Provi' (1209816109394690078)
-- delta_minutes=840.3 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1209816109394690078' WHERE id = 362 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=363 start=2024-02-22T01:00:00+00:00
-- thread: '2024-02-21 Terrorizing the Warzone' (1210267782936272907)
-- delta_minutes=780.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1210267782936272907' WHERE id = 363 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=356 start=2024-02-23T02:00:00+00:00
-- thread: '2024-02-22 Slugging over Amarr Structures' (1210593254341484554)
-- delta_minutes=840.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1210593254341484554' WHERE id = 356 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=364 start=2024-02-23T05:00:00+00:00
-- thread: '2024-02-22 Dripped out Drakes' (1210462480367616010)
-- delta_minutes=1020.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1210462480367616010' WHERE id = 364 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=372 start=2024-02-28T01:10:29+00:00
-- thread: "2024-02-28 EDICT's Final Structure" (1212620234469670932)
-- delta_minutes=649.5 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1212620234469670932' WHERE id = 372 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=394 start=2024-03-07T02:37:27+00:00
-- thread: '2024-03-6 The Frontline Provides Part 2, Electric Boogaloo.' (1215173722537730058)
-- delta_minutes=189.1 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1215173722537730058' WHERE id = 394 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=401 start=2024-03-10T14:21:53+00:00
-- thread: '2024-03-10 Flash Form' (1216403588931387502)
-- delta_minutes=141.9 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1216403588931387502' WHERE id = 401 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=405 start=2024-03-14T00:01:00+00:00
-- thread: '2024-03-13 - Another Casper Structure Bash' (1217654023247626300)
-- delta_minutes=721.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1217654023247626300' WHERE id = 405 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=407 start=2024-03-15T00:23:27+00:00
-- thread: "14/04/24 kiki's" (1217986544640593950)
-- delta_minutes=19.8 reason=time-only
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1217986544640593950' WHERE id = 407 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=408 start=2024-03-16T01:00:00+00:00
-- thread: '2024-03-15 Friday night fun' (1218409377950863440)
-- delta_minutes=780.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1218409377950863440' WHERE id = 408 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=419 start=2024-03-19T23:00:00+00:00
-- thread: "2024-03-19 Shem's Retirement Fund, Confescated." (1219373061426384947)
-- delta_minutes=660.0 reason=time-only
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1219373061426384947' WHERE id = 419 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=424 start=2024-03-24T02:35:00+00:00
-- thread: 'The Rat Tax is Paid' (1221312293938401371)
-- delta_minutes=104.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1221312293938401371' WHERE id = 424 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=445 start=2024-04-04T16:10:37+00:00
-- thread: '2024-04-04 The Dragons ride again' (1226154088937295902)
-- delta_minutes=250.6 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1226154088937295902' WHERE id = 445 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=457 start=2024-04-07T17:00:00+00:00
-- thread: '2024-04-07 FL33T FEED #2' (1226631849120501874)
-- delta_minutes=300.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1226631849120501874' WHERE id = 457 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=456 start=2024-04-07T11:00:00+00:00
-- thread: '2024-04-07, Downtime battlefields, once more!' (1226509347031486474)
-- delta_minutes=60.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1226509347031486474' WHERE id = 456 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=464 start=2024-04-12T01:45:50+00:00
-- thread: '2024-04-12 True Herons' (1228441624300884128)
-- delta_minutes=614.2 reason=time-only
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1228441624300884128' WHERE id = 464 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=465 start=2024-04-13T19:00:00+00:00
-- thread: '2024-04-13 Scalding Chickens' (1228897812541079602)
-- delta_minutes=420.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1228897812541079602' WHERE id = 465 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=461 start=2024-04-14T00:15:00+00:00
-- thread: '2024-04-13 Saturday Shenanigans' (1228819775480660070)
-- delta_minutes=735.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1228819775480660070' WHERE id = 461 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=473 start=2024-04-17T00:00:00+00:00
-- thread: '2024-04-16 Scorched Earth' (1230129783233314929)
-- delta_minutes=720.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1230129783233314929' WHERE id = 473 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=477 start=2024-04-18T11:01:21+00:00
-- thread: '2024-04-18 The rats versus the Dragons' (1230510121650491402)
-- delta_minutes=58.6 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1230510121650491402' WHERE id = 477 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=478 start=2024-04-18T23:00:00+00:00
-- thread: '2024-04-18 Threesome in Scalding Pass' (1230687475471482944)
-- delta_minutes=660.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1230687475471482944' WHERE id = 478 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=484 start=2024-04-20T23:30:00+00:00
-- thread: '2024-04-20 IS THIS CYBERBULLYING?' (1231417488626155592)
-- delta_minutes=690.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1231417488626155592' WHERE id = 484 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=488 start=2024-04-21T19:20:54+00:00
-- thread: '2024-04-21 Sunday USTZ Content' (1231780685862408252)
-- delta_minutes=440.9 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1231780685862408252' WHERE id = 488 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=489 start=2024-04-21T22:58:51+00:00
-- thread: '2024-04-21 Sunday EUTZ Content' (1231705763844591646)
-- delta_minutes=658.9 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1231705763844591646' WHERE id = 489 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=485 start=2024-04-22T23:30:00+00:00
-- thread: '2024-04-22: MINMATAR MINING ALLIANCE' (1232152899031797882)
-- delta_minutes=690.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1232152899031797882' WHERE id = 485 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=498 start=2024-04-25T02:23:23+00:00
-- thread: 'Ourzad Under Fire (#1 because we all know there will be more)' (1232896483427225613)
-- delta_minutes=67.1 reason=time-only
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1232896483427225613' WHERE id = 498 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=494 start=2024-04-26T00:45:00+00:00
-- thread: '2024-04-25 Typhoon adventure' (1233253947398029373)
-- delta_minutes=765.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1233253947398029373' WHERE id = 494 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=505 start=2024-04-28T02:03:20+00:00
-- thread: '2024-04-27 Yourzad… Myzad… Ourzad…Spyzad..?' (1233984052562886676)
-- delta_minutes=843.3 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1233984052562886676' WHERE id = 505 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=510 start=2024-04-30T23:45:00+00:00
-- thread: '2024-05-01 Defending OURZAD from an elite opponent' (1235397771272519781)
-- delta_minutes=735.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1235397771272519781' WHERE id = 510 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=513 start=2024-05-02T23:30:42+00:00
-- thread: 'Bears fun roaming fleet' (1235756365260128356)
-- delta_minutes=83.9 reason=time-only
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1235756365260128356' WHERE id = 513 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=509 start=2024-05-04T00:50:00+00:00
-- thread: '2024-05-03 DRUNK DRIPPED OUT DRAKES' (1236144062206181416)
-- delta_minutes=770.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1236144062206181416' WHERE id = 509 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=514 start=2024-05-04T17:30:00+00:00
-- thread: '2024-05-04 What a lovely, peaceful day' (1236499235612917841)
-- delta_minutes=330.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1236499235612917841' WHERE id = 514 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=524 start=2024-05-07T23:30:00+00:00
-- thread: '2024-05-07 Tuesday Night Brawl' (1237584655528759327)
-- delta_minutes=690.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1237584655528759327' WHERE id = 524 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=536 start=2024-05-15T00:14:13+00:00
-- thread: 'Heavy Survives! Tararan Athanor Kill Op' (1239995139263430677)
-- delta_minutes=396.2 reason=time-only
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1239995139263430677' WHERE id = 536 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=541 start=2024-05-19T02:00:06+00:00
-- thread: '2024-05-19 Tasha Dying Repeatedly: The Battlefield' (1241932112068874420)
-- delta_minutes=599.9 reason=time-only
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1241932112068874420' WHERE id = 541 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=543 start=2024-05-18T21:00:00+00:00
-- thread: '2024-05-19 Absolute Bitches: the Watermelon flash form' (1241844621928038431)
-- delta_minutes=900.0 reason=time-only
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1241844621928038431' WHERE id = 543 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=545 start=2024-05-22T10:30:00+00:00
-- thread: '2024-05-22 Everyone Hates DG' (1242813983971479607)
-- delta_minutes=90.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1242813983971479607' WHERE id = 545 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=549 start=2024-05-23T21:00:00+00:00
-- thread: '2024-05-23 Shooting UNITY, BIGAB, and DIGI' (1243333707524345986)
-- delta_minutes=540.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1243333707524345986' WHERE id = 549 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=546 start=2024-05-24T01:00:00+00:00
-- thread: '2024-05-23 Late Night Fun / Athanor Defense' (1243397039774109696)
-- delta_minutes=780.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1243397039774109696' WHERE id = 546 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=551 start=2024-05-26T22:30:00+00:00
-- thread: '2024-05-26 DUNKING DIGI & HORDE' (1244449705002533064)
-- delta_minutes=630.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1244449705002533064' WHERE id = 551 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=567 start=2024-05-30T23:45:00+00:00
-- thread: '2024-05-30 Getting Creative' (1245925913410146325)
-- delta_minutes=705.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1245925913410146325' WHERE id = 567 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=570 start=2024-05-29T23:45:00+00:00
-- thread: '2024-05-30 Vard Ihub Round 1' (1245856636678049863)
-- delta_minutes=735.0 reason=time-only
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1245856636678049863' WHERE id = 570 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=574 start=2024-05-31T21:00:00+00:00
-- thread: '2024-05-31 Kitchen Sink Fleet' (1246241986529460266)
-- delta_minutes=540.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1246241986529460266' WHERE id = 574 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=577 start=2024-06-02T14:15:00+00:00
-- thread: '2024-06-02 DIGI FINALLY GOT IT DOWN' (1246973646879195207)
-- delta_minutes=135.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1246973646879195207' WHERE id = 577 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=569 start=2024-06-02T17:00:00+00:00
-- thread: '2024-06-02 SUBCAPITAL Shenanigans' (1246900506119634945)
-- delta_minutes=300.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1246900506119634945' WHERE id = 569 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=582 start=2024-06-05T13:28:00+00:00
-- thread: '2024-06-05 WATERMELLON DEFENSE' (1247914658808201287)
-- delta_minutes=88.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1247914658808201287' WHERE id = 582 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=589 start=2024-06-10T11:30:00+00:00
-- thread: '2024-06-10 Dragon Riders Legion Structures – Caution: Student Driver' (1249829888849088553)
-- delta_minutes=30.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1249829888849088553' WHERE id = 589 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=596 start=2024-06-13T23:00:00+00:00
-- thread: '2024-06-13 Roaming the Warzone' (1250982158714011749)
-- delta_minutes=660.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1250982158714011749' WHERE id = 596 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=621 start=2024-06-21T13:25:00+00:00
-- thread: '2024-06-21 Good guys win again' (1253722079463866500)
-- delta_minutes=85.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1253722079463866500' WHERE id = 621 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=622 start=2024-06-22T17:30:00+00:00
-- thread: '2024-06-22 Carrier Conduit' (1254196267610013781)
-- delta_minutes=330.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1254196267610013781' WHERE id = 622 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=623 start=2024-06-22T20:30:00+00:00
-- thread: '2024-06-22 Fortizar Shenanigans' (1254194663775146134)
-- delta_minutes=510.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1254194663775146134' WHERE id = 623 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=618 start=2024-06-23T11:30:00+00:00
-- thread: '2024-06-23 We Came, Some Died, We Left.' (1254424172847960175)
-- delta_minutes=30.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1254424172847960175' WHERE id = 618 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=630 start=2024-06-26T01:10:00+00:00
-- thread: '2024-06-25 Big Brother Bear Holds My Hand //  IHUB Brawl and HIC Bubble Catching BIGAB' (1255347571816402955)
-- delta_minutes=790.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1255347571816402955' WHERE id = 630 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=635 start=2024-06-29T17:30:00+00:00
-- thread: '2024-06-29 The Rat Provides' (1256790294582792212)
-- delta_minutes=330.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1256790294582792212' WHERE id = 635 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=637 start=2024-07-01T19:00:00+00:00
-- thread: '2024-07-01 Tinfoil Fleet #1' (1257426424600727633)
-- delta_minutes=420.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1257426424600727633' WHERE id = 637 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=639 start=2024-07-03T00:15:00+00:00
-- thread: '2024-07-02 Structure defense... and a dread?' (1257873331508740196)
-- delta_minutes=735.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1257873331508740196' WHERE id = 639 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=646 start=2024-07-07T17:00:00+00:00
-- thread: '2024-07-07 Amarr Structure' (1259661197985189988)
-- delta_minutes=300.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1259661197985189988' WHERE id = 646 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=645 start=2024-07-07T22:30:00+00:00
-- thread: '2024-07-07 Mumble Test #2' (1259587369385066608)
-- delta_minutes=630.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1259587369385066608' WHERE id = 645 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=661 start=2024-07-12T02:05:00+00:00
-- thread: '2024-07-12 - Raitaru Timers - Capitals' (1261711000470556825)
-- delta_minutes=595.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1261711000470556825' WHERE id = 661 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=673 start=2024-07-15T02:00:00+00:00
-- thread: '2024-07-14 Mini-AAR for Kamela Fortizar Kill' (1262259553756512299)
-- delta_minutes=840.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1262259553756512299' WHERE id = 673 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=674 start=2024-07-15T23:50:00+00:00
-- thread: '2024-07-15 Productive Night' (1262606514846171168)
-- delta_minutes=710.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1262606514846171168' WHERE id = 674 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=683 start=2024-07-20T20:15:00+00:00
-- thread: '2024-07-20 Skyhook, Line, and Sinker' (1264381859870146611)
-- delta_minutes=495.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1264381859870146611' WHERE id = 683 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=690 start=2024-07-25T00:30:00+00:00
-- thread: '2024-07-24 Structure Defense' (1265853213538521150)
-- delta_minutes=750.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1265853213538521150' WHERE id = 690 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=700 start=2024-07-28T00:45:00+00:00
-- thread: '2024-07-27 Mercenary Contract' (1266966641212657805)
-- delta_minutes=765.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1266966641212657805' WHERE id = 700 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=696 start=2024-07-30T00:00:00+00:00
-- thread: '2024-07-29 Milking, bashing, and crashing' (1267868703618502666)
-- delta_minutes=720.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1267868703618502666' WHERE id = 696 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=697 start=2024-08-02T00:00:00+00:00
-- thread: '2024-08-01 Mommy Milkers' (1268762040294445150)
-- delta_minutes=720.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1268762040294445150' WHERE id = 697 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=707 start=2024-08-03T17:48:00+00:00
-- thread: '2024-08-03 Post Town Hall Shenanigans' (1269375705737855049)
-- delta_minutes=348.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1269375705737855049' WHERE id = 707 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=724 start=2024-08-08T23:30:00+00:00
-- thread: '2024-08-08 Absolute Chickens' (1271281739880202322)
-- delta_minutes=690.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1271281739880202322' WHERE id = 724 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=722 start=2024-08-11T23:00:00+00:00
-- thread: '2024-08-11  Add Rat, Chicken, and a Pinch of Salt. (CTRLV Astra)' (1272641396309758042)
-- delta_minutes=660.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1272641396309758042' WHERE id = 722 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=734 start=2024-08-15T23:20:00+00:00
-- thread: '2024-08-15 Thursday Night Fleet' (1273814657483935895)
-- delta_minutes=680.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1273814657483935895' WHERE id = 734 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=733 start=2024-08-15T21:30:00+00:00
-- thread: '2024-08-15 Krabbing Flash Form?' (1273773800076345405)
-- delta_minutes=570.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1273773800076345405' WHERE id = 733 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=749 start=2024-08-24T01:15:00+00:00
-- thread: '2024-08-23: Friday Drunk FLeeb' (1276745138701471937)
-- delta_minutes=795.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1276745138701471937' WHERE id = 749 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=760 start=2024-08-30T17:00:00+00:00
-- thread: '2024-08-30: Casper am I doing it right?' (1279158410247540836)
-- delta_minutes=300.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1279158410247540836' WHERE id = 760 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=768 start=2024-09-04T00:00:00+00:00
-- thread: '2024-09-03 Kitchen Accident' (1280715355765080196)
-- delta_minutes=720.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1280715355765080196' WHERE id = 768 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=769 start=2024-09-05T00:00:00+00:00
-- thread: '2024-09-05 Buy an amulet set' (1281458450098028674)
-- delta_minutes=720.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1281458450098028674' WHERE id = 769 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=771 start=2024-09-05T17:00:00+00:00
-- thread: '2024-09-05 Milk Fleet 2' (1281328850071982080)
-- delta_minutes=300.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1281328850071982080' WHERE id = 771 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=776 start=2024-09-07T15:49:00+00:00
-- thread: '2024-09-07 Auga Metanox Defense' (1282021188406743061)
-- delta_minutes=229.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1282021188406743061' WHERE id = 776 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=782 start=2024-09-11T01:15:00+00:00
-- thread: '2024-09-10 18th Century Naval Combat' (1283269388207788134)
-- delta_minutes=795.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1283269388207788134' WHERE id = 782 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=778 start=2024-09-12T18:00:00+00:00
-- thread: '2024-09-12 FL33T goes to Poch' (1283887394432487526)
-- delta_minutes=360.0 reason=time-only
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1283887394432487526' WHERE id = 778 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=790 start=2024-09-13T19:00:00+00:00
-- thread: '2024-09-13 FL33T Pochven Dara Boogaloo 2.0' (1284290964126695518)
-- delta_minutes=420.0 reason=time-only
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1284290964126695518' WHERE id = 790 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=797 start=2024-09-18T00:20:00+00:00
-- thread: '2024-09-17 Tornado Third Party' (1285785110767075440)
-- delta_minutes=740.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1285785110767075440' WHERE id = 797 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=793 start=2024-09-18T18:00:00+00:00
-- thread: '2024-09-18 Short and Sweet Pochven 3.0' (1286051641245827082)
-- delta_minutes=360.0 reason=time-only
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1286051641245827082' WHERE id = 793 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=796 start=2024-09-19T00:30:00+00:00
-- thread: "2024-09-18 Knocking on the Dragon's Door" (1286184408524652655)
-- delta_minutes=750.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1286184408524652655' WHERE id = 796 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=800 start=2024-09-20T19:00:00+00:00
-- thread: '2024-09-20 DRAAAAAKKKKEEEEESSSSSSSSSSS' (1286790161203724359)
-- delta_minutes=420.0 reason=time-only
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1286790161203724359' WHERE id = 800 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=799 start=2024-09-21T18:00:00+00:00
-- thread: '2024-09-21 How the fuck do I write an AAR for this (Pochven #4)' (1287144947178278953)
-- delta_minutes=360.0 reason=time-only
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1287144947178278953' WHERE id = 799 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=803 start=2024-09-24T01:26:00+00:00
-- thread: '2024-09-23 Milking in Teneferis' (1287962392206118962)
-- delta_minutes=806.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1287962392206118962' WHERE id = 803 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=804 start=2024-09-25T01:05:00+00:00
-- thread: '2024-09-25 Nobody but us are allowed to kill ZUCK!' (1288333043270029312)
-- delta_minutes=655.0 reason=time-only
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1288333043270029312' WHERE id = 804 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=806 start=2024-09-26T23:45:00+00:00
-- thread: '2024-09-26 EDICT Drills' (1289044687063089162)
-- delta_minutes=705.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1289044687063089162' WHERE id = 806 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=813 start=2024-09-28T17:15:00+00:00
-- thread: '2024-09-28 Congratulations Twan' (1289659292764344320)
-- delta_minutes=315.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1289659292764344320' WHERE id = 813 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=811 start=2024-09-29T13:00:00+00:00
-- thread: '"Chill" "Krabbing" Pochven Fleet' (1289977521940725843)
-- delta_minutes=170.1 reason=time-only
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1289977521940725843' WHERE id = 811 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=819 start=2024-10-06T11:30:00+00:00
-- thread: '2024-10-06 Maryland Renaissance Festival' (1292919943729250334)
-- delta_minutes=30.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1292919943729250334' WHERE id = 819 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=820 start=2024-10-06T17:00:00+00:00
-- thread: '2024-10-06 Rofl Birthday "bash"' (1292914244857364550)
-- delta_minutes=300.0 reason=time-only
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1292914244857364550' WHERE id = 820 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=830 start=2024-10-10T20:00:00+00:00
-- thread: '2024-10-10 Clearing out Kamela' (1294149277160968192)
-- delta_minutes=480.0 reason=time-only
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1294149277160968192' WHERE id = 830 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=833 start=2024-10-13T09:00:00+00:00
-- thread: '2024-10-12 EXIT being casual in AUTZ' (1294735084427022438)
-- delta_minutes=1260.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1294735084427022438' WHERE id = 833 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=832 start=2024-10-12T17:35:00+00:00
-- thread: '2024-10-12 Town Hall Skirmish' (1294750002324967504)
-- delta_minutes=335.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1294750002324967504' WHERE id = 832 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=846 start=2024-10-19T17:00:00+00:00
-- thread: '2024-10-19 Masters of Running Around' (1297297195128590407)
-- delta_minutes=300.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1297297195128590407' WHERE id = 846 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=864 start=2024-10-24T01:00:00+00:00
-- thread: '2024-10-23 Grand Feeding Return - Algos Upgrade fleet' (1298854904944791624)
-- delta_minutes=780.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1298854904944791624' WHERE id = 864 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=856 start=2024-10-25T08:30:00+00:00
-- thread: '2024-10-24 Quiet Night in Poch [Gone wrong] (Dreadfund secured) {Balanced ISK Faucet}' (1298054571784142938)
-- delta_minutes=1230.0 reason=time-only
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1298054571784142938' WHERE id = 856 AND (aar_link IS NULL OR aar_link = '');

-- fleet_id=872 start=2024-10-27T17:45:00+00:00
-- thread: '2024-10-27 PussyX strikes again' (1300202755843162122)
-- delta_minutes=345.0 reason=owner+time
UPDATE fleets_evefleet SET aar_link = 'https://discord.com/channels/1041384161505722368/1300202755843162122' WHERE id = 872 AND (aar_link IS NULL OR aar_link = '');

COMMIT;
