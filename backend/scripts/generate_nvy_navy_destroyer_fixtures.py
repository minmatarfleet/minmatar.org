"""Generate NVY navy destroyer metagame fixture entries."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

TIMESTAMP = "2026-06-21T12:00:00.000Z"
START_PK = 362

SHIPS = {
    "Catalyst Navy Issue": 73796,
    "Coercer Navy Issue": 73789,
    "Thrasher Fleet Issue": 73794,
    "Cormorant Navy Issue": 73795,
}

TAGS = ["faction_warfare", "solo"]

CARGO = {
    "blaster": (
        "Null S x2500\r\n"
        "Void S x5000\r\n"
        "Caldari Navy Antimatter Charge S x1000\r\n"
        "Nanite Repair Paste x50"
    ),
    "rail": (
        "Caldari Navy Antimatter Charge S x2000\r\n"
        "Caldari Navy Iridium Charge S x2000\r\n"
        "Caldari Navy Iron Charge S x2000\r\n"
        "Caldari Navy Thorium Charge S x2000\r\n"
        "Nanite Repair Paste x120"
    ),
    "pulse": (
        "Conflagration S x5\r\n"
        "Scorch S x5\r\n"
        "Imperial Navy Multifrequency S x5\r\n"
        "Nanite Repair Paste x50"
    ),
    "beam": (
        "Conflagration S x5\r\n"
        "Imperial Navy Multifrequency S x5\r\n"
        "Scorch S x5\r\n"
        "Nanite Repair Paste x50"
    ),
    "artillery": (
        "Quake S x1500\r\n"
        "Tremor S x1500\r\n"
        "Nanite Repair Paste x50\r\n"
        "Republic Fleet Depleted Uranium S x1000\r\n"
        "Republic Fleet EMP S x1000\r\n"
        "Republic Fleet Fusion S x1000\r\n"
        "Republic Fleet Phased Plasma S x1000"
    ),
    "ac": (
        "Barrage S x2500\r\n"
        "Hail S x5000\r\n"
        "Inferno Rage Rocket x1000\r\n"
        "Nanite Repair Paste x50\r\n"
        "Republic Fleet Depleted Uranium S x1000\r\n"
        "Republic Fleet EMP S x1000\r\n"
        "Republic Fleet Phased Plasma S x1000"
    ),
    "ac_shield": (
        "Barrage S x2500\r\n"
        "Hail S x5000\r\n"
        "Nanite Repair Paste x50\r\n"
        "Republic Fleet Depleted Uranium S x1000\r\n"
        "Republic Fleet EMP S x1000\r\n"
        "Republic Fleet Phased Plasma S x1000"
    ),
    "masb": (
        "Null S x2500\r\n"
        "Void S x5000\r\n"
        "Caldari Navy Antimatter Charge S x1000\r\n"
        "Nanite Repair Paste x100\r\n"
        "Navy Cap Booster 400 x25"
    ),
    "masb_ion": (
        "Null S x2500\r\n"
        "Void S x5000\r\n"
        "Caldari Navy Antimatter Charge S x1000\r\n"
        "Nanite Repair Paste x100\r\n"
        "Navy Cap Booster 400 x25"
    ),
    "buffer": (
        "Null S x2500\r\n"
        "Void S x5000\r\n"
        "Caldari Navy Antimatter Charge S x1000\r\n"
        "Nanite Repair Paste x50"
    ),
    "10mn_rail": (
        "Caldari Navy Antimatter Charge S x2000\r\n"
        "Caldari Navy Iridium Charge S x2000\r\n"
        "Caldari Navy Iron Charge S x2000\r\n"
        "Caldari Navy Thorium Charge S x2000\r\n"
        "Nanite Repair Paste x120\r\n"
        "Navy Cap Booster 400 x25"
    ),
}


def build_eft(ship: str, fit_name: str, low, mid, high, rigs, cargo_key: str) -> str:
    lines = [f"[{ship}, {fit_name}]", ""]
    lines.extend(low)
    lines.append("")
    lines.extend(mid)
    lines.append("")
    lines.extend(high)
    lines.append("")
    lines.extend(rigs)
    lines.extend(["", "", CARGO[cargo_key]])
    return "\r\n".join(lines)


FITS = [
    {
        "ship": "Catalyst Navy Issue",
        "slug": "plate-web-scram",
        "description": (
            "Versatile blaster brawler with armor plate, web, and scram. "
            "High buffer EHP wins most close-range destroyer scram fights; "
            "very weak to anything that can kite."
        ),
        "cargo": "blaster",
        "low": [
            "Damage Control II",
            "400mm Rolled Tungsten Compact Plates",
            "Vortex Compact Magnetic Field Stabilizer",
        ],
        "mid": [
            "5MN Y-T8 Compact Microwarpdrive",
            "Warp Scrambler II",
            "Fleeting Compact Stasis Webifier",
        ],
        "high": [
            "Light Neutron Blaster II",
            "Light Neutron Blaster II",
            "Light Neutron Blaster II",
            "[Empty High slot]",
            "Light Neutron Blaster II",
            "Light Neutron Blaster II",
            "Light Neutron Blaster II",
        ],
        "rig": [
            "Small Transverse Bulkhead II",
            "Small Transverse Bulkhead II",
            "Small Transverse Bulkhead II",
        ],
    },
    {
        "ship": "Catalyst Navy Issue",
        "slug": "saar-web-scram",
        "description": (
            "Active armor blaster brawler using a SAAR and nosferatu for sustain. "
            "More flexible than the plate variant but with a thinner buffer; "
            "still beats most destroyers you can land scram and web on."
        ),
        "cargo": "blaster",
        "low": [
            "Small Ancillary Armor Repairer",
            "Damage Control II",
            "Vortex Compact Magnetic Field Stabilizer",
        ],
        "mid": [
            "5MN Y-T8 Compact Microwarpdrive",
            "Warp Scrambler II",
            "Fleeting Compact Stasis Webifier",
        ],
        "high": [
            "Light Neutron Blaster II",
            "Light Neutron Blaster II",
            "Light Neutron Blaster II",
            "Small Ghoul Compact Energy Nosferatu",
            "Light Neutron Blaster II",
            "Light Neutron Blaster II",
            "Light Neutron Blaster II",
        ],
        "rig": [
            "Small Transverse Bulkhead II",
            "Small Transverse Bulkhead II",
            "Small Transverse Bulkhead II",
        ],
    },
    {
        "ship": "Catalyst Navy Issue",
        "slug": "10mn-150mm",
        "description": (
            "10MN afterburner rail kiter with 150mm gauss guns. "
            "Slippery scram-kite fit that controls range against other destroyers; "
            "over-propped, so turn on prey early and avoid slingshots."
        ),
        "cargo": "rail",
        "low": [
            "Damage Control II",
            "Vortex Compact Magnetic Field Stabilizer",
            "Small Ancillary Armor Repairer",
        ],
        "mid": [
            "10MN Y-S8 Compact Afterburner",
            "Fleeting Compact Stasis Webifier",
            "Faint Scoped Warp Disruptor",
        ],
        "high": [
            "150mm Prototype Gauss Gun",
            "150mm Prototype Gauss Gun",
            "150mm Prototype Gauss Gun",
            "[Empty High slot]",
            "150mm Prototype Gauss Gun",
            "150mm Prototype Gauss Gun",
            "150mm Prototype Gauss Gun",
        ],
        "rig": [
            "Small Transverse Bulkhead II",
            "Small Transverse Bulkhead II",
            "Small Transverse Bulkhead II",
        ],
    },
    {
        "ship": "Catalyst Navy Issue",
        "slug": "10mn-125mm",
        "description": (
            "Faster 10MN rail kiter with T2 125mm rails and a disruptor. "
            "Even harder to catch than the 150mm variant but with lower raw DPS; "
            "excellent for picking destroyer fights on your terms."
        ),
        "cargo": "rail",
        "low": [
            "Damage Control II",
            "Magnetic Field Stabilizer II",
            "Small Ancillary Armor Repairer",
        ],
        "mid": [
            "10MN Monopropellant Enduring Afterburner",
            "X5 Enduring Stasis Webifier",
            "Warp Disruptor II",
        ],
        "high": [
            "125mm Railgun II",
            "125mm Railgun II",
            "125mm Railgun II",
            "[Empty High slot]",
            "125mm Railgun II",
            "125mm Railgun II",
            "125mm Railgun II",
        ],
        "rig": [
            "Small Transverse Bulkhead II",
            "Small Transverse Bulkhead II",
            "Small Transverse Bulkhead II",
        ],
    },
    {
        "ship": "Coercer Navy Issue",
        "slug": "dual-neuts-mwd",
        "description": (
            "Classic dual neut brawler with MWD. "
            "Leverages the hull neut bonus to drain cap-reliant targets, "
            "then grind them down at scram range. Beware kiters and capless guns."
        ),
        "cargo": "pulse",
        "low": [
            "400mm Rolled Tungsten Compact Plates",
            "Damage Control II",
            "Heat Sink II",
            "Multispectrum Energized Membrane II",
        ],
        "mid": [
            "5MN Y-T8 Compact Microwarpdrive",
            "Faint Epsilon Scoped Warp Scrambler",
        ],
        "high": [
            "Dual Light Pulse Laser II",
            "Dual Light Pulse Laser II",
            "Dual Light Pulse Laser II",
            "Small Infectious Scoped Energy Neutralizer",
            "Small Infectious Scoped Energy Neutralizer",
            "Dual Light Pulse Laser II",
            "Dual Light Pulse Laser II",
        ],
        "rig": [
            "Small Ancillary Current Router I",
            "Small Trimark Armor Pump I",
            "Small Trimark Armor Pump I",
        ],
    },
    {
        "ship": "Coercer Navy Issue",
        "slug": "dual-neuts-no-prop",
        "description": (
            "Slow brawler with dual neuts, web, and no prop mod. "
            "Trades mobility for more tank and control at scram range; "
            "ideal when you expect a straight brawl rather than a chase."
        ),
        "cargo": "pulse",
        "low": [
            "400mm Rolled Tungsten Compact Plates",
            "Damage Control II",
            "Heat Sink II",
            "Multispectrum Coating II",
        ],
        "mid": [
            "Faint Epsilon Scoped Warp Scrambler",
            "Fleeting Compact Stasis Webifier",
        ],
        "high": [
            "Small Focused Pulse Laser II",
            "Small Focused Pulse Laser II",
            "Small Focused Pulse Laser II",
            "Small Energy Neutralizer II",
            "Small Infectious Scoped Energy Neutralizer",
            "Small Focused Pulse Laser II",
            "Small Focused Pulse Laser II",
        ],
        "rig": [
            "Small Ancillary Current Router II",
            "Small Trimark Armor Pump I",
            "Small Energy Locus Coordinator II",
        ],
    },
    {
        "ship": "Coercer Navy Issue",
        "slug": "ab-scram-brawl",
        "description": (
            "Afterburner pulse brawler for tighter range control without MWD signature penalty. "
            "Full dual-pulse rack with a neut for cap warfare in straight scram brawls."
        ),
        "cargo": "pulse",
        "low": [
            "Damage Control II",
            "Multispectrum Energized Membrane II",
            "400mm Rolled Tungsten Compact Plates",
            "Heat Sink II",
        ],
        "mid": ["1MN Afterburner II", "Warp Scrambler II"],
        "high": [
            "Dual Light Pulse Laser II",
            "Dual Light Pulse Laser II",
            "Dual Light Pulse Laser II",
            "Small Infectious Scoped Energy Neutralizer",
            "Dual Light Pulse Laser II",
            "Dual Light Pulse Laser II",
            "Dual Light Pulse Laser II",
        ],
        "rig": [
            "Small Trimark Armor Pump I",
            "Small Trimark Armor Pump I",
            "Small Trimark Armor Pump I",
        ],
    },
    {
        "ship": "Coercer Navy Issue",
        "slug": "mwd-scram-brawl",
        "description": (
            "Focused pulse MWD brawler with a full gun rack and no neut. "
            "Pure scram-range DPS for pilots who want to close quickly and brawl."
        ),
        "cargo": "pulse",
        "low": [
            "200mm Steel Plates II",
            "Heat Sink II",
            "Multispectrum Coating II",
            "Multispectrum Energized Membrane II",
        ],
        "mid": ["5MN Quad LiF Restrained Microwarpdrive", "Warp Scrambler II"],
        "high": [
            "Small Focused Pulse Laser II",
            "Small Focused Pulse Laser II",
            "Small Focused Pulse Laser II",
            "[Empty High slot]",
            "Small Focused Pulse Laser II",
            "Small Focused Pulse Laser II",
            "Small Focused Pulse Laser II",
        ],
        "rig": [
            "Small Trimark Armor Pump I",
            "Small Trimark Armor Pump I",
            "Small Trimark Armor Pump I",
        ],
    },
    {
        "ship": "Coercer Navy Issue",
        "slug": "locus-pulse",
        "description": (
            "Locus coordinator pulse kiter with SAAR for mid-range pressure. "
            "Uses tracking and the hull's neut-adjacent slot layout to fight "
            "at pulse falloff while staying mobile."
        ),
        "cargo": "pulse",
        "low": [
            "Heat Sink II",
            "Extruded Compact Heat Sink",
            "Damage Control II",
            "Small Ancillary Armor Repairer",
        ],
        "mid": [
            "5MN Y-T8 Compact Microwarpdrive",
            "Initiated Compact Warp Disruptor",
        ],
        "high": [
            "Small Focused Pulse Laser II",
            "Small Focused Pulse Laser II",
            "Small Focused Pulse Laser II",
            "[Empty High slot]",
            "Small Focused Pulse Laser II",
            "Small Focused Pulse Laser II",
            "Small Focused Pulse Laser II",
        ],
        "rig": [
            "Small Transverse Bulkhead II",
            "Small Energy Locus Coordinator II",
            "Small Energy Locus Coordinator II",
        ],
    },
    {
        "ship": "Coercer Navy Issue",
        "slug": "kite-beams",
        "description": (
            "Beam kiter with tracking enhancer for fighting near falloff. "
            "Keeps range with MWD and disruptor while applying steady beam DPS "
            "to slower brawlers and other kiters."
        ),
        "cargo": "beam",
        "low": [
            "Heat Sink II",
            "Extruded Compact Heat Sink",
            "Damage Control II",
            "Fourier Compact Tracking Enhancer",
        ],
        "mid": [
            "5MN Y-T8 Compact Microwarpdrive",
            "Initiated Compact Warp Disruptor",
        ],
        "high": [
            "Small Focused Beam Laser II",
            "Small Focused Beam Laser II",
            "Small Focused Beam Laser II",
            "[Empty High slot]",
            "Small Focused Beam Laser II",
            "Small Focused Beam Laser II",
            "Small Focused Beam Laser II",
        ],
        "rig": [
            "Small Processor Overclocking Unit II",
            "Small Transverse Bulkhead I",
            "Small Transverse Bulkhead I",
        ],
    },
    {
        "ship": "Coercer Navy Issue",
        "slug": "web-beams",
        "description": (
            "Double-web beam fit for catching other kiters and holding them in beam range. "
            "A niche meme build that punishes pilots who assume every Coercer is a neut brawler."
        ),
        "cargo": "beam",
        "low": [
            "Heat Sink II",
            "Heat Sink II",
            "Damage Control II",
            "Fourier Compact Tracking Enhancer",
        ],
        "mid": ["Stasis Webifier II", "Fleeting Compact Stasis Webifier"],
        "high": [
            "Small Focused Beam Laser II",
            "Small Focused Beam Laser II",
            "Small Focused Beam Laser II",
            "[Empty High slot]",
            "Small Focused Beam Laser II",
            "Small Focused Beam Laser II",
            "Small Focused Beam Laser II",
        ],
        "rig": [
            "Small Processor Overclocking Unit II",
            "Small Transverse Bulkhead I",
            "Small Transverse Bulkhead I",
        ],
    },
    {
        "ship": "Thrasher Fleet Issue",
        "slug": "280mm-acr",
        "description": (
            "Standard 280mm artillery kiter with collision accelerator for alpha and range control. "
            "Excellent for fighting on your terms; if you get tackled, you die."
        ),
        "cargo": "artillery",
        "low": [
            "Gyrostabilizer II",
            "Counterbalanced Compact Gyrostabilizer",
            "IFFA Compact Damage Control",
        ],
        "mid": [
            "5MN Y-T8 Compact Microwarpdrive",
            "Fleeting Compact Stasis Webifier",
            "Initiated Compact Warp Disruptor",
        ],
        "high": [
            "280mm Howitzer Artillery II",
            "280mm Howitzer Artillery II",
            "280mm Howitzer Artillery II",
            "[Empty High slot]",
            "280mm Howitzer Artillery II",
            "280mm Howitzer Artillery II",
            "280mm Howitzer Artillery II",
        ],
        "rig": [
            "Small Transverse Bulkhead II",
            "Small Projectile Collision Accelerator I",
            "Small Ancillary Current Router I",
        ],
    },
    {
        "ship": "Thrasher Fleet Issue",
        "slug": "280-overdrive",
        "description": (
            "Simpler overdrive artillery kiter with more speed and less alpha than the ACR variant. "
            "Good entry 280mm fit for pilots learning Thrasher Fleet Issue kiting."
        ),
        "cargo": "artillery",
        "low": [
            "Gyrostabilizer II",
            "Overdrive Injector System II",
            "Damage Control II",
        ],
        "mid": [
            "5MN Y-T8 Compact Microwarpdrive",
            "Fleeting Compact Stasis Webifier",
            "Warp Disruptor II",
        ],
        "high": [
            "280mm Howitzer Artillery II",
            "280mm Howitzer Artillery II",
            "280mm Howitzer Artillery II",
            "[Empty High slot]",
            "280mm Howitzer Artillery II",
            "280mm Howitzer Artillery II",
            "280mm Howitzer Artillery II",
        ],
        "rig": [
            "Small Transverse Bulkhead II",
            "Small Transverse Bulkhead II",
            "Small Transverse Bulkhead II",
        ],
    },
    {
        "ship": "Thrasher Fleet Issue",
        "slug": "armour-acs",
        "description": (
            "Armor autocannon brawler with a rocket launcher for close-range brawling. "
            "Scram, web, and MWD into range then tear down other destroyers with AC alpha."
        ),
        "cargo": "ac",
        "low": [
            "Damage Control II",
            "Gyrostabilizer II",
            "400mm Crystalline Carbonide Restrained Plates",
        ],
        "mid": [
            "Warp Scrambler II",
            "Fleeting Compact Stasis Webifier",
            "5MN Quad LiF Restrained Microwarpdrive",
        ],
        "high": [
            "200mm AutoCannon II",
            "200mm AutoCannon II",
            "200mm AutoCannon II",
            "Rocket Launcher II",
            "200mm AutoCannon II",
            "200mm AutoCannon II",
            "200mm AutoCannon II",
        ],
        "rig": [
            "Small Trimark Armor Pump I",
            "Small Trimark Armor Pump I",
            "Small Projectile Burst Aerator II",
        ],
    },
    {
        "ship": "Thrasher Fleet Issue",
        "slug": "shield-acs",
        "description": (
            "Shield autocannon brawler with a neut for cap-dependent targets at scram range. "
            "More speed and buffer than the armor AC variant; trades some EHP for mobility."
        ),
        "cargo": "ac_shield",
        "low": [
            "Gyrostabilizer II",
            "Gyrostabilizer II",
            "IFFA Compact Damage Control",
        ],
        "mid": [
            "5MN Quad LiF Restrained Microwarpdrive",
            "Republic Fleet Medium Shield Extender",
            "Warp Scrambler II",
        ],
        "high": [
            "200mm AutoCannon II",
            "200mm AutoCannon II",
            "200mm AutoCannon II",
            "Small Energy Neutralizer II",
            "200mm AutoCannon II",
            "200mm AutoCannon II",
            "200mm AutoCannon II",
        ],
        "rig": [
            "Small Core Defense Field Extender I",
            "Small EM Shield Reinforcer II",
            "Small Thermal Shield Reinforcer II",
        ],
    },
    {
        "ship": "Thrasher Fleet Issue",
        "slug": "280-double-web",
        "description": (
            "Dual-web afterburner arty fit for catching kiters and controlling range at artillery optimal. "
            "A meme build that turns the tables on other 280mm kiters who rely on keeping you at range."
        ),
        "cargo": "artillery",
        "low": [
            "Damage Control II",
            "Gyrostabilizer II",
            "Gyrostabilizer II",
        ],
        "mid": [
            "1MN Afterburner II",
            "Fleeting Compact Stasis Webifier",
            "Fleeting Compact Stasis Webifier",
        ],
        "high": [
            "280mm Howitzer Artillery II",
            "280mm Howitzer Artillery II",
            "280mm Howitzer Artillery II",
            "[Empty High slot]",
            "280mm Howitzer Artillery II",
            "280mm Howitzer Artillery II",
            "280mm Howitzer Artillery II",
        ],
        "rig": [
            "Small Transverse Bulkhead II",
            "Small Transverse Bulkhead II",
            "Small Transverse Bulkhead II",
        ],
    },
    {
        "ship": "Cormorant Navy Issue",
        "slug": "dual-masb-neutrons",
        "description": (
            "Dual MASB neutron brawler with burst shield tank for winning scram brawls. "
            "Pulses XLASB charges and overheats to outlast other destroyers at close range."
        ),
        "cargo": "masb",
        "low": [
            "IFFA Compact Damage Control",
            "Vortex Compact Magnetic Field Stabilizer",
        ],
        "mid": [
            "1MN Y-S8 Compact Afterburner",
            "Initiated Compact Warp Scrambler",
            "Medium Ancillary Shield Booster",
            "Medium Ancillary Shield Booster",
        ],
        "high": [
            "Light Neutron Blaster II",
            "Light Neutron Blaster II",
            "Light Neutron Blaster II",
            "[Empty High slot]",
            "Light Neutron Blaster II",
            "Light Neutron Blaster II",
            "Light Neutron Blaster II",
        ],
        "rig": [
            "Small EM Shield Reinforcer I",
            "Small Hybrid Burst Aerator II",
            "Small Thermal Shield Reinforcer I",
        ],
    },
    {
        "ship": "Cormorant Navy Issue",
        "slug": "dual-masb-ions",
        "description": (
            "Dual MASB ion blaster brawler with slightly longer reach than the neutron variant. "
            "Same burst-shield brawl concept for pilots who prefer ion range and tracking tradeoffs."
        ),
        "cargo": "masb_ion",
        "low": ["Damage Control II", "Magnetic Field Stabilizer II"],
        "mid": [
            "1MN Afterburner II",
            "Warp Scrambler II",
            "Medium Ancillary Shield Booster",
            "Medium Ancillary Shield Booster",
        ],
        "high": [
            "Light Ion Blaster II",
            "Light Ion Blaster II",
            "Light Ion Blaster II",
            "[Empty High slot]",
            "Light Ion Blaster II",
            "Light Ion Blaster II",
            "Light Ion Blaster II",
        ],
        "rig": [
            "Small EM Shield Reinforcer I",
            "Small Hybrid Burst Aerator II",
            "Small Thermal Shield Reinforcer I",
        ],
    },
    {
        "ship": "Cormorant Navy Issue",
        "slug": "buffer",
        "description": (
            "Surprise MWD buffer fit with a Republic Fleet medium shield extender. "
            "Looks like a kiter until you scram and brawl with strong shield buffer and blaster DPS."
        ),
        "cargo": "buffer",
        "low": ["Magnetic Field Stabilizer II", "Damage Control II"],
        "mid": [
            "5MN Y-T8 Compact Microwarpdrive",
            "Republic Fleet Medium Shield Extender",
            "Stasis Webifier II",
            "Warp Scrambler II",
        ],
        "high": [
            "Light Neutron Blaster II",
            "Light Neutron Blaster II",
            "Light Neutron Blaster II",
            "[Empty High slot]",
            "Light Neutron Blaster II",
            "Light Neutron Blaster II",
            "Light Neutron Blaster II",
        ],
        "rig": [
            "Small Core Defense Field Extender I",
            "Small EM Shield Reinforcer II",
            "Small Hybrid Burst Aerator I",
        ],
    },
    {
        "ship": "Cormorant Navy Issue",
        "slug": "10mn",
        "description": (
            "10MN rail scram-kite with cap booster and shield booster for sustained mid-range pressure. "
            "Uses 75mm rails to control range while staying under scram and applying steady DPS."
        ),
        "cargo": "10mn_rail",
        "low": ["Damage Control II", "Magnetic Field Stabilizer II"],
        "mid": [
            "10MN Afterburner II",
            "Warp Scrambler II",
            "Small Capacitor Booster II",
            "Pithum C-Type Medium Shield Booster",
        ],
        "high": [
            "75mm Gatling Rail II",
            "75mm Gatling Rail II",
            "75mm Gatling Rail II",
            "[Empty High slot]",
            "75mm Gatling Rail II",
            "75mm Gatling Rail II",
            "75mm Gatling Rail II",
        ],
        "rig": [
            "Small EM Shield Reinforcer II",
            "Small Hybrid Collision Accelerator I",
            "Small Thermal Shield Reinforcer II",
        ],
    },
]


def main() -> None:
    rows = []
    for index, fit in enumerate(FITS):
        ship = fit["ship"]
        fit_name = f"[NVY] {ship} — {fit['slug']}"
        eft = build_eft(
            ship,
            fit_name,
            fit["low"],
            fit["mid"],
            fit["high"],
            fit["rig"],
            fit["cargo"],
        )
        rows.append(
            {
                "model": "fittings.evefitting",
                "pk": START_PK + index,
                "fields": {
                    "deleted": None,
                    "deleted_by_cascade": False,
                    "name": fit_name,
                    "ship_id": SHIPS[ship],
                    "created_at": TIMESTAMP,
                    "updated_at": TIMESTAMP,
                    "description": fit["description"],
                    "aliases": "",
                    "eft_format": eft,
                    "latest_version": str(uuid.uuid4()),
                    "minimum_pod": "",
                    "recommended_pod": "",
                    "tags": TAGS,
                },
            }
        )

    out = Path(__file__).resolve().parents[1] / "fixtures/data/09_nvy_navy_destroyer_fittings.json"
    out.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(rows)} fittings to {out}")


if __name__ == "__main__":
    main()
