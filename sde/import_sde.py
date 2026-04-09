import argparse
import io
import json
from pathlib import Path
import sqlite3
import sys
import urllib.request
import zipfile

# Mapping from JSONL file names to table names (based on EVE SDE conventions)
table_mapping = {
    "agentsInSpace": "agtAgentsInSpace",
    "agentTypes": "agtAgentTypes",
    "ancestries": "chrAncestries",
    "bloodlines": "chrBloodlines",
    "blueprints": "industryBlueprints",
    "categories": "invCategories",
    "certificates": "chrCertificates",
    "characterAttributes": "chrAttributes",
    "cloneGrades": "chrCloneGrades",
    "compressibleTypes": "invCompressibleTypes",
    "corporationActivities": "crpActivities",
    "dbuffCollections": "dbuffCollections",
    "dogmaAttributeCategories": "dgmAttributeCategories",
    "dogmaAttributes": "dgmAttributeTypes",
    "dogmaEffects": "dgmEffects",
    "dogmaUnits": "eveUnits",
    "dynamicItemAttributes": "invDynamicItemAttributes",
    "factions": "chrFactions",
    "graphics": "eveGraphics",
    "groups": "invGroups",
    "icons": "eveIcons",
    "landmarks": "mapLandmarks",
    "mapAsteroidBelts": "mapAsteroidBelts",
    "mapConstellations": "mapConstellations",
    "mapMoons": "mapMoons",
    "mapPlanets": "mapPlanets",
    "mapRegions": "mapRegions",
    "mapSecondarySuns": "mapSecondarySuns",
    "mapSolarSystems": "mapSolarSystems",
    "mapStargates": "mapStargates",
    "mapStars": "mapStars",
    "marketGroups": "invMarketGroups",
    "masteries": "chrMasteries",
    "mercenaryTacticalOperations": "mercenaryTacticalOperations",
    "metaGroups": "invMetaGroups",
    "npcCharacters": "chrNPCCharacters",
    "npcCorporationDivisions": "crpNPCDivisions",
    "npcCorporations": "crpNPCCorporations",
    "npcStations": "staStations",
    "planetResources": "planetResources",
    "planetSchematics": "planetSchematics",
    "races": "chrRaces",
    "skinLicenses": "skinLicense",
    "skinMaterials": "skinMaterials",
    "skins": "skins",
    "sovereigntyUpgrades": "sovUpgrades",
    "stationOperations": "staOperations",
    "stationServices": "staServices",
    "translationLanguages": "translationLanguages",
    "typeBonus": "invTypeBonus",
    "typeDogma": "invTypeDogma",
    "types": "invTypes",
}

# Derived tables extracted from nested fields within source JSONL files.
# Each entry maps a new table name to its extraction config:
#   source        - JSONL filename (without .jsonl)
#   field         - the nested field to extract from each row
#   parent_fields - dict of {source_field: output_column} to carry from the parent row
#   renames       - optional dict of {child_field: output_column} renames
#   filter        - optional parent field that must be truthy for the row to be included
#   scalar_name   - for list-of-scalars: wraps each value into {scalar_name: value}
#   drop          - optional list of child fields to exclude from the output
derived_tables = {
    "agtAgents": {
        "source": "npcCharacters",
        "field": "agent",
        "parent_fields": {
            "_key": "agentID",
            "corporationID": "corporationID",
            "locationID": "locationID",
        },
    },
    "agtResearchAgents": {
        "source": "npcCharacters",
        "field": "skills",
        "parent_fields": {"_key": "agentID"},
        "filter": "agent",
    },
    "dgmTypeAttributes": {
        "source": "typeDogma",
        "field": "dogmaAttributes",
        "parent_fields": {"_key": "typeID"},
    },
    "dgmTypeEffects": {
        "source": "typeDogma",
        "field": "dogmaEffects",
        "parent_fields": {"_key": "typeID"},
    },
    "invTypeMaterials": {
        "source": "typeMaterials",
        "field": "materials",
        "parent_fields": {"_key": "typeID"},
    },
    "invContrabandTypes": {
        "source": "contrabandTypes",
        "field": "factions",
        "parent_fields": {"_key": "typeID"},
        "renames": {"_key": "factionID"},
    },
    "invControlTowerResources": {
        "source": "controlTowerResources",
        "field": "resources",
        "parent_fields": {"_key": "controlTowerTypeID"},
    },
    "crpNPCCorporationDivisions": {
        "source": "npcCorporations",
        "field": "divisions",
        "parent_fields": {"_key": "corporationID"},
        "renames": {"_key": "divisionID"},
        "drop": ["divisionNumber", "leaderID"],
    },
    "crpNPCCorporationTrades": {
        "source": "npcCorporations",
        "field": "corporationTrades",
        "parent_fields": {"_key": "corporationID"},
        "renames": {"_key": "typeID"},
        "drop": ["_value"],
    },
    "planetSchematicsTypeMap": {
        "source": "planetSchematics",
        "field": "types",
        "parent_fields": {"_key": "schematicID"},
        "renames": {"_key": "typeID"},
    },
    "planetSchematicsPinMap": {
        "source": "planetSchematics",
        "field": "pins",
        "parent_fields": {"_key": "schematicID"},
        "scalar_name": "pinTypeID",
    },
    "staOperationServices": {
        "source": "stationOperations",
        "field": "services",
        "parent_fields": {"_key": "operationID"},
        "scalar_name": "serviceID",
    },
    "skinShip": {
        "source": "skins",
        "field": "types",
        "parent_fields": {"_key": "skinID"},
        "scalar_name": "typeID",
    },
    "sovUpgradeFuels": {
        "source": "sovereigntyUpgrades",
        "field": "fuel",
        "parent_fields": {"_key": "upgradeID"},
        "renames": {
            "hourly_upkeep": "hourlyUpkeep",
            "startup_cost": "startupCost",
            "type_id": "fuelTypeID",
        },
    },
    "chrFactionRaces": {
        "source": "factions",
        "field": "memberRaces",
        "parent_fields": {"_key": "factionID"},
        "scalar_name": "raceID",
    },
    "chrCloneGradeSkills": {
        "source": "cloneGrades",
        "field": "skills",
        "parent_fields": {"_key": "gradeID"},
    },
    "chrRaceSkills": {
        "source": "races",
        "field": "skills",
        "parent_fields": {"_key": "raceID"},
        "renames": {"_key": "skillTypeID", "_value": "level"},
    },
    "crpNPCCorporationRaces": {
        "source": "npcCorporations",
        "field": "allowedMemberRaces",
        "parent_fields": {"_key": "corporationID"},
        "scalar_name": "raceID",
    },
    "crpNPCCorporationLPOfferTables": {
        "source": "npcCorporations",
        "field": "lpOfferTables",
        "parent_fields": {"_key": "corporationID"},
        "scalar_name": "offerTableID",
    },
    "crpNPCCorporationExchangeRates": {
        "source": "npcCorporations",
        "field": "exchangeRates",
        "parent_fields": {"_key": "corporationID"},
        "renames": {"_key": "targetCorporationID", "_value": "rate"},
    },
    "invDynamicItemAttributeRanges": {
        "source": "dynamicItemAttributes",
        "field": "attributeIDs",
        "parent_fields": {"_key": "typeID"},
        "renames": {"_key": "attributeID"},
    },
    "invDynamicItemInputOutput": {
        "source": "dynamicItemAttributes",
        "field": "inputOutputMapping",
        "parent_fields": {"_key": "typeID"},
    },
    "staOperationStationTypes": {
        "source": "stationOperations",
        "field": "stationTypes",
        "parent_fields": {"_key": "operationID"},
        "renames": {"_key": "raceID", "_value": "stationTypeID"},
    },
    "mapMoonStations": {
        "source": "mapMoons",
        "field": "npcStationIDs",
        "parent_fields": {"_key": "celestialID"},
        "scalar_name": "stationID",
    },
    "mapPlanetAsteroidBelts": {
        "source": "mapPlanets",
        "field": "asteroidBeltIDs",
        "parent_fields": {"_key": "celestialID"},
        "scalar_name": "asteroidBeltID",
    },
    "mapPlanetMoons": {
        "source": "mapPlanets",
        "field": "moonIDs",
        "parent_fields": {"_key": "celestialID"},
        "scalar_name": "moonID",
    },
    "mapPlanetStations": {
        "source": "mapPlanets",
        "field": "npcStationIDs",
        "parent_fields": {"_key": "celestialID"},
        "scalar_name": "stationID",
    },
}


def get_build_number(zf):
    candidates = [n for n in zf.namelist() if n.endswith("_sde.jsonl")]
    if not candidates:
        raise FileNotFoundError("_sde.jsonl not found in zip")
    with zf.open(candidates[0]) as raw:
        meta = json.loads(raw.readline().strip())
    return meta["buildNumber"]


# Field rename mapping based on table names
field_renames = {
    "invTypes": {"_key": "typeID", "name": "typeName"},
    "invCategories": {"_key": "categoryID", "name": "categoryName"},
    "invGroups": {"_key": "groupID", "name": "groupName"},
    "invMarketGroups": {"_key": "marketGroupID", "name": "marketGroupName"},
    "invMetaGroups": {
        "_key": "metaGroupID",
        "name": "metaGroupName",
        "r": "colorR",
        "g": "colorG",
        "b": "colorB",
    },
    "chrRaces": {"_key": "raceID", "name": "raceName", "skills": None},
    "chrFactions": {"_key": "factionID", "name": "factionName", "memberRaces": None},
    "chrAncestries": {"_key": "ancestryID", "name": "ancestryName"},
    "chrBloodlines": {"_key": "bloodlineID", "name": "bloodlineName"},
    "chrAttributes": {"_key": "attributeID", "name": "attributeName"},
    "agtAgentTypes": {"_key": "agentTypeID", "name": "agentType"},
    "agtAgentsInSpace": {"_key": "agentID"},
    "crpActivities": {"_key": "activityID", "name": "activityName"},
    "crpNPCCorporations": {
        "_key": "corporationID",
        "name": "corporationName",
        "corporationTrades": None,
        "divisions": None,
        "allowedMemberRaces": None,
        "lpOfferTables": None,
        "exchangeRates": None,
        "investors": None,
    },
    "crpNPCDivisions": {"_key": "divisionID", "name": "divisionName"},
    "dgmAttributeCategories": {
        "_key": "categoryID",
        "name": "categoryName",
        "description": "categoryDescription",
    },
    "dgmAttributeTypes": {
        "_key": "attributeID",
        "name": "attributeName",
        "attributeCategoryID": "categoryID",
    },
    "dgmEffects": {
        "_key": "effectID",
        "name": "effectName",
        "effectCategoryID": "effectCategory",
    },
    "eveUnits": {"_key": "unitID", "name": "unitName"},
    "skinLicense": {"_key": None},
    "eveGraphics": {"_key": "graphicID"},
    "eveIcons": {"_key": "iconID"},
    "industryBlueprints": {"_key": "typeID", "activities": None},
    "mapLandmarks": {"_key": "landmarkID", "name": "landmarkName"},
    "mapRegions": {"_key": "regionID", "name": "regionName", "constellationIDs": None},
    "mapConstellations": {
        "_key": "constellationID",
        "name": "constellationName",
        "solarSystemIDs": None,
    },
    "mapSolarSystems": {
        "_key": "solarSystemID",
        "name": "solarSystemName",
        "planetIDs": None,
        "stargateIDs": None,
    },
    "mapStargates": {"_key": "stargateID", "name": "stargateName", "destination": None},
    "planetSchematics": {
        "_key": "schematicID",
        "name": "schematicName",
        "pins": None,
        "types": None,
    },
    "skinMaterials": {"_key": "skinMaterialID"},
    "skins": {"_key": "skinID", "types": None},
    "staOperations": {"_key": "operationID", "services": None, "stationTypes": None},
    "staServices": {"_key": "serviceID"},
    "staStations": {"_key": "stationID", "name": "stationName"},
    "sovUpgrades": {
        "_key": "upgradeID",
        "fuel": None,
        "mutually_exclusive_group": "mutuallyExclusiveGroup",
        "power_allocation": "powerAllocation",
        "workforce_allocation": "workforceAllocation",
        "power_production": "powerProduction",
        "workforce_production": "workforceProduction",
    },
    "chrCertificates": {
        "_key": "certID",
        "name": "certName",
        "recommendedFor": None,
        "skillTypes": None,
    },
    "chrCloneGrades": {"_key": "gradeID", "skills": None},
    "chrMasteries": {"_key": "typeID", "_value": None},
    "chrNPCCharacters": {"_key": "characterID", "skills": None, "agent": None},
    "dbuffCollections": {
        "_key": "dbuffCollectionID",
        "itemModifiers": None,
        "locationGroupModifiers": None,
        "locationModifiers": None,
        "locationRequiredSkillModifiers": None,
    },
    "invCompressibleTypes": {"_key": "typeID"},
    "invDynamicItemAttributes": {
        "_key": "typeID",
        "attributeIDs": None,
        "inputOutputMapping": None,
    },
    "invTypeBonus": {
        "_key": "typeID",
        "roleBonuses": None,
        "types": None,
        "miscBonuses": None,
    },
    "invTypeDogma": {"_key": "typeID", "dogmaAttributes": None, "dogmaEffects": None},
    "mapAsteroidBelts": {"_key": "celestialID", "statistics": None},
    "mapMoons": {
        "_key": "celestialID",
        "statistics": None,
        "attributes": None,
        "npcStationIDs": None,
    },
    "mapPlanets": {
        "_key": "celestialID",
        "statistics": None,
        "attributes": None,
        "asteroidBeltIDs": None,
        "moonIDs": None,
        "npcStationIDs": None,
    },
    "mapSecondarySuns": {"_key": "itemID"},
    "mapStars": {"_key": "celestialID", "statistics": None},
    "mercenaryTacticalOperations": {
        "_key": "operationID",
        "anarchy_impact": "anarchyImpact",
        "development_impact": "developmentImpact",
        "infomorph_bonus": "infomorphBonus",
    },
    "planetResources": {
        "_key": "celestialID",
        "amount_per_cycle": "reagentAmountPerCycle",
        "cycle_period": "reagentCyclePeriod",
        "secured_capacity": "reagentSecuredCapacity",
        "type_id": "reagentTypeID",
        "unsecured_capacity": "reagentUnsecuredCapacity",
    },
    "translationLanguages": {"_key": "languageID"},
}

# Fields that are dicts and should be flattened into separate columns.
# Maps table_name -> list of field names to flatten.
# e.g. position: {"x": 1.0, "y": 2.0, "z": 3.0} becomes columns x, y, z
flatten_fields = {
    "mapConstellations": ["position"],
    "mapRegions": ["position"],
    "mapSolarSystems": ["position", "position2D"],
    "mapLandmarks": ["position"],
    "staStations": ["position"],
    "mapAsteroidBelts": ["position"],
    "mapMoons": ["position"],
    "mapPlanets": ["position"],
    "mapSecondarySuns": ["position"],
    "mapStargates": ["position"],
    "mapStars": ["position"],
    "invMetaGroups": ["color"],
    "planetResources": ["reagent"],
}

# Per-table field transforms applied after flatten but before type inference.
# Maps table_name -> {field_name: transform_function}
_pct = lambda v: round(v * 100) if v is not None else None

field_transforms = {
    "staOperations": {
        f: _pct for f in ("border", "corridor", "fringe", "hub", "ratio")
    },
}

_race_id_to_name = {1: "caldari", 2: "minmatar", 4: "amarr", 8: "gallente", 16: "jove"}


def _expand_station_types(row):
    st = row.pop("stationTypes", None)
    if isinstance(st, list):
        for item in st:
            race_id = item.get("_key")
            station_type_id = item.get("_value")
            name = _race_id_to_name.get(race_id)
            if name:
                row[f"{name}StationTypeID"] = station_type_id
            else:
                print(
                    f"WARNING: unknown race ID {race_id} in stationTypes for operation {row.get('operationID', '?')}"
                )


def _expand_investors(row):
    inv = row.pop("investors", None)
    if isinstance(inv, list):
        if len(inv) > 4:
            print(
                f"WARNING: corporation {row.get('corporationID', '?')} has {len(inv)} investors, truncating to 4"
            )
        for i, item in enumerate(inv[:4], 1):
            row[f"investorID{i}"] = item.get("_key")
            row[f"investorShares{i}"] = item.get("_value")


def _expand_destination(row):
    dest = row.pop("destination", None)
    if isinstance(dest, dict):
        row["destinationSolarSystemID"] = dest.get("solarSystemID")
        row["destinationStargateID"] = dest.get("stargateID")


# Row-level transforms applied after flatten and field transforms.
# Maps table_name -> function(row) that mutates the row in place.
row_transforms = {
    "staOperations": _expand_station_types,
    "crpNPCCorporations": _expand_investors,
    "mapStargates": _expand_destination,
}

# Primary key definitions. Maps table_name -> list of PK column names.
# Tables not listed here will have no primary key.
primary_keys = {
    "agtAgentTypes": ["agentTypeID"],
    "agtAgents": ["agentID"],
    "agtAgentsInSpace": ["agentID"],
    "agtResearchAgents": ["agentID", "typeID"],
    "certCerts": ["certID"],
    "certMasteries": ["typeID", "masteryLevel", "certID"],
    "certSkills": ["certID", "skillID", "certLevelInt"],
    "chrAncestries": ["ancestryID"],
    "chrAttributes": ["attributeID"],
    "chrBloodlines": ["bloodlineID"],
    "chrCertificates": ["certID"],
    "chrCloneGradeSkills": ["gradeID", "typeID"],
    "chrCloneGrades": ["gradeID"],
    "chrFactionRaces": ["factionID", "raceID"],
    "chrFactions": ["factionID"],
    "chrMasteries": ["typeID"],
    "chrNPCCharacters": ["characterID"],
    "chrRaceSkills": ["raceID", "skillTypeID"],
    "chrRaces": ["raceID"],
    "crpActivities": ["activityID"],
    "crpNPCCorporationDivisions": ["corporationID", "divisionID"],
    "crpNPCCorporationExchangeRates": ["corporationID", "targetCorporationID"],
    "crpNPCCorporationLPOfferTables": ["corporationID", "offerTableID"],
    "crpNPCCorporationRaces": ["corporationID", "raceID"],
    "crpNPCCorporationResearchFields": ["skillID", "corporationID"],
    "crpNPCCorporationTrades": ["corporationID", "typeID"],
    "crpNPCCorporations": ["corporationID"],
    "crpNPCDivisions": ["divisionID"],
    "dbuffCollections": ["dbuffCollectionID"],
    "dgmAttributeCategories": ["categoryID"],
    "dgmAttributeTypes": ["attributeID"],
    "dgmEffects": ["effectID"],
    "dgmTypeAttributes": ["typeID", "attributeID"],
    "dgmTypeEffects": ["typeID", "effectID"],
    "eveGraphics": ["graphicID"],
    "eveIcons": ["iconID"],
    "eveUnits": ["unitID"],
    "freelanceJobSchemaParameters": ["schemaID", "parameterID"],
    "freelanceJobSchemas": ["schemaID"],
    "industryActivity": ["typeID", "activityID"],
    "industryActivityMaterials": ["typeID", "activityID", "materialTypeID"],
    "industryActivityProbabilities": ["typeID", "activityID", "productTypeID"],
    "industryActivityProducts": ["typeID", "activityID", "productTypeID"],
    "industryBlueprints": ["typeID"],
    "invCategories": ["categoryID"],
    "invCompressibleTypes": ["typeID"],
    "invContrabandTypes": ["factionID", "typeID"],
    "invControlTowerResources": ["controlTowerTypeID", "resourceTypeID"],
    "invDynamicItemAttributeRanges": ["typeID", "attributeID"],
    "invDynamicItemAttributes": ["typeID"],
    "invDynamicItemInputOutput": ["typeID", "resultingType"],
    "invGroups": ["groupID"],
    "invMarketGroups": ["marketGroupID"],
    "invMetaGroups": ["metaGroupID"],
    "invTraits": ["traitID"],
    "invTypeBonus": ["typeID"],
    "invTypeDogma": ["typeID"],
    "invTypeMaterials": ["typeID", "materialTypeID"],
    "invTypes": ["typeID"],
    "mapAsteroidBelts": ["celestialID"],
    "mapCelestialGraphics": ["celestialID"],
    "mapCelestialStatistics": ["celestialID"],
    "mapConstellationJumps": ["fromConstellationID", "toConstellationID"],
    "mapConstellations": ["constellationID"],
    "mapDenormalize": ["itemID"],
    "mapLandmarks": ["landmarkID"],
    "mapLocationWormholeClasses": ["locationID"],
    "mapMoonStations": ["celestialID", "stationID"],
    "mapMoons": ["celestialID"],
    "mapPlanetAsteroidBelts": ["celestialID", "asteroidBeltID"],
    "mapPlanetMoons": ["celestialID", "moonID"],
    "mapPlanetStations": ["celestialID", "stationID"],
    "mapPlanets": ["celestialID"],
    "mapRegionJumps": ["fromRegionID", "toRegionID"],
    "mapRegions": ["regionID"],
    "mapSecondarySuns": ["itemID"],
    "mapSolarSystemJumps": ["fromSolarSystemID", "toSolarSystemID"],
    "mapSolarSystems": ["solarSystemID"],
    "mapStargates": ["stargateID"],
    "mapStars": ["celestialID"],
    "mercenaryTacticalOperations": ["operationID"],
    "planetResources": ["celestialID"],
    "planetSchematics": ["schematicID"],
    "planetSchematicsPinMap": ["schematicID", "pinTypeID"],
    "planetSchematicsTypeMap": ["schematicID", "typeID"],
    "skinLicense": ["licenseTypeID"],
    "skinMaterials": ["skinMaterialID"],
    "skinShip": ["skinID", "typeID"],
    "skins": ["skinID"],
    "sovUpgradeFuels": ["upgradeID"],
    "sovUpgrades": ["upgradeID"],
    "staOperationServices": ["operationID", "serviceID"],
    "staOperationStationTypes": ["operationID", "raceID"],
    "staOperations": ["operationID"],
    "staServices": ["serviceID"],
    "staStations": ["stationID"],
    "translationLanguages": ["languageID"],
}

# Secondary indexes for common foreign-key lookups.
# Maps table_name -> list of (index_name, column(s)) tuples.
indexes = {
    "agtAgents": [
        ("ix_agtAgents_corporationID", ["corporationID"]),
        ("ix_agtAgents_locationID", ["locationID"]),
    ],
    "agtAgentsInSpace": [
        ("ix_agtAgentsInSpace_solarSystemID", ["solarSystemID"]),
    ],
    "agtResearchAgents": [
        ("ix_agtResearchAgents_typeID", ["typeID"]),
    ],
    "certMasteries": [
        ("ix_certMasteries_certID", ["certID"]),
    ],
    "certSkills": [
        ("ix_certSkills_skillID", ["skillID"]),
    ],
    "chrNPCCharacters": [
        ("ix_chrNPCCharacters_corporationID", ["corporationID"]),
    ],
    "dgmTypeAttributes": [
        ("ix_dgmTypeAttributes_attributeID", ["attributeID"]),
    ],
    "dgmTypeEffects": [
        ("ix_dgmTypeEffects_effectID", ["effectID"]),
    ],
    "industryActivity": [
        ("ix_industryActivity_activityID", ["activityID"]),
    ],
    "industryActivityMaterials": [
        ("ix_industryActivityMaterials_typeID", ["typeID"]),
        ("ix_industryActivityMaterials_typeID_activityID", ["typeID", "activityID"]),
    ],
    "industryActivityProbabilities": [
        ("ix_industryActivityProbabilities_typeID", ["typeID"]),
        ("ix_industryActivityProbabilities_productTypeID", ["productTypeID"]),
    ],
    "industryActivityProducts": [
        ("ix_industryActivityProducts_typeID", ["typeID"]),
        ("ix_industryActivityProducts_productTypeID", ["productTypeID"]),
    ],
    "industryActivitySkills": [
        ("ix_industryActivitySkills_typeID", ["typeID"]),
        ("ix_industryActivitySkills_typeID_activityID", ["typeID", "activityID"]),
        ("ix_industryActivitySkills_skillID", ["skillID"]),
    ],
    "invContrabandTypes": [
        ("ix_invContrabandTypes_typeID", ["typeID"]),
    ],
    "invGroups": [
        ("ix_invGroups_categoryID", ["categoryID"]),
    ],
    "invTypes": [
        ("ix_invTypes_groupID", ["groupID"]),
    ],
    "invTypeMaterials": [
        ("ix_invTypeMaterials_materialTypeID", ["materialTypeID"]),
    ],
    "mapAsteroidBelts": [
        ("ix_mapAsteroidBelts_solarSystemID", ["solarSystemID"]),
    ],
    "mapConstellations": [
        ("ix_mapConstellations_regionID", ["regionID"]),
    ],
    "mapMoons": [
        ("ix_mapMoons_solarSystemID", ["solarSystemID"]),
    ],
    "mapPlanets": [
        ("ix_mapPlanets_solarSystemID", ["solarSystemID"]),
    ],
    "mapSolarSystems": [
        ("ix_mapSolarSystems_constellationID", ["constellationID"]),
        ("ix_mapSolarSystems_regionID", ["regionID"]),
        ("ix_mapSolarSystems_securityStatus", ["securityStatus"]),
    ],
    "mapStargates": [
        ("ix_mapStargates_solarSystemID", ["solarSystemID"]),
    ],
    "skinShip": [
        ("ix_skinShip_typeID", ["typeID"]),
    ],
    "staStations": [
        ("ix_staStations_solarSystemID", ["solarSystemID"]),
        ("ix_staStations_operationID", ["operationID"]),
    ],
    "invTraits": [
        ("ix_invTraits_typeID", ["typeID"]),
    ],
    "dbuffCollectionModifiers": [
        ("ix_dbuffCollectionModifiers_dbuffCollectionID", ["dbuffCollectionID"]),
    ],
    "invDynamicItemAttributeRanges": [
        ("ix_invDynamicItemAttributeRanges_attributeID", ["attributeID"]),
    ],
    "crpNPCCorporationTrades": [
        ("ix_crpNPCCorporationTrades_typeID", ["typeID"]),
    ],
    "mapMoonStations": [
        ("ix_mapMoonStations_stationID", ["stationID"]),
    ],
    "mapPlanetMoons": [
        ("ix_mapPlanetMoons_moonID", ["moonID"]),
    ],
    "mapDenormalize": [
        ("ix_mapDenormalize_solarSystemID", ["solarSystemID"]),
        ("ix_mapDenormalize_constellationID", ["constellationID"]),
        ("ix_mapDenormalize_regionID", ["regionID"]),
        ("ix_mapDenormalize_orbitID", ["orbitID"]),
        ("ix_mapDenormalize_typeID", ["typeID"]),
        ("mapDenormalize_IX_groupSystem", ["groupID", "solarSystemID"]),
        ("mapDenormalize_IX_groupConstellation", ["groupID", "constellationID"]),
        ("mapDenormalize_IX_groupRegion", ["groupID", "regionID"]),
    ],
}


_LANG_CODES = {"en", "de", "es", "fr", "it", "ja", "ko", "ru", "zh"}


def _is_lang_dict(d):
    return isinstance(d, dict) and "en" in d and d.keys() <= _LANG_CODES


def _localized_str(val):
    if isinstance(val, dict):
        return val.get("en", "")
    return "" if val is None else str(val)


_TYPE_RANK = {"BOOLEAN": 0, "INTEGER": 1, "REAL": 2, "TEXT": 3}


def update_type(current_type, val):
    if val is None:
        return current_type
    if isinstance(val, bool):
        new = "BOOLEAN"
    elif isinstance(val, int):
        new = "INTEGER"
    elif isinstance(val, float):
        new = "REAL"
    else:
        new = "TEXT"
    if current_type is None:
        return new
    return (
        current_type
        if _TYPE_RANK.get(current_type, 3) >= _TYPE_RANK.get(new, 3)
        else new
    )


def infer_column_types(rows):
    key_types = {}
    for row in rows:
        for k, v in row.items():
            key_types[k] = update_type(key_types.get(k), v)
    return {k: (t or "TEXT") for k, t in key_types.items()}


def q(name):
    return f'"{name}"'


activity_id_map = {
    "manufacturing": 1,
    "research_time": 3,
    "research_material": 4,
    "copying": 5,
    "invention": 8,
    "reaction": 11,
}

cert_level_names = ["basic", "standard", "improved", "advanced", "elite"]


def flatten_row(row, fields_to_flatten):
    for field in fields_to_flatten:
        val = row.pop(field, None)
        if isinstance(val, dict):
            collisions = set(val.keys()) & set(row.keys())
            if collisions and field not in flatten_row.warned:
                flatten_row.warned.add(field)
                print(f"WARNING: flatten_row key collision on {field}: {collisions}")
            row.update(val)


flatten_row.warned = set()


def transform_row(row, transforms):
    for field, fn in transforms.items():
        if field in row:
            row[field] = fn(row[field])


class SdeImporter:
    def __init__(self, zf, conn):
        self.zf = zf
        self.conn = conn
        self.cursor = conn.cursor()
        names = zf.namelist()
        prefix = ""
        if names and not any(n.endswith(".jsonl") and "/" not in n for n in names):
            prefixes = {n.rsplit("/", 1)[0] + "/" for n in names if "/" in n}
            if len(prefixes) == 1:
                prefix = prefixes.pop()
        self._prefix = prefix
        self._members = set(names)

    def read_jsonl(self, member):
        with self.zf.open(member) as raw:
            for line in io.TextIOWrapper(raw, encoding="utf-8"):
                line = line.strip()
                if line:
                    yield json.loads(line)

    def table_exists(self, name):
        self.cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        )
        return self.cursor.fetchone() is not None

    def create_table(self, table_name, columns):
        col_defs = []
        for key, typ in columns.items():
            col_defs.append(f"{q(key)} {typ}")
        pk_cols = primary_keys.get(table_name)
        if pk_cols:
            col_defs.append(f"PRIMARY KEY ({', '.join(q(c) for c in pk_cols)})")
        self.cursor.execute(f"CREATE TABLE {q(table_name)} ({', '.join(col_defs)})")

    def create_indexes(self):
        for table_name, idx_list in indexes.items():
            for idx_name, cols in idx_list:
                col_str = ", ".join(q(c) for c in cols)
                self.cursor.execute(
                    f"CREATE INDEX {q(idx_name)} ON {q(table_name)} ({col_str})"
                )

    def insert_data(self, table_name, data, columns):
        if not data:
            return
        placeholders = ", ".join("?" for _ in columns)
        insert_stmt = f"INSERT INTO {q(table_name)} ({', '.join(q(c) for c in columns)}) VALUES ({placeholders})"
        rows = []
        for row in data:
            values = []
            for col in columns:
                val = row.get(col)
                if isinstance(val, dict):
                    if _is_lang_dict(val):
                        val = val.get("en", "")
                    else:
                        val = json.dumps(val)
                elif isinstance(val, list):
                    val = json.dumps(val)
                values.append(val)
            rows.append(values)
        self.cursor.executemany(insert_stmt, rows)

    def emit_table(self, table_name, rows, columns):
        print(f"Derived {table_name} ({len(rows)} rows)")
        self.create_table(table_name, columns)
        self.insert_data(table_name, rows, list(columns.keys()))

    def sde_file(self, name):
        member = self._prefix + name
        return member if member in self._members else None

    def process_jsonl(self, file_path, table_name):
        renames = field_renames.get(table_name, {})
        to_flatten = flatten_fields.get(table_name, [])
        transforms = field_transforms.get(table_name, {})
        row_transform = row_transforms.get(table_name)

        def _prepare(row):
            flatten_row(row, to_flatten)
            transform_row(row, transforms)
            if row_transform:
                row_transform(row)
            return row

        key_types = {}
        all_rows = []
        for row in self.read_jsonl(file_path):
            _prepare(row)
            for key, val in row.items():
                key_types[key] = update_type(key_types.get(key), val)
            all_rows.append(row)
        for key in key_types:
            if key_types[key] is None:
                key_types[key] = "TEXT"
        columns = {}
        for key, typ in key_types.items():
            new_key = renames.get(key, key)
            if new_key is None:
                continue
            columns[new_key] = typ
        if not columns:
            print(f"Skipping {table_name}: no columns inferred (empty file?)")
            return
        self.create_table(table_name, columns)
        col_keys = list(columns.keys())
        batch = []
        for row in all_rows:
            for key in row:
                val = row[key]
                if isinstance(val, dict):
                    if _is_lang_dict(val):
                        row[key] = val.get("en", "")
                    else:
                        row[key] = json.dumps(val)
                elif isinstance(val, list):
                    row[key] = json.dumps(val)
            for old_name, new_name in renames.items():
                if old_name in row:
                    if new_name is None:
                        del row[old_name]
                    else:
                        if new_name in row and new_name != old_name:
                            print(
                                f"WARNING: rename collision in {table_name}: {old_name}->{new_name} overwrites existing value"
                            )
                        row[new_name] = row.pop(old_name)
            for col in columns:
                if col not in row:
                    row[col] = None
            batch.append(row)
            if len(batch) >= 10000:
                self.insert_data(table_name, batch, col_keys)
                batch = []
        if batch:
            self.insert_data(table_name, batch, col_keys)

    def process_file(self, member):
        base_name = member.rsplit("/", 1)[-1].removesuffix(".jsonl")
        table_name = table_mapping.get(base_name)
        if not table_name:
            print(f"Skipping {base_name}.jsonl, no table mapping")
            return

        print(f"Processing {base_name}.jsonl -> {table_name}")
        self.process_jsonl(member, table_name)
        print(f"Completed {table_name}")

    def process_derived_tables(self):
        from collections import defaultdict

        sources = defaultdict(list)
        for table_name, config in derived_tables.items():
            sources[config["source"]].append((table_name, config))

        for source, table_configs in sources.items():
            file_path = self.sde_file(f"{source}.jsonl")
            if not file_path:
                table_names = [t for t, _ in table_configs]
                print(
                    f"WARNING: Skipping derived tables from {source}: file not found (affects: {', '.join(table_names)})"
                )
                continue

            collectors = {}
            for table_name, config in table_configs:
                collectors[table_name] = {"config": config, "rows": [], "key_types": {}}

            for parent in self.read_jsonl(file_path):
                for table_name, col in collectors.items():
                    config = col["config"]
                    field = config["field"]
                    if field not in parent:
                        continue
                    filt = config.get("filter")
                    if filt and not parent.get(filt):
                        continue

                    val = parent[field]
                    scalar_name = config.get("scalar_name")
                    if scalar_name:
                        if isinstance(val, list):
                            items = [{scalar_name: v} for v in val]
                        else:
                            continue
                    elif isinstance(val, dict):
                        items = [val]
                    elif isinstance(val, list):
                        items = val
                    else:
                        continue

                    parent_fields = config["parent_fields"]
                    renames = config.get("renames", {})
                    drop = set(config.get("drop", []))

                    for item in items:
                        row = {}
                        for src_field, out_col in parent_fields.items():
                            row[out_col] = parent.get(src_field)
                        for k, v in item.items():
                            if k in drop:
                                continue
                            row[renames.get(k, k)] = v
                        col["rows"].append(row)
                        for k, v in row.items():
                            col["key_types"][k] = update_type(
                                col["key_types"].get(k), v
                            )

            for table_name, col in collectors.items():
                key_types = col["key_types"]
                if not key_types:
                    print(f"Skipping {table_name}: no data extracted")
                    continue
                columns = {k: (t or "TEXT") for k, t in key_types.items()}
                self.emit_table(table_name, col["rows"], columns)

    def process_blueprint_activities(self):
        file_path = self.sde_file("blueprints.jsonl")
        if not file_path:
            print("Skipping blueprint activities: blueprints.jsonl not found")
            return

        activities = []
        materials = []
        products = []
        probabilities = []
        skills = []

        for bp in self.read_jsonl(file_path):
            type_id = bp["_key"]
            for act_name, act_data in bp.get("activities", {}).items():
                act_id = activity_id_map.get(act_name)
                if act_id is None:
                    continue
                activities.append(
                    {
                        "typeID": type_id,
                        "activityID": act_id,
                        "time": act_data.get("time"),
                    }
                )
                for mat in act_data.get("materials", []):
                    materials.append(
                        {
                            "typeID": type_id,
                            "activityID": act_id,
                            "materialTypeID": mat["typeID"],
                            "quantity": mat["quantity"],
                        }
                    )
                for prod in act_data.get("products", []):
                    products.append(
                        {
                            "typeID": type_id,
                            "activityID": act_id,
                            "productTypeID": prod["typeID"],
                            "quantity": prod["quantity"],
                        }
                    )
                    if "probability" in prod:
                        probabilities.append(
                            {
                                "typeID": type_id,
                                "activityID": act_id,
                                "productTypeID": prod["typeID"],
                                "probability": prod["probability"],
                            }
                        )
                for skill in act_data.get("skills", []):
                    skills.append(
                        {
                            "typeID": type_id,
                            "activityID": act_id,
                            "skillID": skill["typeID"],
                            "level": skill["level"],
                        }
                    )

        tables = {
            "industryActivity": (
                activities,
                {"typeID": "INTEGER", "activityID": "INTEGER", "time": "INTEGER"},
            ),
            "industryActivityMaterials": (
                materials,
                {
                    "typeID": "INTEGER",
                    "activityID": "INTEGER",
                    "materialTypeID": "INTEGER",
                    "quantity": "INTEGER",
                },
            ),
            "industryActivityProducts": (
                products,
                {
                    "typeID": "INTEGER",
                    "activityID": "INTEGER",
                    "productTypeID": "INTEGER",
                    "quantity": "INTEGER",
                },
            ),
            "industryActivityProbabilities": (
                probabilities,
                {
                    "typeID": "INTEGER",
                    "activityID": "INTEGER",
                    "productTypeID": "INTEGER",
                    "probability": "REAL",
                },
            ),
            "industryActivitySkills": (
                skills,
                {
                    "typeID": "INTEGER",
                    "activityID": "INTEGER",
                    "skillID": "INTEGER",
                    "level": "INTEGER",
                },
            ),
        }
        for name, (rows, columns) in tables.items():
            self.emit_table(name, rows, columns)

    def process_certificate_tables(self):
        file_path = self.sde_file("certificates.jsonl")
        if not file_path:
            print("Skipping certificate tables: certificates.jsonl not found")
            return

        certs = []
        skills = []
        for row in self.read_jsonl(file_path):
            cert_id = row["_key"]
            certs.append(
                {
                    "certID": cert_id,
                    "description": _localized_str(row.get("description")),
                    "groupID": row.get("groupID"),
                    "name": _localized_str(row.get("name")),
                }
            )
            for skill_entry in row.get("skillTypes", []):
                skill_id = skill_entry["_key"]
                for level_int, level_text in enumerate(cert_level_names):
                    if level_text in skill_entry:
                        skills.append(
                            {
                                "certID": cert_id,
                                "skillID": skill_id,
                                "certLevelInt": level_int,
                                "skillLevel": skill_entry[level_text],
                                "certLevelText": level_text,
                            }
                        )

        masteries_path = self.sde_file("masteries.jsonl")
        masteries = []
        if masteries_path:
            for row in self.read_jsonl(masteries_path):
                type_id = row["_key"]
                for level_entry in row.get("_value", []):
                    mastery_level = level_entry["_key"]
                    for cert_id in level_entry.get("_value", []):
                        masteries.append(
                            {
                                "typeID": type_id,
                                "masteryLevel": mastery_level,
                                "certID": cert_id,
                            }
                        )

        tables = {
            "certCerts": (
                certs,
                {
                    "certID": "INTEGER",
                    "description": "TEXT",
                    "groupID": "INTEGER",
                    "name": "TEXT",
                },
            ),
            "certSkills": (
                skills,
                {
                    "certID": "INTEGER",
                    "skillID": "INTEGER",
                    "certLevelInt": "INTEGER",
                    "skillLevel": "INTEGER",
                    "certLevelText": "TEXT",
                },
            ),
            "certMasteries": (
                masteries,
                {"typeID": "INTEGER", "masteryLevel": "INTEGER", "certID": "INTEGER"},
            ),
        }
        for name, (rows, columns) in tables.items():
            self.emit_table(name, rows, columns)

    def process_research_fields(self):
        file_path = self.sde_file("npcCharacters.jsonl")
        if not file_path:
            print(
                "Skipping crpNPCCorporationResearchFields: npcCharacters.jsonl not found"
            )
            return

        pairs = set()
        for row in self.read_jsonl(file_path):
            if not row.get("agent") or not row.get("skills"):
                continue
            corp_id = row.get("corporationID")
            for skill in row["skills"]:
                skill_id = skill.get("_key") or skill.get("typeID")
                if corp_id is not None and skill_id is not None:
                    pairs.add((skill_id, corp_id))

        rows = [{"skillID": s, "corporationID": c} for s, c in sorted(pairs)]
        columns = {"skillID": "INTEGER", "corporationID": "INTEGER"}
        self.emit_table("crpNPCCorporationResearchFields", rows, columns)

    def _process_celestial_subtable(self, table_name, source_files, nested_field):
        all_rows = []
        for filename, id_field in source_files:
            file_path = self.sde_file(filename)
            if not file_path:
                continue
            for obj in self.read_jsonl(file_path):
                nested = obj.get(nested_field)
                if not isinstance(nested, dict):
                    continue
                row = {"celestialID": obj[id_field]}
                row.update(nested)
                all_rows.append(row)

        columns = infer_column_types(all_rows)
        self.emit_table(table_name, all_rows, columns)

    def process_celestial_statistics(self):
        self._process_celestial_subtable(
            "mapCelestialStatistics",
            [
                ("mapStars.jsonl", "_key"),
                ("mapPlanets.jsonl", "_key"),
                ("mapMoons.jsonl", "_key"),
                ("mapAsteroidBelts.jsonl", "_key"),
            ],
            "statistics",
        )

    def process_celestial_graphics(self):
        self._process_celestial_subtable(
            "mapCelestialGraphics",
            [
                ("mapPlanets.jsonl", "_key"),
                ("mapMoons.jsonl", "_key"),
            ],
            "attributes",
        )

    def process_jump_tables(self):
        stargates_path = self.sde_file("mapStargates.jsonl")
        systems_path = self.sde_file("mapSolarSystems.jsonl")
        if not stargates_path or not systems_path:
            print(
                "Skipping jump tables: missing mapStargates.jsonl or mapSolarSystems.jsonl"
            )
            return

        system_info = {}
        for row in self.read_jsonl(systems_path):
            system_info[row["_key"]] = {
                "constellationID": row.get("constellationID"),
                "regionID": row.get("regionID"),
            }

        system_jumps = set()
        for row in self.read_jsonl(stargates_path):
            from_sys = row.get("solarSystemID")
            to_sys = row.get("destination", {}).get("solarSystemID")
            if from_sys and to_sys:
                system_jumps.add((from_sys, to_sys))

        sys_rows = []
        constellation_jumps = set()
        region_jumps = set()
        for from_sys, to_sys in sorted(system_jumps):
            from_info = system_info.get(from_sys, {})
            to_info = system_info.get(to_sys, {})
            from_con = from_info.get("constellationID")
            from_reg = from_info.get("regionID")
            to_con = to_info.get("constellationID")
            to_reg = to_info.get("regionID")
            sys_rows.append(
                {
                    "fromRegionID": from_reg,
                    "fromConstellationID": from_con,
                    "fromSolarSystemID": from_sys,
                    "toSolarSystemID": to_sys,
                    "toConstellationID": to_con,
                    "toRegionID": to_reg,
                }
            )
            if from_con and to_con and from_con != to_con:
                constellation_jumps.add((from_reg, from_con, to_con, to_reg))
            if from_reg and to_reg and from_reg != to_reg:
                region_jumps.add((from_reg, to_reg))

        con_rows = [
            {
                "fromRegionID": fr,
                "fromConstellationID": fc,
                "toConstellationID": tc,
                "toRegionID": tr,
            }
            for fr, fc, tc, tr in sorted(constellation_jumps)
        ]
        reg_rows = [
            {"fromRegionID": fr, "toRegionID": tr} for fr, tr in sorted(region_jumps)
        ]

        tables = {
            "mapSolarSystemJumps": (
                sys_rows,
                {
                    "fromRegionID": "INTEGER",
                    "fromConstellationID": "INTEGER",
                    "fromSolarSystemID": "INTEGER",
                    "toSolarSystemID": "INTEGER",
                    "toConstellationID": "INTEGER",
                    "toRegionID": "INTEGER",
                },
            ),
            "mapConstellationJumps": (
                con_rows,
                {
                    "fromRegionID": "INTEGER",
                    "fromConstellationID": "INTEGER",
                    "toConstellationID": "INTEGER",
                    "toRegionID": "INTEGER",
                },
            ),
            "mapRegionJumps": (
                reg_rows,
                {
                    "fromRegionID": "INTEGER",
                    "toRegionID": "INTEGER",
                },
            ),
        }
        for name, (rows, columns) in tables.items():
            self.emit_table(name, rows, columns)

    def process_traits(self):
        file_path = self.sde_file("typeBonus.jsonl")
        if not file_path:
            print("Skipping invTraits: typeBonus.jsonl not found")
            return

        def _trait_row(trait_id, type_id, skill_id, b):
            return {
                "traitID": trait_id,
                "typeID": type_id,
                "skillID": skill_id,
                "bonus": b.get("bonus"),
                "bonusText": _localized_str(b.get("bonusText")),
                "unitID": b.get("unitID"),
            }

        rows = []
        trait_id = 0
        for obj in self.read_jsonl(file_path):
            type_id = obj["_key"]
            for bonus_entry in obj.get("types", []):
                skill_id = bonus_entry["_key"]
                for b in bonus_entry.get("_value", []):
                    trait_id += 1
                    rows.append(_trait_row(trait_id, type_id, skill_id, b))
            for b in obj.get("roleBonuses", []):
                trait_id += 1
                rows.append(_trait_row(trait_id, type_id, -1, b))
            for b in obj.get("miscBonuses", []):
                trait_id += 1
                rows.append(_trait_row(trait_id, type_id, -2, b))

        columns = {
            "traitID": "INTEGER",
            "typeID": "INTEGER",
            "skillID": "INTEGER",
            "bonus": "REAL",
            "bonusText": "TEXT",
            "unitID": "INTEGER",
        }
        self.emit_table("invTraits", rows, columns)

    def process_wormhole_classes(self):
        rows = []
        for filename, id_field in [
            ("mapSolarSystems.jsonl", "_key"),
            ("mapRegions.jsonl", "_key"),
        ]:
            file_path = self.sde_file(filename)
            if not file_path:
                continue
            for obj in self.read_jsonl(file_path):
                wh_class = obj.get("wormholeClassID")
                if wh_class is not None:
                    rows.append(
                        {
                            "locationID": obj[id_field],
                            "wormholeClassID": wh_class,
                        }
                    )

        columns = {"locationID": "INTEGER", "wormholeClassID": "INTEGER"}
        self.emit_table("mapLocationWormholeClasses", rows, columns)

    def process_freelance_job_schemas(self):
        file_path = self.sde_file("freelanceJobSchemas.jsonl")
        if not file_path:
            print("Skipping freelance job schemas: freelanceJobSchemas.jsonl not found")
            return

        schemas = []
        params = []

        for parent in self.read_jsonl(file_path):
            for item in parent.get("_value", []):
                mcp = item.get("maxContributionsPerParticipant")
                if isinstance(mcp, dict):
                    mcp = {
                        k: v.get("en", v) if isinstance(v, dict) else v
                        for k, v in mcp.items()
                    }
                else:
                    mcp = None

                schemas.append(
                    {
                        "schemaID": item["_key"],
                        "title": _localized_str(item.get("title")),
                        "description": _localized_str(item.get("description")),
                        "iconID": item.get("iconID"),
                        "progressDescription": _localized_str(
                            item.get("progressDescription")
                        ),
                        "rewardDescription": _localized_str(
                            item.get("rewardDescription")
                        ),
                        "targetDescription": _localized_str(
                            item.get("targetDescription")
                        ),
                        "contentTags": json.dumps(item.get("contentTags")),
                        "maxContributionsPerParticipant": json.dumps(mcp)
                        if mcp
                        else None,
                        "contributionMultiplier": item.get("contributionMultiplier"),
                        "maxProgressPerContribution": item.get(
                            "maxProgressPerContribution"
                        ),
                    }
                )

                for p in item.get("parameters", []):
                    m = p.get("matcher") or {}
                    params.append(
                        {
                            "schemaID": item["_key"],
                            "parameterID": p["_key"],
                            "type": m.get("type"),
                            "maxEntries": m.get("maxEntries"),
                            "optional": m.get("optional"),
                            "title": _localized_str(m.get("title")),
                            "description": _localized_str(m.get("description")),
                            "acceptedValueTypes": json.dumps(
                                m.get("acceptedValueTypes")
                            ),
                        }
                    )

        schema_cols = {
            "schemaID": "TEXT",
            "title": "TEXT",
            "description": "TEXT",
            "iconID": "TEXT",
            "progressDescription": "TEXT",
            "rewardDescription": "TEXT",
            "targetDescription": "TEXT",
            "contentTags": "TEXT",
            "maxContributionsPerParticipant": "TEXT",
            "contributionMultiplier": "REAL",
            "maxProgressPerContribution": "REAL",
        }
        self.emit_table("freelanceJobSchemas", schemas, schema_cols)

        param_cols = {
            "schemaID": "TEXT",
            "parameterID": "TEXT",
            "type": "TEXT",
            "maxEntries": "INTEGER",
            "optional": "BOOLEAN",
            "title": "TEXT",
            "description": "TEXT",
            "acceptedValueTypes": "TEXT",
        }
        self.emit_table("freelanceJobSchemaParameters", params, param_cols)

    def process_dbuff_modifiers(self):
        file_path = self.sde_file("dbuffCollections.jsonl")
        if not file_path:
            print("Skipping dbuff modifiers: dbuffCollections.jsonl not found")
            return

        rows = []
        modifier_fields = [
            ("itemModifiers", "item"),
            ("locationGroupModifiers", "locationGroup"),
            ("locationModifiers", "location"),
            ("locationRequiredSkillModifiers", "locationRequiredSkill"),
        ]

        for parent in self.read_jsonl(file_path):
            collection_id = parent.get("_key")
            for field, modifier_type in modifier_fields:
                items = parent.get(field, [])
                if not isinstance(items, list):
                    continue
                for item in items:
                    rows.append(
                        {
                            "dbuffCollectionID": collection_id,
                            "modifierType": modifier_type,
                            "dogmaAttributeID": item.get("dogmaAttributeID"),
                            "groupID": item.get("groupID"),
                            "skillID": item.get("skillID"),
                        }
                    )

        columns = {
            "dbuffCollectionID": "INTEGER",
            "modifierType": "TEXT",
            "dogmaAttributeID": "INTEGER",
            "groupID": "INTEGER",
            "skillID": "INTEGER",
        }
        self.emit_table("dbuffCollectionModifiers", rows, columns)

    def process_map_denormalize(self):
        required = [
            "mapSolarSystems",
            "mapPlanets",
            "mapRegions",
            "mapConstellations",
            "mapStars",
            "mapMoons",
            "mapAsteroidBelts",
            "mapStargates",
            "staStations",
            "mapSecondarySuns",
        ]
        missing = [t for t in required if not self.table_exists(t)]
        if missing:
            print(f"Skipping mapDenormalize: missing tables {', '.join(missing)}")
            return

        ROMAN = [
            "",
            "I",
            "II",
            "III",
            "IV",
            "V",
            "VI",
            "VII",
            "VIII",
            "IX",
            "X",
            "XI",
            "XII",
            "XIII",
            "XIV",
            "XV",
            "XVI",
            "XVII",
            "XVIII",
            "XIX",
            "XX",
        ]

        GROUP_REGION = 3
        GROUP_CONSTELLATION = 4
        GROUP_SOLAR_SYSTEM = 5
        GROUP_STAR = 6
        GROUP_PLANET = 7
        GROUP_MOON = 8
        GROUP_ASTEROID_BELT = 9
        GROUP_STARGATE = 10
        GROUP_STATION = 15
        GROUP_SECONDARY_SUN = 995

        expected_groups = {
            GROUP_REGION: "Region",
            GROUP_CONSTELLATION: "Constellation",
            GROUP_SOLAR_SYSTEM: "Solar System",
            GROUP_STAR: "Sun",
            GROUP_PLANET: "Planet",
            GROUP_MOON: "Moon",
            GROUP_ASTEROID_BELT: "Asteroid Belt",
            GROUP_STARGATE: "Stargate",
            GROUP_STATION: "Station",
            GROUP_SECONDARY_SUN: "Secondary Sun",
        }
        if self.table_exists("invGroups"):
            for gid, expected_name in expected_groups.items():
                self.cursor.execute(
                    "SELECT groupName FROM invGroups WHERE groupID = ?", (gid,)
                )
                result = self.cursor.fetchone()
                if not result:
                    print(
                        f"WARNING: mapDenormalize expected groupID {gid} ({expected_name}) not found in invGroups"
                    )

        rows = []

        system_info = {}
        self.cursor.execute(
            "SELECT solarSystemID, solarSystemName, constellationID, regionID, securityStatus FROM mapSolarSystems"
        )
        for sid, name, cid, rid, sec in self.cursor.fetchall():
            system_info[sid] = {
                "name": name,
                "constellationID": cid,
                "regionID": rid,
                "security": sec,
            }

        planet_info = {}
        self.cursor.execute(
            "SELECT celestialID, celestialIndex, solarSystemID, uniqueName FROM mapPlanets"
        )
        for cid, ci, sid, uname in self.cursor.fetchall():
            sinfo = system_info.get(sid, {})
            if uname:
                pname = uname
            else:
                pname = (
                    f"{sinfo.get('name', '')} {ROMAN[ci]}"
                    if ci and 0 < ci <= 20
                    else sinfo.get("name", "")
                )
            planet_info[cid] = {
                "name": pname,
                "celestialIndex": ci,
                "solarSystemID": sid,
            }

        self.cursor.execute("SELECT regionID, regionName, x, y, z FROM mapRegions")
        for rid, name, x, y, z in self.cursor.fetchall():
            rows.append(
                {
                    "itemID": rid,
                    "typeID": GROUP_REGION,
                    "groupID": GROUP_REGION,
                    "solarSystemID": None,
                    "constellationID": None,
                    "regionID": None,
                    "orbitID": None,
                    "x": x,
                    "y": y,
                    "z": z,
                    "radius": None,
                    "itemName": name,
                    "security": None,
                    "celestialIndex": None,
                    "orbitIndex": None,
                }
            )

        self.cursor.execute(
            "SELECT constellationID, constellationName, regionID, x, y, z FROM mapConstellations"
        )
        for cid, name, rid, x, y, z in self.cursor.fetchall():
            rows.append(
                {
                    "itemID": cid,
                    "typeID": GROUP_CONSTELLATION,
                    "groupID": GROUP_CONSTELLATION,
                    "solarSystemID": None,
                    "constellationID": None,
                    "regionID": rid,
                    "orbitID": None,
                    "x": x,
                    "y": y,
                    "z": z,
                    "radius": None,
                    "itemName": name,
                    "security": None,
                    "celestialIndex": None,
                    "orbitIndex": None,
                }
            )

        self.cursor.execute(
            "SELECT solarSystemID, solarSystemName, constellationID, regionID, radius, securityStatus, x, y, z FROM mapSolarSystems"
        )
        for sid, name, cid, rid, radius, sec, x, y, z in self.cursor.fetchall():
            rows.append(
                {
                    "itemID": sid,
                    "typeID": GROUP_SOLAR_SYSTEM,
                    "groupID": GROUP_SOLAR_SYSTEM,
                    "solarSystemID": None,
                    "constellationID": cid,
                    "regionID": rid,
                    "orbitID": None,
                    "x": x,
                    "y": y,
                    "z": z,
                    "radius": radius,
                    "itemName": name,
                    "security": sec,
                    "celestialIndex": None,
                    "orbitIndex": None,
                }
            )

        self.cursor.execute(
            "SELECT celestialID, solarSystemID, typeID, radius FROM mapStars"
        )
        for cid, sid, tid, radius in self.cursor.fetchall():
            sinfo = system_info.get(sid, {})
            name = f"{sinfo.get('name', '')} - Star"
            rows.append(
                {
                    "itemID": cid,
                    "typeID": tid,
                    "groupID": GROUP_STAR,
                    "solarSystemID": sid,
                    "constellationID": sinfo.get("constellationID"),
                    "regionID": sinfo.get("regionID"),
                    "orbitID": None,
                    "x": 0.0,
                    "y": 0.0,
                    "z": 0.0,
                    "radius": radius,
                    "itemName": name,
                    "security": sinfo.get("security"),
                    "celestialIndex": None,
                    "orbitIndex": None,
                }
            )

        self.cursor.execute(
            "SELECT celestialID, celestialIndex, orbitID, radius, solarSystemID, typeID, x, y, z, uniqueName FROM mapPlanets"
        )
        for cid, ci, oid, radius, sid, tid, x, y, z, uname in self.cursor.fetchall():
            sinfo = system_info.get(sid, {})
            if uname:
                name = uname
            else:
                name = (
                    f"{sinfo.get('name', '')} {ROMAN[ci]}"
                    if ci and 0 < ci <= 20
                    else None
                )
            rows.append(
                {
                    "itemID": cid,
                    "typeID": tid,
                    "groupID": GROUP_PLANET,
                    "solarSystemID": sid,
                    "constellationID": sinfo.get("constellationID"),
                    "regionID": sinfo.get("regionID"),
                    "orbitID": oid,
                    "x": x,
                    "y": y,
                    "z": z,
                    "radius": radius,
                    "itemName": name,
                    "security": sinfo.get("security"),
                    "celestialIndex": ci,
                    "orbitIndex": None,
                }
            )

        self.cursor.execute(
            "SELECT celestialID, celestialIndex, orbitID, orbitIndex, radius, solarSystemID, typeID, x, y, z, uniqueName FROM mapMoons"
        )
        for (
            cid,
            ci,
            oid,
            oi,
            radius,
            sid,
            tid,
            x,
            y,
            z,
            uname,
        ) in self.cursor.fetchall():
            sinfo = system_info.get(sid, {})
            if uname:
                name = uname
            else:
                pinfo = planet_info.get(oid, {})
                pname = pinfo.get("name")
                name = f"{pname} - Moon {oi}" if pname and oi else None
            rows.append(
                {
                    "itemID": cid,
                    "typeID": tid,
                    "groupID": GROUP_MOON,
                    "solarSystemID": sid,
                    "constellationID": sinfo.get("constellationID"),
                    "regionID": sinfo.get("regionID"),
                    "orbitID": oid,
                    "x": x,
                    "y": y,
                    "z": z,
                    "radius": radius,
                    "itemName": name,
                    "security": sinfo.get("security"),
                    "celestialIndex": ci,
                    "orbitIndex": oi,
                }
            )

        self.cursor.execute(
            "SELECT celestialID, celestialIndex, orbitID, orbitIndex, radius, solarSystemID, typeID, x, y, z, uniqueName FROM mapAsteroidBelts"
        )
        for (
            cid,
            ci,
            oid,
            oi,
            radius,
            sid,
            tid,
            x,
            y,
            z,
            uname,
        ) in self.cursor.fetchall():
            sinfo = system_info.get(sid, {})
            if uname:
                name = uname
            else:
                pinfo = planet_info.get(oid, {})
                pname = pinfo.get("name")
                name = f"{pname} - Asteroid Belt {oi}" if pname and oi else None
            rows.append(
                {
                    "itemID": cid,
                    "typeID": tid,
                    "groupID": GROUP_ASTEROID_BELT,
                    "solarSystemID": sid,
                    "constellationID": sinfo.get("constellationID"),
                    "regionID": sinfo.get("regionID"),
                    "orbitID": oid,
                    "x": x,
                    "y": y,
                    "z": z,
                    "radius": radius,
                    "itemName": name,
                    "security": sinfo.get("security"),
                    "celestialIndex": ci,
                    "orbitIndex": oi,
                }
            )

        dest_system_names = {}
        self.cursor.execute(
            "SELECT stargateID, destinationSolarSystemID FROM mapStargates"
        )
        for sgid, dsid in self.cursor.fetchall():
            if dsid:
                dest_system_names[sgid] = system_info.get(dsid, {}).get("name")

        self.cursor.execute(
            "SELECT stargateID, solarSystemID, typeID, x, y, z FROM mapStargates"
        )
        for sgid, sid, tid, x, y, z in self.cursor.fetchall():
            sinfo = system_info.get(sid, {})
            dname = dest_system_names.get(sgid)
            name = f"Stargate ({dname})" if dname else None
            rows.append(
                {
                    "itemID": sgid,
                    "typeID": tid,
                    "groupID": GROUP_STARGATE,
                    "solarSystemID": sid,
                    "constellationID": sinfo.get("constellationID"),
                    "regionID": sinfo.get("regionID"),
                    "orbitID": None,
                    "x": x,
                    "y": y,
                    "z": z,
                    "radius": None,
                    "itemName": name,
                    "security": sinfo.get("security"),
                    "celestialIndex": None,
                    "orbitIndex": None,
                }
            )

        self.cursor.execute(
            "SELECT stationID, solarSystemID, typeID, orbitID, x, y, z FROM staStations"
        )
        for stid, sid, tid, oid, x, y, z in self.cursor.fetchall():
            sinfo = system_info.get(sid, {})
            rows.append(
                {
                    "itemID": stid,
                    "typeID": tid,
                    "groupID": GROUP_STATION,
                    "solarSystemID": sid,
                    "constellationID": sinfo.get("constellationID"),
                    "regionID": sinfo.get("regionID"),
                    "orbitID": oid,
                    "x": x,
                    "y": y,
                    "z": z,
                    "radius": None,
                    "itemName": None,
                    "security": sinfo.get("security"),
                    "celestialIndex": None,
                    "orbitIndex": None,
                }
            )

        self.cursor.execute(
            "SELECT itemID, solarSystemID, typeID, x, y, z FROM mapSecondarySuns"
        )
        for iid, sid, tid, x, y, z in self.cursor.fetchall():
            sinfo = system_info.get(sid, {})
            rows.append(
                {
                    "itemID": iid,
                    "typeID": tid,
                    "groupID": GROUP_SECONDARY_SUN,
                    "solarSystemID": sid,
                    "constellationID": sinfo.get("constellationID"),
                    "regionID": sinfo.get("regionID"),
                    "orbitID": None,
                    "x": x,
                    "y": y,
                    "z": z,
                    "radius": None,
                    "itemName": None,
                    "security": sinfo.get("security"),
                    "celestialIndex": None,
                    "orbitIndex": None,
                }
            )

        columns = {
            "itemID": "INTEGER",
            "typeID": "INTEGER",
            "groupID": "INTEGER",
            "solarSystemID": "INTEGER",
            "constellationID": "INTEGER",
            "regionID": "INTEGER",
            "orbitID": "INTEGER",
            "x": "REAL",
            "y": "REAL",
            "z": "REAL",
            "radius": "REAL",
            "itemName": "TEXT",
            "security": "REAL",
            "celestialIndex": "INTEGER",
            "orbitIndex": "INTEGER",
        }
        table_name = "mapDenormalize"
        self.create_table(table_name, columns)
        if rows:
            self.insert_data(table_name, rows, list(columns.keys()))
        print(f"Derived {table_name} ({len(rows)} rows)")

    def process_compat_tables(self):
        if self.table_exists("invTypes"):
            self.cursor.execute("""
                CREATE TABLE invMetaTypes (
                    typeID INTEGER PRIMARY KEY NOT NULL,
                    parentTypeID INTEGER,
                    metaGroupID INTEGER
                )
            """)
            self.cursor.execute("""
                INSERT INTO invMetaTypes (typeID, parentTypeID, metaGroupID)
                SELECT typeID, variationParentTypeID, metaGroupID
                FROM invTypes WHERE metaGroupID IS NOT NULL
            """)
            count = self.cursor.execute("SELECT COUNT(*) FROM invMetaTypes").fetchone()[
                0
            ]
            print(f"Derived invMetaTypes ({count} rows)")
        else:
            print("Skipping invMetaTypes: invTypes table missing")

        if self.table_exists("mapDenormalize"):
            self.cursor.execute("""
                CREATE TABLE invItems (
                    itemID INTEGER PRIMARY KEY NOT NULL,
                    typeID INTEGER NOT NULL,
                    ownerID INTEGER NOT NULL,
                    locationID INTEGER NOT NULL,
                    flagID INTEGER NOT NULL,
                    quantity INTEGER NOT NULL
                )
            """)
            self.cursor.execute("""
                INSERT INTO invItems (itemID, typeID, ownerID, locationID, flagID, quantity)
                SELECT itemID, typeID,
                    CASE groupID
                        WHEN 15 THEN COALESCE(
                            (SELECT ownerID FROM staStations WHERE stationID = mapDenormalize.itemID), 1)
                        ELSE 1
                    END,
                    COALESCE(solarSystemID, COALESCE(constellationID, COALESCE(regionID, 0))),
                    0, -1
                FROM mapDenormalize
            """)
            self.cursor.execute(
                "CREATE INDEX ix_invItems_locationID ON invItems (locationID)"
            )
            self.cursor.execute(
                "CREATE INDEX items_IX_OwnerLocation ON invItems (ownerID, locationID)"
            )
            count = self.cursor.execute("SELECT COUNT(*) FROM invItems").fetchone()[0]
            print(f"Derived invItems ({count} rows)")

            self.cursor.execute("""
                CREATE TABLE invUniqueNames (
                    itemID INTEGER PRIMARY KEY NOT NULL,
                    itemName TEXT NOT NULL,
                    groupID INTEGER
                )
            """)
            self.cursor.execute("""
                INSERT INTO invUniqueNames (itemID, itemName, groupID)
                SELECT itemID, itemName, groupID
                FROM mapDenormalize WHERE itemName IS NOT NULL AND itemName != ''
            """)
            self.cursor.execute(
                "CREATE INDEX invUniqueNames_IX_GroupName ON invUniqueNames (groupID, itemName)"
            )
            self.cursor.execute(
                "CREATE INDEX ix_invUniqueNames_itemName ON invUniqueNames (itemName)"
            )
            count = self.cursor.execute(
                "SELECT COUNT(*) FROM invUniqueNames"
            ).fetchone()[0]
            print(f"Derived invUniqueNames ({count} rows)")
        else:
            print("Skipping invItems/invUniqueNames: mapDenormalize table missing")

        if self.table_exists("dgmTypeAttributes"):
            self.cursor.execute(
                "ALTER TABLE dgmTypeAttributes ADD COLUMN valueInt INTEGER"
            )
            self.cursor.execute(
                "ALTER TABLE dgmTypeAttributes ADD COLUMN valueFloat REAL"
            )
            self.cursor.execute("""
                UPDATE dgmTypeAttributes SET
                    valueFloat = value,
                    valueInt = CASE WHEN value = CAST(value AS INTEGER) THEN CAST(value AS INTEGER) ELSE NULL END
            """)
            print("Added valueInt/valueFloat columns to dgmTypeAttributes")
        else:
            print("Skipping dgmTypeAttributes compat columns: table missing")

        if self.table_exists("mapSolarSystems"):
            self.cursor.execute(
                "ALTER TABLE mapSolarSystems ADD COLUMN sunTypeID INTEGER"
            )
            if self.table_exists("mapStars"):
                self.cursor.execute("""
                    UPDATE mapSolarSystems SET sunTypeID = (
                        SELECT typeID FROM mapStars WHERE mapStars.solarSystemID = mapSolarSystems.solarSystemID
                    )
                """)
            print("Added sunTypeID column to mapSolarSystems")

            self.cursor.execute("ALTER TABLE mapSolarSystems ADD COLUMN security REAL")
            self.cursor.execute("UPDATE mapSolarSystems SET security = securityStatus")
            print("Added security alias column to mapSolarSystems")
        else:
            print("Skipping mapSolarSystems compat columns: table missing")

    def import_sde(self):
        files = [
            m
            for m in self._members
            if m.startswith(self._prefix) and m.endswith(".jsonl")
        ]
        failed_tables = []
        for file in files:
            try:
                self.process_file(file)
            except Exception as e:
                base_name = file.rsplit("/", 1)[-1].removesuffix(".jsonl")
                table_name = table_mapping.get(base_name, base_name)
                failed_tables.append(table_name)
                print(f"Failed {file}: {e}")
        if failed_tables:
            print(
                f"WARNING: {len(failed_tables)} table(s) failed to import: {', '.join(failed_tables)}"
            )
        self.process_derived_tables()
        self.process_blueprint_activities()
        self.process_certificate_tables()
        self.process_research_fields()
        self.process_celestial_statistics()
        self.process_celestial_graphics()
        self.process_jump_tables()
        self.process_traits()
        self.process_wormhole_classes()
        self.process_freelance_job_schemas()
        self.process_dbuff_modifiers()
        self.process_map_denormalize()
        self.process_compat_tables()
        self.create_indexes()
        self.conn.commit()
        print("SDE import complete")


SDE_LATEST_URL = "https://developers.eveonline.com/static-data/eve-online-static-data-latest-jsonl.zip"
SDE_BUILD_URL = "https://developers.eveonline.com/static-data/tranquility/eve-online-static-data-{build}-jsonl.zip"


def download_sde(build=None):
    url = SDE_BUILD_URL.format(build=build) if build else SDE_LATEST_URL
    print(f"Downloading SDE from {url}")
    data_dir = Path("./data")
    data_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = data_dir / "_download.zip"
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "eve-sde-importer/1.0"}
        )
        with urllib.request.urlopen(req) as resp:
            total = resp.headers.get("Content-Length")
            total = int(total) if total else None
            downloaded = 0
            with open(tmp_path, "wb") as f:
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = downloaded * 100 // total
                        print(
                            f"\r  {downloaded // (1024 * 1024)}MB / {total // (1024 * 1024)}MB ({pct}%)",
                            end="",
                            flush=True,
                        )
                    else:
                        print(
                            f"\r  {downloaded // (1024 * 1024)}MB", end="", flush=True
                        )
            print()
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise
    final_url = resp.url if hasattr(resp, "url") else url
    filename = (
        final_url.rsplit("/", 1)[-1]
        if "/" in final_url
        else "eve-online-static-data-latest-jsonl.zip"
    )
    final_path = data_dir / filename
    tmp_path.replace(final_path)
    print(f"Saved to {final_path}")
    return final_path


def main():
    parser = argparse.ArgumentParser(
        description="Import EVE Online SDE (JSONL zip) into SQLite"
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--download",
        nargs="?",
        const="latest",
        metavar="BUILD",
        help="Download SDE zip and import (optionally specify a build number)",
    )
    source.add_argument(
        "--input",
        metavar="ZIP",
        help="Path to a local SDE zip file",
    )
    parser.add_argument(
        "--output-dir",
        metavar="DIR",
        default=".",
        help="Output directory for sde-{build}.sqlite (default: current directory)",
    )
    parser.add_argument(
        "--delete-zip-after",
        action="store_true",
        help="Delete the zip file after successful import",
    )
    args = parser.parse_args()

    if args.download is not None:
        build = None if args.download == "latest" else args.download
        zip_path = download_sde(build)
    else:
        zip_path = Path(args.input)
        if not zip_path.is_file():
            parser.error(f"File not found: {zip_path}")

    zf = zipfile.ZipFile(zip_path, "r")

    build_number = get_build_number(zf)

    output_dir = Path(args.output_dir)
    db_path = output_dir / f"sde-{build_number}.sqlite"

    tmp_db_path = db_path.with_suffix(".sqlite.tmp")

    print(f"SDE build {build_number} -> {db_path}")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if tmp_db_path.exists():
        tmp_db_path.unlink()
    conn = sqlite3.connect(tmp_db_path)

    success = False
    try:
        importer = SdeImporter(zf, conn)
        importer.import_sde()
        success = True
    finally:
        conn.close()
        zf.close()
        if success:
            tmp_db_path.replace(db_path)
            if args.delete_zip_after:
                Path(zip_path).unlink()
                print(f"Deleted {zip_path}")
        else:
            if tmp_db_path.exists():
                tmp_db_path.unlink()


if __name__ == "__main__":
    main()
