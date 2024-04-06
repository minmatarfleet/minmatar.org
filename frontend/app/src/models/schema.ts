import { sqliteTable, AnySQLiteColumn, integer, numeric, real, index, primaryKey, text, uniqueIndex } from "drizzle-orm/sqlite-core"
  import { sql } from "drizzle-orm"

export const crpNpcCorporations = sqliteTable("crpNPCCorporations", {
	corporationId: integer("corporationID").primaryKey().notNull(),
	size: numeric("size"),
	extent: numeric("extent"),
	solarSystemId: integer("solarSystemID"),
	investorId1: integer("investorID1"),
	investorShares1: integer("investorShares1"),
	investorId2: integer("investorID2"),
	investorShares2: integer("investorShares2"),
	investorId3: integer("investorID3"),
	investorShares3: integer("investorShares3"),
	investorId4: integer("investorID4"),
	investorShares4: integer("investorShares4"),
	friendId: integer("friendID"),
	enemyId: integer("enemyID"),
	publicShares: integer("publicShares"),
	initialPrice: integer("initialPrice"),
	minSecurity: real("minSecurity"),
	scattered: numeric("scattered"),
	fringe: integer("fringe"),
	corridor: integer("corridor"),
	hub: integer("hub"),
	border: integer("border"),
	factionId: integer("factionID"),
	sizeFactor: real("sizeFactor"),
	stationCount: integer("stationCount"),
	stationSystemCount: integer("stationSystemCount"),
	description: numeric("description"),
	iconId: integer("iconID"),
});

export const staOperations = sqliteTable("staOperations", {
	activityId: integer("activityID"),
	operationId: integer("operationID").primaryKey().notNull(),
	operationName: numeric("operationName"),
	description: numeric("description"),
	fringe: integer("fringe"),
	corridor: integer("corridor"),
	hub: integer("hub"),
	border: integer("border"),
	ratio: integer("ratio"),
	caldariStationTypeId: integer("caldariStationTypeID"),
	minmatarStationTypeId: integer("minmatarStationTypeID"),
	amarrStationTypeId: integer("amarrStationTypeID"),
	gallenteStationTypeId: integer("gallenteStationTypeID"),
	joveStationTypeId: integer("joveStationTypeID"),
});

export const invVolumes = sqliteTable("invVolumes", {
	typeId: integer("typeID").primaryKey().notNull(),
	volume: integer("volume"),
});

export const industryActivityProbabilities = sqliteTable("industryActivityProbabilities", {
	typeId: integer("typeID"),
	activityId: integer("activityID"),
	productTypeId: integer("productTypeID"),
	probability: numeric("probability"),
},
(table) => {
	return {
		ixIndustryActivityProbabilitiesProductTypeId: index("ix_industryActivityProbabilities_productTypeID").on(table.productTypeId),
		ixIndustryActivityProbabilitiesTypeId: index("ix_industryActivityProbabilities_typeID").on(table.typeId),
	}
});

export const ramAssemblyLineStations = sqliteTable("ramAssemblyLineStations", {
	stationId: integer("stationID").notNull(),
	assemblyLineTypeId: integer("assemblyLineTypeID").notNull(),
	quantity: integer("quantity"),
	stationTypeId: integer("stationTypeID"),
	ownerId: integer("ownerID"),
	solarSystemId: integer("solarSystemID"),
	regionId: integer("regionID"),
},
(table) => {
	return {
		ixRamAssemblyLineStationsSolarSystemId: index("ix_ramAssemblyLineStations_solarSystemID").on(table.solarSystemId),
		ixRamAssemblyLineStationsOwnerId: index("ix_ramAssemblyLineStations_ownerID").on(table.ownerId),
		ixRamAssemblyLineStationsRegionId: index("ix_ramAssemblyLineStations_regionID").on(table.regionId),
		pk0: primaryKey({ columns: [table.assemblyLineTypeId, table.stationId], name: "ramAssemblyLineStations_assemblyLineTypeID_stationID_pk"})
	}
});

export const ramAssemblyLineTypes = sqliteTable("ramAssemblyLineTypes", {
	assemblyLineTypeId: integer("assemblyLineTypeID").primaryKey().notNull(),
	assemblyLineTypeName: numeric("assemblyLineTypeName"),
	description: numeric("description"),
	baseTimeMultiplier: real("baseTimeMultiplier"),
	baseMaterialMultiplier: real("baseMaterialMultiplier"),
	baseCostMultiplier: real("baseCostMultiplier"),
	volume: real("volume"),
	activityId: integer("activityID"),
	minCostPerHour: real("minCostPerHour"),
});

export const invMarketGroups = sqliteTable("invMarketGroups", {
	marketGroupId: integer("marketGroupID").primaryKey().notNull(),
	parentGroupId: integer("parentGroupID"),
	marketGroupName: numeric("marketGroupName"),
	description: numeric("description"),
	iconId: integer("iconID"),
	hasTypes: numeric("hasTypes"),
});

export const trnTranslationLanguages = sqliteTable("trnTranslationLanguages", {
	numericLanguageId: integer("numericLanguageID").primaryKey().notNull(),
	languageId: numeric("languageID"),
	languageName: numeric("languageName"),
});

export const chrAttributes = sqliteTable("chrAttributes", {
	attributeId: integer("attributeID").primaryKey().notNull(),
	attributeName: numeric("attributeName"),
	description: numeric("description"),
	iconId: integer("iconID"),
	shortDescription: numeric("shortDescription"),
	notes: numeric("notes"),
});

export const industryActivityProducts = sqliteTable("industryActivityProducts", {
	typeId: integer("typeID"),
	activityId: integer("activityID"),
	productTypeId: integer("productTypeID"),
	quantity: integer("quantity"),
},
(table) => {
	return {
		ixIndustryActivityProductsProductTypeId: index("ix_industryActivityProducts_productTypeID").on(table.productTypeId),
		ixIndustryActivityProductsTypeId: index("ix_industryActivityProducts_typeID").on(table.typeId),
	}
});

export const planetSchematicsPinMap = sqliteTable("planetSchematicsPinMap", {
	schematicId: integer("schematicID").notNull(),
	pinTypeId: integer("pinTypeID").notNull(),
},
(table) => {
	return {
		pk0: primaryKey({ columns: [table.pinTypeId, table.schematicId], name: "planetSchematicsPinMap_pinTypeID_schematicID_pk"})
	}
});

export const mapRegionJumps = sqliteTable("mapRegionJumps", {
	fromRegionId: integer("fromRegionID").notNull(),
	toRegionId: integer("toRegionID").notNull(),
},
(table) => {
	return {
		pk0: primaryKey({ columns: [table.fromRegionId, table.toRegionId], name: "mapRegionJumps_fromRegionID_toRegionID_pk"})
	}
});

export const skinMaterials = sqliteTable("skinMaterials", {
	skinMaterialId: integer("skinMaterialID").primaryKey().notNull(),
	displayNameId: integer("displayNameID"),
	materialSetId: integer("materialSetID"),
});

export const mapSolarSystems = sqliteTable("mapSolarSystems", {
	regionId: integer("regionID"),
	constellationId: integer("constellationID"),
	solarSystemId: integer("solarSystemID").primaryKey().notNull(),
	solarSystemName: numeric("solarSystemName"),
	x: real("x"),
	y: real("y"),
	z: real("z"),
	xMin: real("xMin"),
	xMax: real("xMax"),
	yMin: real("yMin"),
	yMax: real("yMax"),
	zMin: real("zMin"),
	zMax: real("zMax"),
	luminosity: real("luminosity"),
	border: numeric("border"),
	fringe: numeric("fringe"),
	corridor: numeric("corridor"),
	hub: numeric("hub"),
	international: numeric("international"),
	regional: numeric("regional"),
	constellation: numeric("constellation"),
	security: real("security"),
	factionId: integer("factionID"),
	radius: real("radius"),
	sunTypeId: integer("sunTypeID"),
	securityClass: numeric("securityClass"),
},
(table) => {
	return {
		ixMapSolarSystemsConstellationId: index("ix_mapSolarSystems_constellationID").on(table.constellationId),
		ixMapSolarSystemsRegionId: index("ix_mapSolarSystems_regionID").on(table.regionId),
		ixMapSolarSystemsSecurity: index("ix_mapSolarSystems_security").on(table.security),
	}
});

export const trnTranslationColumns = sqliteTable("trnTranslationColumns", {
	tcGroupId: integer("tcGroupID"),
	tcId: integer("tcID").primaryKey().notNull(),
	tableName: numeric("tableName").notNull(),
	columnName: numeric("columnName").notNull(),
	masterId: numeric("masterID"),
});

export const eveIcons = sqliteTable("eveIcons", {
	iconId: integer("iconID").primaryKey().notNull(),
	iconFile: numeric("iconFile"),
	description: text("description"),
});

export const mapRegions = sqliteTable("mapRegions", {
	regionId: integer("regionID").primaryKey().notNull(),
	regionName: numeric("regionName"),
	x: real("x"),
	y: real("y"),
	z: real("z"),
	xMin: real("xMin"),
	xMax: real("xMax"),
	yMin: real("yMin"),
	yMax: real("yMax"),
	zMin: real("zMin"),
	zMax: real("zMax"),
	factionId: integer("factionID"),
	nebula: integer("nebula"),
	radius: real("radius"),
});

export const industryActivityRaces = sqliteTable("industryActivityRaces", {
	typeId: integer("typeID"),
	activityId: integer("activityID"),
	productTypeId: integer("productTypeID"),
	raceId: integer("raceID"),
},
(table) => {
	return {
		ixIndustryActivityRacesProductTypeId: index("ix_industryActivityRaces_productTypeID").on(table.productTypeId),
		ixIndustryActivityRacesTypeId: index("ix_industryActivityRaces_typeID").on(table.typeId),
	}
});

export const skins = sqliteTable("skins", {
	skinId: integer("skinID").primaryKey().notNull(),
	internalName: numeric("internalName"),
	skinMaterialId: integer("skinMaterialID"),
});

export const invTypeReactions = sqliteTable("invTypeReactions", {
	reactionTypeId: integer("reactionTypeID").notNull(),
	input: numeric("input").notNull(),
	typeId: integer("typeID").notNull(),
	quantity: integer("quantity"),
},
(table) => {
	return {
		pk0: primaryKey({ columns: [table.input, table.reactionTypeId, table.typeId], name: "invTypeReactions_input_reactionTypeID_typeID_pk"})
	}
});

export const eveUnits = sqliteTable("eveUnits", {
	unitId: integer("unitID").primaryKey().notNull(),
	unitName: numeric("unitName"),
	displayName: numeric("displayName"),
	description: numeric("description"),
});

export const agtAgentTypes = sqliteTable("agtAgentTypes", {
	agentTypeId: integer("agentTypeID").primaryKey().notNull(),
	agentType: numeric("agentType"),
});

export const planetSchematicsTypeMap = sqliteTable("planetSchematicsTypeMap", {
	schematicId: integer("schematicID").notNull(),
	typeId: integer("typeID").notNull(),
	quantity: integer("quantity"),
	isInput: numeric("isInput"),
},
(table) => {
	return {
		pk0: primaryKey({ columns: [table.schematicId, table.typeId], name: "planetSchematicsTypeMap_schematicID_typeID_pk"})
	}
});

export const ramInstallationTypeContents = sqliteTable("ramInstallationTypeContents", {
	installationTypeId: integer("installationTypeID").notNull(),
	assemblyLineTypeId: integer("assemblyLineTypeID").notNull(),
	quantity: integer("quantity"),
},
(table) => {
	return {
		pk0: primaryKey({ columns: [table.assemblyLineTypeId, table.installationTypeId], name: "ramInstallationTypeContents_assemblyLineTypeID_installationTypeID_pk"})
	}
});

export const invUniqueNames = sqliteTable("invUniqueNames", {
	itemId: integer("itemID").primaryKey().notNull(),
	itemName: numeric("itemName").notNull(),
	groupId: integer("groupID"),
},
(table) => {
	return {
		ixGroupName: index("invUniqueNames_IX_GroupName").on(table.groupId, table.itemName),
		ixInvUniqueNamesItemName: uniqueIndex("ix_invUniqueNames_itemName").on(table.itemName),
	}
});

export const chrAncestries = sqliteTable("chrAncestries", {
	ancestryId: integer("ancestryID").primaryKey().notNull(),
	ancestryName: numeric("ancestryName"),
	bloodlineId: integer("bloodlineID"),
	description: numeric("description"),
	perception: integer("perception"),
	willpower: integer("willpower"),
	charisma: integer("charisma"),
	memory: integer("memory"),
	intelligence: integer("intelligence"),
	iconId: integer("iconID"),
	shortDescription: numeric("shortDescription"),
});

export const mapLocationScenes = sqliteTable("mapLocationScenes", {
	locationId: integer("locationID").primaryKey().notNull(),
	graphicId: integer("graphicID"),
});

export const invTypes = sqliteTable("invTypes", {
	typeId: integer("typeID").primaryKey().notNull(),
	groupId: integer("groupID"),
	typeName: numeric("typeName"),
	description: text("description"),
	mass: real("mass"),
	volume: real("volume"),
	capacity: real("capacity"),
	portionSize: integer("portionSize"),
	raceId: integer("raceID"),
	basePrice: numeric("basePrice"),
	published: numeric("published"),
	marketGroupId: integer("marketGroupID"),
	iconId: integer("iconID"),
	soundId: integer("soundID"),
	graphicId: integer("graphicID"),
},
(table) => {
	return {
		ixInvTypesGroupId: index("ix_invTypes_groupID").on(table.groupId),
	}
});

export const industryActivity = sqliteTable("industryActivity", {
	typeId: integer("typeID").notNull(),
	activityId: integer("activityID").notNull(),
	time: integer("time"),
},
(table) => {
	return {
		ixIndustryActivityActivityId: index("ix_industryActivity_activityID").on(table.activityId),
		pk0: primaryKey({ columns: [table.activityId, table.typeId], name: "industryActivity_activityID_typeID_pk"})
	}
});

export const invControlTowerResources = sqliteTable("invControlTowerResources", {
	controlTowerTypeId: integer("controlTowerTypeID").notNull(),
	resourceTypeId: integer("resourceTypeID").notNull(),
	purpose: integer("purpose"),
	quantity: integer("quantity"),
	minSecurityLevel: real("minSecurityLevel"),
	factionId: integer("factionID"),
},
(table) => {
	return {
		pk0: primaryKey({ columns: [table.controlTowerTypeId, table.resourceTypeId], name: "invControlTowerResources_controlTowerTypeID_resourceTypeID_pk"})
	}
});

export const mapJumps = sqliteTable("mapJumps", {
	stargateId: integer("stargateID").primaryKey().notNull(),
	destinationId: integer("destinationID"),
});

export const certCerts = sqliteTable("certCerts", {
	certId: integer("certID").primaryKey().notNull(),
	description: text("description"),
	groupId: integer("groupID"),
	name: numeric("name"),
});

export const industryBlueprints = sqliteTable("industryBlueprints", {
	typeId: integer("typeID").primaryKey().notNull(),
	maxProductionLimit: integer("maxProductionLimit"),
});

export const invTypeMaterials = sqliteTable("invTypeMaterials", {
	typeId: integer("typeID").notNull(),
	materialTypeId: integer("materialTypeID").notNull(),
	quantity: integer("quantity").notNull(),
},
(table) => {
	return {
		pk0: primaryKey({ columns: [table.materialTypeId, table.typeId], name: "invTypeMaterials_materialTypeID_typeID_pk"})
	}
});

export const ramAssemblyLineTypeDetailPerGroup = sqliteTable("ramAssemblyLineTypeDetailPerGroup", {
	assemblyLineTypeId: integer("assemblyLineTypeID").notNull(),
	groupId: integer("groupID").notNull(),
	timeMultiplier: real("timeMultiplier"),
	materialMultiplier: real("materialMultiplier"),
	costMultiplier: real("costMultiplier"),
},
(table) => {
	return {
		pk0: primaryKey({ columns: [table.assemblyLineTypeId, table.groupId], name: "ramAssemblyLineTypeDetailPerGroup_assemblyLineTypeID_groupID_pk"})
	}
});

export const trnTranslations = sqliteTable("trnTranslations", {
	tcId: integer("tcID").notNull(),
	keyId: integer("keyID").notNull(),
	languageId: numeric("languageID").notNull(),
	text: text("text").notNull(),
},
(table) => {
	return {
		pk0: primaryKey({ columns: [table.keyId, table.languageId, table.tcId], name: "trnTranslations_keyID_languageID_tcID_pk"})
	}
});

export const dgmAttributeTypes = sqliteTable("dgmAttributeTypes", {
	attributeId: integer("attributeID").primaryKey().notNull(),
	attributeName: numeric("attributeName"),
	description: numeric("description"),
	iconId: integer("iconID"),
	defaultValue: real("defaultValue"),
	published: numeric("published"),
	displayName: numeric("displayName"),
	unitId: integer("unitID"),
	stackable: numeric("stackable"),
	highIsGood: numeric("highIsGood"),
	categoryId: integer("categoryID"),
});

export const agtResearchAgents = sqliteTable("agtResearchAgents", {
	agentId: integer("agentID").notNull(),
	typeId: integer("typeID").notNull(),
},
(table) => {
	return {
		ixAgtResearchAgentsTypeId: index("ix_agtResearchAgents_typeID").on(table.typeId),
		pk0: primaryKey({ columns: [table.agentId, table.typeId], name: "agtResearchAgents_agentID_typeID_pk"})
	}
});

export const mapSolarSystemJumps = sqliteTable("mapSolarSystemJumps", {
	fromRegionId: integer("fromRegionID"),
	fromConstellationId: integer("fromConstellationID"),
	fromSolarSystemId: integer("fromSolarSystemID").notNull(),
	toSolarSystemId: integer("toSolarSystemID").notNull(),
	toConstellationId: integer("toConstellationID"),
	toRegionId: integer("toRegionID"),
},
(table) => {
	return {
		pk0: primaryKey({ columns: [table.fromSolarSystemId, table.toSolarSystemId], name: "mapSolarSystemJumps_fromSolarSystemID_toSolarSystemID_pk"})
	}
});

export const mapCelestialStatistics = sqliteTable("mapCelestialStatistics", {
	celestialId: integer("celestialID").primaryKey().notNull(),
	temperature: real("temperature"),
	spectralClass: numeric("spectralClass"),
	luminosity: real("luminosity"),
	age: real("age"),
	life: real("life"),
	orbitRadius: real("orbitRadius"),
	eccentricity: real("eccentricity"),
	massDust: real("massDust"),
	massGas: real("massGas"),
	fragmented: numeric("fragmented"),
	density: real("density"),
	surfaceGravity: real("surfaceGravity"),
	escapeVelocity: real("escapeVelocity"),
	orbitPeriod: real("orbitPeriod"),
	rotationRate: real("rotationRate"),
	locked: numeric("locked"),
	pressure: real("pressure"),
	radius: real("radius"),
	mass: integer("mass"),
});

export const mapConstellationJumps = sqliteTable("mapConstellationJumps", {
	fromRegionId: integer("fromRegionID"),
	fromConstellationId: integer("fromConstellationID").notNull(),
	toConstellationId: integer("toConstellationID").notNull(),
	toRegionId: integer("toRegionID"),
},
(table) => {
	return {
		pk0: primaryKey({ columns: [table.fromConstellationId, table.toConstellationId], name: "mapConstellationJumps_fromConstellationID_toConstellationID_pk"})
	}
});

export const mapCelestialGraphics = sqliteTable("mapCelestialGraphics", {
	celestialId: integer("celestialID").primaryKey().notNull(),
	heightMap1: integer("heightMap1"),
	heightMap2: integer("heightMap2"),
	shaderPreset: integer("shaderPreset"),
	population: numeric("population"),
});

export const staServices = sqliteTable("staServices", {
	serviceId: integer("serviceID").primaryKey().notNull(),
	serviceName: numeric("serviceName"),
	description: numeric("description"),
});

export const warCombatZoneSystems = sqliteTable("warCombatZoneSystems", {
	solarSystemId: integer("solarSystemID").primaryKey().notNull(),
	combatZoneId: integer("combatZoneID"),
});

export const industryActivityMaterials = sqliteTable("industryActivityMaterials", {
	typeId: integer("typeID"),
	activityId: integer("activityID"),
	materialTypeId: integer("materialTypeID"),
	quantity: integer("quantity"),
},
(table) => {
	return {
		idx1: index("industryActivityMaterials_idx1").on(table.typeId, table.activityId),
		ixIndustryActivityMaterialsTypeId: index("ix_industryActivityMaterials_typeID").on(table.typeId),
	}
});

export const mapLandmarks = sqliteTable("mapLandmarks", {
	landmarkId: integer("landmarkID").primaryKey().notNull(),
	landmarkName: numeric("landmarkName"),
	description: text("description"),
	locationId: integer("locationID"),
	x: real("x"),
	y: real("y"),
	z: real("z"),
	iconId: integer("iconID"),
});

export const invFlags = sqliteTable("invFlags", {
	flagId: integer("flagID").primaryKey().notNull(),
	flagName: numeric("flagName"),
	flagText: numeric("flagText"),
	orderId: integer("orderID"),
});

export const invContrabandTypes = sqliteTable("invContrabandTypes", {
	factionId: integer("factionID").notNull(),
	typeId: integer("typeID").notNull(),
	standingLoss: real("standingLoss"),
	confiscateMinSec: real("confiscateMinSec"),
	fineByValue: real("fineByValue"),
	attackMinSec: real("attackMinSec"),
},
(table) => {
	return {
		ixInvContrabandTypesTypeId: index("ix_invContrabandTypes_typeID").on(table.typeId),
		pk0: primaryKey({ columns: [table.factionId, table.typeId], name: "invContrabandTypes_factionID_typeID_pk"})
	}
});

export const invControlTowerResourcePurposes = sqliteTable("invControlTowerResourcePurposes", {
	purpose: integer("purpose").primaryKey().notNull(),
	purposeText: numeric("purposeText"),
});

export const staStationTypes = sqliteTable("staStationTypes", {
	stationTypeId: integer("stationTypeID").primaryKey().notNull(),
	dockEntryX: real("dockEntryX"),
	dockEntryY: real("dockEntryY"),
	dockEntryZ: real("dockEntryZ"),
	dockOrientationX: real("dockOrientationX"),
	dockOrientationY: real("dockOrientationY"),
	dockOrientationZ: real("dockOrientationZ"),
	operationId: integer("operationID"),
	officeSlots: integer("officeSlots"),
	reprocessingEfficiency: real("reprocessingEfficiency"),
	conquerable: numeric("conquerable"),
});

export const invTraits = sqliteTable("invTraits", {
	traitId: integer("traitID").primaryKey().notNull(),
	typeId: integer("typeID"),
	skillId: integer("skillID"),
	bonus: real("bonus"),
	bonusText: text("bonusText"),
	unitId: integer("unitID"),
});

export const invPositions = sqliteTable("invPositions", {
	itemId: integer("itemID").primaryKey().notNull(),
	x: real("x").notNull(),
	y: real("y").notNull(),
	z: real("z").notNull(),
	yaw: real("yaw"),
	pitch: real("pitch"),
	roll: real("roll"),
});

export const certSkills = sqliteTable("certSkills", {
	certId: integer("certID"),
	skillId: integer("skillID"),
	certLevelInt: integer("certLevelInt"),
	skillLevel: integer("skillLevel"),
	certLevelText: numeric("certLevelText"),
},
(table) => {
	return {
		ixCertSkillsSkillId: index("ix_certSkills_skillID").on(table.skillId),
	}
});

export const skinLicense = sqliteTable("skinLicense", {
	licenseTypeId: integer("licenseTypeID").primaryKey().notNull(),
	duration: integer("duration"),
	skinId: integer("skinID"),
});

export const dgmTypeAttributes = sqliteTable("dgmTypeAttributes", {
	typeId: integer("typeID").notNull(),
	attributeId: integer("attributeID").notNull(),
	valueInt: integer("valueInt"),
	valueFloat: real("valueFloat"),
},
(table) => {
	return {
		ixDgmTypeAttributesAttributeId: index("ix_dgmTypeAttributes_attributeID").on(table.attributeId),
		pk0: primaryKey({ columns: [table.attributeId, table.typeId], name: "dgmTypeAttributes_attributeID_typeID_pk"})
	}
});

export const mapConstellations = sqliteTable("mapConstellations", {
	regionId: integer("regionID"),
	constellationId: integer("constellationID").primaryKey().notNull(),
	constellationName: numeric("constellationName"),
	x: real("x"),
	y: real("y"),
	z: real("z"),
	xMin: real("xMin"),
	xMax: real("xMax"),
	yMin: real("yMin"),
	yMax: real("yMax"),
	zMin: real("zMin"),
	zMax: real("zMax"),
	factionId: integer("factionID"),
	radius: real("radius"),
});

export const crpNpcCorporationDivisions = sqliteTable("crpNPCCorporationDivisions", {
	corporationId: integer("corporationID").notNull(),
	divisionId: integer("divisionID").notNull(),
	size: integer("size"),
},
(table) => {
	return {
		pk0: primaryKey({ columns: [table.corporationId, table.divisionId], name: "crpNPCCorporationDivisions_corporationID_divisionID_pk"})
	}
});

export const dgmAttributeCategories = sqliteTable("dgmAttributeCategories", {
	categoryId: integer("categoryID").primaryKey().notNull(),
	categoryName: numeric("categoryName"),
	categoryDescription: numeric("categoryDescription"),
});

export const translationTables = sqliteTable("translationTables", {
	sourceTable: numeric("sourceTable").notNull(),
	destinationTable: numeric("destinationTable"),
	translatedKey: numeric("translatedKey").notNull(),
	tcGroupId: integer("tcGroupID"),
	tcId: integer("tcID"),
},
(table) => {
	return {
		pk0: primaryKey({ columns: [table.sourceTable, table.translatedKey], name: "translationTables_sourceTable_translatedKey_pk"})
	}
});

export const planetSchematics = sqliteTable("planetSchematics", {
	schematicId: integer("schematicID").primaryKey().notNull(),
	schematicName: numeric("schematicName"),
	cycleTime: integer("cycleTime"),
});

export const invMetaTypes = sqliteTable("invMetaTypes", {
	typeId: integer("typeID").primaryKey().notNull(),
	parentTypeId: integer("parentTypeID"),
	metaGroupId: integer("metaGroupID"),
});

export const certMasteries = sqliteTable("certMasteries", {
	typeId: integer("typeID"),
	masteryLevel: integer("masteryLevel"),
	certId: integer("certID"),
});

export const crpNpcCorporationResearchFields = sqliteTable("crpNPCCorporationResearchFields", {
	skillId: integer("skillID").notNull(),
	corporationId: integer("corporationID").notNull(),
},
(table) => {
	return {
		pk0: primaryKey({ columns: [table.corporationId, table.skillId], name: "crpNPCCorporationResearchFields_corporationID_skillID_pk"})
	}
});

export const crpNpcDivisions = sqliteTable("crpNPCDivisions", {
	divisionId: integer("divisionID").primaryKey().notNull(),
	divisionName: numeric("divisionName"),
	description: numeric("description"),
	leaderType: numeric("leaderType"),
});

export const dgmTypeEffects = sqliteTable("dgmTypeEffects", {
	typeId: integer("typeID").notNull(),
	effectId: integer("effectID").notNull(),
	isDefault: numeric("isDefault"),
},
(table) => {
	return {
		pk0: primaryKey({ columns: [table.effectId, table.typeId], name: "dgmTypeEffects_effectID_typeID_pk"})
	}
});

export const invNames = sqliteTable("invNames", {
	itemId: integer("itemID").primaryKey().notNull(),
	itemName: numeric("itemName").notNull(),
});

export const mapDenormalize = sqliteTable("mapDenormalize", {
	itemId: integer("itemID").primaryKey().notNull(),
	typeId: integer("typeID"),
	groupId: integer("groupID"),
	solarSystemId: integer("solarSystemID"),
	constellationId: integer("constellationID"),
	regionId: integer("regionID"),
	orbitId: integer("orbitID"),
	x: real("x"),
	y: real("y"),
	z: real("z"),
	radius: real("radius"),
	itemName: numeric("itemName"),
	security: real("security"),
	celestialIndex: integer("celestialIndex"),
	orbitIndex: integer("orbitIndex"),
},
(table) => {
	return {
		ixMapDenormalizeTypeId: index("ix_mapDenormalize_typeID").on(table.typeId),
		ixMapDenormalizeSolarSystemId: index("ix_mapDenormalize_solarSystemID").on(table.solarSystemId),
		ixMapDenormalizeRegionId: index("ix_mapDenormalize_regionID").on(table.regionId),
		ixGroupRegion: index("mapDenormalize_IX_groupRegion").on(table.groupId, table.regionId),
		ixGroupConstellation: index("mapDenormalize_IX_groupConstellation").on(table.groupId, table.constellationId),
		ixGroupSystem: index("mapDenormalize_IX_groupSystem").on(table.groupId, table.solarSystemId),
		ixMapDenormalizeConstellationId: index("ix_mapDenormalize_constellationID").on(table.constellationId),
		ixMapDenormalizeOrbitId: index("ix_mapDenormalize_orbitID").on(table.orbitId),
	}
});

export const chrRaces = sqliteTable("chrRaces", {
	raceId: integer("raceID").primaryKey().notNull(),
	raceName: numeric("raceName"),
	description: numeric("description"),
	iconId: integer("iconID"),
	shortDescription: numeric("shortDescription"),
});

export const agtAgentsInSpace = sqliteTable("agtAgentsInSpace", {
	agentId: integer("agentID").primaryKey().notNull(),
	dungeonId: integer("dungeonID"),
	solarSystemId: integer("solarSystemID"),
	spawnPointId: integer("spawnPointID"),
	typeId: integer("typeID"),
},
(table) => {
	return {
		ixAgtAgentsInSpaceSolarSystemId: index("ix_agtAgentsInSpace_solarSystemID").on(table.solarSystemId),
	}
});

export const crpActivities = sqliteTable("crpActivities", {
	activityId: integer("activityID").primaryKey().notNull(),
	activityName: numeric("activityName"),
	description: numeric("description"),
});

export const chrFactions = sqliteTable("chrFactions", {
	factionId: integer("factionID").primaryKey().notNull(),
	factionName: numeric("factionName"),
	description: numeric("description"),
	raceIds: integer("raceIDs"),
	solarSystemId: integer("solarSystemID"),
	corporationId: integer("corporationID"),
	sizeFactor: real("sizeFactor"),
	stationCount: integer("stationCount"),
	stationSystemCount: integer("stationSystemCount"),
	militiaCorporationId: integer("militiaCorporationID"),
	iconId: integer("iconID"),
});

export const eveGraphics = sqliteTable("eveGraphics", {
	graphicId: integer("graphicID").primaryKey().notNull(),
	sofFactionName: numeric("sofFactionName"),
	graphicFile: numeric("graphicFile"),
	sofHullName: numeric("sofHullName"),
	sofRaceName: numeric("sofRaceName"),
	description: text("description"),
});

export const invCategories = sqliteTable("invCategories", {
	categoryId: integer("categoryID").primaryKey().notNull(),
	categoryName: numeric("categoryName"),
	iconId: integer("iconID"),
	published: numeric("published"),
});

export const staStations = sqliteTable("staStations", {
	stationId: integer("stationID").primaryKey().notNull(),
	security: real("security"),
	dockingCostPerVolume: real("dockingCostPerVolume"),
	maxShipVolumeDockable: real("maxShipVolumeDockable"),
	officeRentalCost: integer("officeRentalCost"),
	operationId: integer("operationID"),
	stationTypeId: integer("stationTypeID"),
	corporationId: integer("corporationID"),
	solarSystemId: integer("solarSystemID"),
	constellationId: integer("constellationID"),
	regionId: integer("regionID"),
	stationName: numeric("stationName"),
	x: real("x"),
	y: real("y"),
	z: real("z"),
	reprocessingEfficiency: real("reprocessingEfficiency"),
	reprocessingStationsTake: real("reprocessingStationsTake"),
	reprocessingHangarFlag: integer("reprocessingHangarFlag"),
},
(table) => {
	return {
		ixStaStationsSolarSystemId: index("ix_staStations_solarSystemID").on(table.solarSystemId),
		ixStaStationsOperationId: index("ix_staStations_operationID").on(table.operationId),
		ixStaStationsRegionId: index("ix_staStations_regionID").on(table.regionId),
		ixStaStationsCorporationId: index("ix_staStations_corporationID").on(table.corporationId),
		ixStaStationsConstellationId: index("ix_staStations_constellationID").on(table.constellationId),
		ixStaStationsStationTypeId: index("ix_staStations_stationTypeID").on(table.stationTypeId),
	}
});

export const mapLocationWormholeClasses = sqliteTable("mapLocationWormholeClasses", {
	locationId: integer("locationID").primaryKey().notNull(),
	wormholeClassId: integer("wormholeClassID"),
});

export const invItems = sqliteTable("invItems", {
	itemId: integer("itemID").primaryKey().notNull(),
	typeId: integer("typeID").notNull(),
	ownerId: integer("ownerID").notNull(),
	locationId: integer("locationID").notNull(),
	flagId: integer("flagID").notNull(),
	quantity: integer("quantity").notNull(),
},
(table) => {
	return {
		ixInvItemsLocationId: index("ix_invItems_locationID").on(table.locationId),
		itemsIxOwnerLocation: index("items_IX_OwnerLocation").on(table.ownerId, table.locationId),
	}
});

export const mapUniverse = sqliteTable("mapUniverse", {
	universeId: integer("universeID").primaryKey().notNull(),
	universeName: numeric("universeName"),
	x: real("x"),
	y: real("y"),
	z: real("z"),
	xMin: real("xMin"),
	xMax: real("xMax"),
	yMin: real("yMin"),
	yMax: real("yMax"),
	zMin: real("zMin"),
	zMax: real("zMax"),
	radius: real("radius"),
});

export const skinShip = sqliteTable("skinShip", {
	skinId: integer("skinID"),
	typeId: integer("typeID"),
},
(table) => {
	return {
		ixSkinShipTypeId: index("ix_skinShip_typeID").on(table.typeId),
		ixSkinShipSkinId: index("ix_skinShip_skinID").on(table.skinId),
	}
});

export const crpNpcCorporationTrades = sqliteTable("crpNPCCorporationTrades", {
	corporationId: integer("corporationID").notNull(),
	typeId: integer("typeID").notNull(),
},
(table) => {
	return {
		pk0: primaryKey({ columns: [table.corporationId, table.typeId], name: "crpNPCCorporationTrades_corporationID_typeID_pk"})
	}
});

export const chrBloodlines = sqliteTable("chrBloodlines", {
	bloodlineId: integer("bloodlineID").primaryKey().notNull(),
	bloodlineName: numeric("bloodlineName"),
	raceId: integer("raceID"),
	description: numeric("description"),
	maleDescription: numeric("maleDescription"),
	femaleDescription: numeric("femaleDescription"),
	shipTypeId: integer("shipTypeID"),
	corporationId: integer("corporationID"),
	perception: integer("perception"),
	willpower: integer("willpower"),
	charisma: integer("charisma"),
	memory: integer("memory"),
	intelligence: integer("intelligence"),
	iconId: integer("iconID"),
	shortDescription: numeric("shortDescription"),
	shortMaleDescription: numeric("shortMaleDescription"),
	shortFemaleDescription: numeric("shortFemaleDescription"),
});

export const warCombatZones = sqliteTable("warCombatZones", {
	combatZoneId: integer("combatZoneID").primaryKey().notNull(),
	combatZoneName: numeric("combatZoneName"),
	factionId: integer("factionID"),
	centerSystemId: integer("centerSystemID"),
	description: numeric("description"),
});

export const invMetaGroups = sqliteTable("invMetaGroups", {
	metaGroupId: integer("metaGroupID").primaryKey().notNull(),
	metaGroupName: numeric("metaGroupName"),
	description: numeric("description"),
	iconId: integer("iconID"),
});

export const industryActivitySkills = sqliteTable("industryActivitySkills", {
	typeId: integer("typeID"),
	activityId: integer("activityID"),
	skillId: integer("skillID"),
	level: integer("level"),
},
(table) => {
	return {
		ixIndustryActivitySkillsSkillId: index("ix_industryActivitySkills_skillID").on(table.skillId),
		ixIndustryActivitySkillsTypeId: index("ix_industryActivitySkills_typeID").on(table.typeId),
		idx1: index("industryActivitySkills_idx1").on(table.typeId, table.activityId),
	}
});

export const staOperationServices = sqliteTable("staOperationServices", {
	operationId: integer("operationID").notNull(),
	serviceId: integer("serviceID").notNull(),
},
(table) => {
	return {
		pk0: primaryKey({ columns: [table.operationId, table.serviceId], name: "staOperationServices_operationID_serviceID_pk"})
	}
});

export const dgmEffects = sqliteTable("dgmEffects", {
	effectId: integer("effectID").primaryKey().notNull(),
	effectName: numeric("effectName"),
	effectCategory: integer("effectCategory"),
	preExpression: integer("preExpression"),
	postExpression: integer("postExpression"),
	description: numeric("description"),
	guid: numeric("guid"),
	iconId: integer("iconID"),
	isOffensive: numeric("isOffensive"),
	isAssistance: numeric("isAssistance"),
	durationAttributeId: integer("durationAttributeID"),
	trackingSpeedAttributeId: integer("trackingSpeedAttributeID"),
	dischargeAttributeId: integer("dischargeAttributeID"),
	rangeAttributeId: integer("rangeAttributeID"),
	falloffAttributeId: integer("falloffAttributeID"),
	disallowAutoRepeat: numeric("disallowAutoRepeat"),
	published: numeric("published"),
	displayName: numeric("displayName"),
	isWarpSafe: numeric("isWarpSafe"),
	rangeChance: numeric("rangeChance"),
	electronicChance: numeric("electronicChance"),
	propulsionChance: numeric("propulsionChance"),
	distribution: integer("distribution"),
	sfxName: numeric("sfxName"),
	npcUsageChanceAttributeId: integer("npcUsageChanceAttributeID"),
	npcActivationChanceAttributeId: integer("npcActivationChanceAttributeID"),
	fittingUsageChanceAttributeId: integer("fittingUsageChanceAttributeID"),
	modifierInfo: text("modifierInfo"),
});

export const ramAssemblyLineTypeDetailPerCategory = sqliteTable("ramAssemblyLineTypeDetailPerCategory", {
	assemblyLineTypeId: integer("assemblyLineTypeID").notNull(),
	categoryId: integer("categoryID").notNull(),
	timeMultiplier: real("timeMultiplier"),
	materialMultiplier: real("materialMultiplier"),
	costMultiplier: real("costMultiplier"),
},
(table) => {
	return {
		pk0: primaryKey({ columns: [table.assemblyLineTypeId, table.categoryId], name: "ramAssemblyLineTypeDetailPerCategory_assemblyLineTypeID_categoryID_pk"})
	}
});

export const dgmExpressions = sqliteTable("dgmExpressions", {
	expressionId: integer("expressionID").primaryKey().notNull(),
	operandId: integer("operandID"),
	arg1: integer("arg1"),
	arg2: integer("arg2"),
	expressionValue: numeric("expressionValue"),
	description: numeric("description"),
	expressionName: numeric("expressionName"),
	expressionTypeId: integer("expressionTypeID"),
	expressionGroupId: integer("expressionGroupID"),
	expressionAttributeId: integer("expressionAttributeID"),
});

export const ramActivities = sqliteTable("ramActivities", {
	activityId: integer("activityID").primaryKey().notNull(),
	activityName: numeric("activityName"),
	iconNo: numeric("iconNo"),
	description: numeric("description"),
	published: numeric("published"),
});

export const agtAgents = sqliteTable("agtAgents", {
	agentId: integer("agentID").primaryKey().notNull(),
	divisionId: integer("divisionID"),
	corporationId: integer("corporationID"),
	locationId: integer("locationID"),
	level: integer("level"),
	quality: integer("quality"),
	agentTypeId: integer("agentTypeID"),
	isLocator: numeric("isLocator"),
},
(table) => {
	return {
		ixAgtAgentsLocationId: index("ix_agtAgents_locationID").on(table.locationId),
		ixAgtAgentsCorporationId: index("ix_agtAgents_corporationID").on(table.corporationId),
	}
});

export const invGroups = sqliteTable("invGroups", {
	groupId: integer("groupID").primaryKey().notNull(),
	categoryId: integer("categoryID"),
	groupName: numeric("groupName"),
	iconId: integer("iconID"),
	useBasePrice: numeric("useBasePrice"),
	anchored: numeric("anchored"),
	anchorable: numeric("anchorable"),
	fittableNonSingleton: numeric("fittableNonSingleton"),
	published: numeric("published"),
},
(table) => {
	return {
		ixInvGroupsCategoryId: index("ix_invGroups_categoryID").on(table.categoryId),
	}
});