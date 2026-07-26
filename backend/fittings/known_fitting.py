"""Stable catalog keys for fittings the app/guides resolve by meaning."""

from django.db import models


class KnownFitting(models.TextChoices):
    # Navy destroyer metagame guide
    GUIDE_NAVY_DESTROYER_CAT_BLASTER = (
        "guide.navy-destroyer.cat-blaster",
        "Blaster Catalyst Navy Issue",
    )
    GUIDE_NAVY_DESTROYER_CAT_10MN = (
        "guide.navy-destroyer.cat-10mn",
        "10mn Catalyst Navy Issue",
    )
    GUIDE_NAVY_DESTROYER_COERCER_DUAL_NEUTS_MWD = (
        "guide.navy-destroyer.coercer-dual-neuts-mwd",
        "2X Neut Coercer Navy Issue",
    )
    GUIDE_NAVY_DESTROYER_COERCER_MWD_SCRAM_BRAWL = (
        "guide.navy-destroyer.coercer-mwd-scram-brawl",
        "Pulse Coercer Navy Issue",
    )
    GUIDE_NAVY_DESTROYER_COERCER_KITE_BEAMS = (
        "guide.navy-destroyer.coercer-kite-beams",
        "Beam Coercer Navy Issue",
    )
    GUIDE_NAVY_DESTROYER_TFI_AC = (
        "guide.navy-destroyer.tfi-ac",
        "AC Thrasher Fleet Issue",
    )
    GUIDE_NAVY_DESTROYER_TFI_ARTY = (
        "guide.navy-destroyer.tfi-arty",
        "Arty Thrasher Fleet Issue",
    )
    GUIDE_NAVY_DESTROYER_CORM_DUAL_MASB_NEUTRONS = (
        "guide.navy-destroyer.corm-dual-masb-neutrons",
        "Dual MASB Cormorant Navy Issue",
    )
    GUIDE_NAVY_DESTROYER_CORM_BUFFER = (
        "guide.navy-destroyer.corm-buffer",
        "Buffer Cormorant Navy Issue",
    )
    GUIDE_NAVY_DESTROYER_CORM_10MN = (
        "guide.navy-destroyer.corm-10mn",
        "10mn Cormorant Navy Issue",
    )
    GUIDE_NAVY_DESTROYER_TALFI_10MN_ROCKET = (
        "guide.navy-destroyer.talfi-10mn-rocket",
        "10mn Talwar Fleet Issue",
    )
    GUIDE_NAVY_DESTROYER_ALGOS_10MN = (
        "guide.navy-destroyer.algos-10mn",
        "10mn Algos",
    )
    GUIDE_NAVY_DESTROYER_ALGOS_BRAWL = (
        "guide.navy-destroyer.algos-brawl",
        "Brawl Algos",
    )
    GUIDE_NAVY_DESTROYER_ALGOS_FARM = (
        "guide.navy-destroyer.algos-farm",
        "Farm Algos",
    )
    GUIDE_NAVY_DESTROYER_THRASHER_ARTY = (
        "guide.navy-destroyer.thrasher-arty",
        "Arty Thrasher",
    )
    GUIDE_NAVY_DESTROYER_THRASHER_AC = (
        "guide.navy-destroyer.thrasher-ac",
        "AC Thrasher",
    )
    GUIDE_NAVY_DESTROYER_COERCER_BRAWL = (
        "guide.navy-destroyer.coercer-brawl",
        "Brawl Coercer",
    )
    GUIDE_NAVY_DESTROYER_DRAGOON_NEUT = (
        "guide.navy-destroyer.dragoon-neut",
        "Neut Dragoon",
    )

    # Navy frigate guide
    GUIDE_NAVY_FRIGATE_HOOKBILL_SHIELD = (
        "guide.navy-frigate.hookbill-shield",
        "Scram Kite — Shield",
    )
    GUIDE_NAVY_FRIGATE_HOOKBILL_CONTROL = (
        "guide.navy-frigate.hookbill-control",
        "Scram Kite — Control",
    )
    GUIDE_NAVY_FRIGATE_COMET_BLASTER = (
        "guide.navy-frigate.comet-blaster",
        "Blaster Comet",
    )
    GUIDE_NAVY_FRIGATE_COMET_RAIL = (
        "guide.navy-frigate.comet-rail",
        "Rail Comet",
    )
    GUIDE_NAVY_FRIGATE_SLICER_BEAM = (
        "guide.navy-frigate.slicer-beam",
        "Beam Slicer",
    )
    GUIDE_NAVY_FRIGATE_FIRETAIL_ARTY = (
        "guide.navy-frigate.firetail-arty",
        "Arty Firetail",
    )
    GUIDE_NAVY_FRIGATE_VIGIL_WEB_KITE = (
        "guide.navy-frigate.vigil-web-kite",
        "Web Kite Vigil Fleet",
    )
    GUIDE_NAVY_FRIGATE_TRISTAN_BRAWL = (
        "guide.navy-frigate.tristan-brawl",
        "Brawl Tristan",
    )
    GUIDE_NAVY_FRIGATE_BREACHER_MASB = (
        "guide.navy-frigate.breacher-masb",
        "MASB Breacher",
    )

    # Faction warfare cruiser guide
    GUIDE_FW_CRUISER_ARBY_LONG_KITE = (
        "guide.fw-cruiser.arby-long-kite",
        "Long Point Arbitrator",
    )
    GUIDE_FW_CRUISER_ARBY_BRAWL = (
        "guide.fw-cruiser.arby-brawl",
        "Brawl Arbitrator",
    )
    GUIDE_FW_CRUISER_ARBY_TD_SUPPORT = (
        "guide.fw-cruiser.arby-td-support",
        "TD Support Arbitrator",
    )
    GUIDE_FW_CRUISER_AUGNI_POLARIZED = (
        "guide.fw-cruiser.augni-polarized",
        "Polarized Augoror Navy Issue",
    )
    GUIDE_FW_CRUISER_AUGNI_KITE_PULSE = (
        "guide.fw-cruiser.augni-kite-pulse",
        "Pulse Augoror Navy Issue",
    )
    GUIDE_FW_CRUISER_MALLER_PULSE = (
        "guide.fw-cruiser.maller-pulse",
        "Pulse Maller",
    )
    GUIDE_FW_CRUISER_OMEN_QUAD_LIGHT = (
        "guide.fw-cruiser.omen-quad-light",
        "Beam Omen",
    )
    GUIDE_FW_CRUISER_OMEN_KITE_PULSE = (
        "guide.fw-cruiser.omen-kite-pulse",
        "Pulse Omen",
    )
    GUIDE_FW_CRUISER_OMEN_SNIPER = (
        "guide.fw-cruiser.omen-sniper",
        "Sniper Omen",
    )
    GUIDE_FW_CRUISER_OMENNI_MID_KITE = (
        "guide.fw-cruiser.omenni-mid-kite",
        "Kite Omen Navy Issue",
    )
    GUIDE_FW_CRUISER_OMENNI_MID_SNIPER = (
        "guide.fw-cruiser.omenni-mid-sniper",
        "Beam Omen Navy Issue",
    )
    GUIDE_FW_CRUISER_CARACALNI_HAM = (
        "guide.fw-cruiser.caracalni-ham",
        "HAM Caracal Navy Issue",
    )
    GUIDE_FW_CRUISER_OSPREYNI_HAM_NEUT = (
        "guide.fw-cruiser.ospreyni-ham-neut",
        "2X Neut HAM Osprey Navy Issue",
    )
    GUIDE_FW_CRUISER_OSPREYNI_RHML_KITE = (
        "guide.fw-cruiser.ospreyni-rhml-kite",
        "RLML Osprey Navy Issue",
    )
    GUIDE_FW_CRUISER_ENI_BLASTER = (
        "guide.fw-cruiser.eni-blaster",
        "Blaster Exequror Navy Issue",
    )
    GUIDE_FW_CRUISER_ENI_250RAIL = (
        "guide.fw-cruiser.eni-250rail",
        "250mm Rail Exequror Navy Issue",
    )
    GUIDE_FW_CRUISER_ENI_DUAL_PLATE_ELECTRON = (
        "guide.fw-cruiser.eni-dual-plate-electron",
        "Dual Plate Electron Exequror Navy Issue",
    )
    GUIDE_FW_CRUISER_VEXOR_NEUT_PLATE = (
        "guide.fw-cruiser.vexor-neut-plate",
        "Neut Vexor",
    )
    GUIDE_FW_CRUISER_VEXOR_BLASTER_NEUT = (
        "guide.fw-cruiser.vexor-blaster-neut",
        "Blaster Vexor",
    )
    GUIDE_FW_CRUISER_VNI_DUAL_REP = (
        "guide.fw-cruiser.vni-dual-rep",
        "Dual Rep Vexor Navy Issue",
    )
    GUIDE_FW_CRUISER_BELLICOSE_HAM = (
        "guide.fw-cruiser.bellicose-ham",
        "HAM Bellicose",
    )
    GUIDE_FW_CRUISER_BELLICOSE_XLSB = (
        "guide.fw-cruiser.bellicose-xlsb",
        "XLASB HAM Bellicose",
    )
    GUIDE_FW_CRUISER_SCYTHEFI_DUAL_PROP_AC = (
        "guide.fw-cruiser.scythefi-dual-prop-ac",
        "Dual Prop Scythe Fleet Issue",
    )
    GUIDE_FW_CRUISER_SCYTHEFI_RLML_ARMOR = (
        "guide.fw-cruiser.scythefi-rlml-armor",
        "Armor RLML Scythe Fleet Issue",
    )
    GUIDE_FW_CRUISER_SCYTHEFI_RLML_XLSB = (
        "guide.fw-cruiser.scythefi-rlml-xlsb",
        "RLML XLASB Scythe Fleet Issue",
    )
    GUIDE_FW_CRUISER_STABBER_XLSB = (
        "guide.fw-cruiser.stabber-xlsb",
        "AB XLASB Stabber",
    )
    GUIDE_FW_CRUISER_STABBER_VULCAN_KITE = (
        "guide.fw-cruiser.stabber-vulcan-kite",
        "Vulcan Stabber",
    )
    GUIDE_FW_CRUISER_STABBERFI_DUAL_PROP = (
        "guide.fw-cruiser.stabberfi-dual-prop",
        "Dual Prop Stabber Fleet Issue",
    )
