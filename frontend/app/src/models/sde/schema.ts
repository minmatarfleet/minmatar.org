import { sqliteTable, integer, numeric, real, index, primaryKey, text, uniqueIndex } from "drizzle-orm/sqlite-core"
  import { sql } from "drizzle-orm"

export const crpNPCCorporations = sqliteTable("crpNPCCorporations", {
	corporationID: integer("corporationID").primaryKey().notNull(),
	size: numeric("size"),
	extent: numeric("extent"),
	solarSystemID: integer("solarSystemID"),
	investorID1: integer("investorID1"),
	investorShares1: integer("investorShares1"),
	investorID2: integer("investorID2"),
	investorShares2: integer("investorShares2"),
	investorID3: integer("investorID3"),
	investorShares3: integer("investorShares3"),
	investorID4: integer("investorID4"),
	investorShares4: integer("investorShares4"),
	friendID: integer("friendID"),
	enemyID: integer("enemyID"),
	publicShares: integer("publicShares"),
	initialPrice: integer("initialPrice"),
	minSecurity: real("minSecurity"),
	scattered: numeric("scattered"),
	fringe: integer("fringe"),
	corridor: integer("corridor"),
	hub: integer("hub"),
	border: integer("border"),
	factionID: integer("factionID"),
	sizeFactor: real("sizeFactor"),
	stationCount: integer("stationCount"),
	stationSystemCount: integer("stationSystemCount"),
	description: text("description", { length: 4000 }),
	iconID: integer("iconID"),
});

export const staOperations = sqliteTable("staOperations", {
	activityID: integer("activityID"),
	operationID: integer("operationID").primaryKey().notNull(),
	operationName: text("operationName", { length: 100 }),
	description: text("description", { length: 1000 }),
	fringe: integer("fringe"),
	corridor: integer("corridor"),
	hub: integer("hub"),
	border: integer("border"),
	ratio: integer("ratio"),
	caldariStationTypeID: integer("caldariStationTypeID"),
	minmatarStationTypeID: integer("minmatarStationTypeID"),
	amarrStationTypeID: integer("amarrStationTypeID"),
	gallenteStationTypeID: integer("gallenteStationTypeID"),
	joveStationTypeID: integer("joveStationTypeID"),
});

export const invVolumes = sqliteTable("invVolumes", {
	typeID: integer("typeID").primaryKey().notNull(),
	volume: integer("volume"),
});

export const industryActivityProbabilities = sqliteTable("industryActivityProbabilities", {
	typeID: integer("typeID"),
	activityID: integer("activityID"),
	productTypeID: integer("productTypeID"),
	probability: numeric("probability"),
},
(table) => {
	return {
		ix_industryActivityProbabilities_productTypeID: index("ix_industryActivityProbabilities_productTypeID").on(table.productTypeID),
		ix_industryActivityProbabilities_typeID: index("ix_industryActivityProbabilities_typeID").on(table.typeID),
	}
});

export const ramAssemblyLineStations = sqliteTable("ramAssemblyLineStations", {
	stationID: integer("stationID").notNull(),
	assemblyLineTypeID: integer("assemblyLineTypeID").notNull(),
	quantity: integer("quantity"),
	stationTypeID: integer("stationTypeID"),
	ownerID: integer("ownerID"),
	solarSystemID: integer("solarSystemID"),
	regionID: integer("regionID"),
},
(table) => {
	return {
		ix_ramAssemblyLineStations_solarSystemID: index("ix_ramAssemblyLineStations_solarSystemID").on(table.solarSystemID),
		ix_ramAssemblyLineStations_ownerID: index("ix_ramAssemblyLineStations_ownerID").on(table.ownerID),
		ix_ramAssemblyLineStations_regionID: index("ix_ramAssemblyLineStations_regionID").on(table.regionID),
		pk0: primaryKey({ columns: [table.assemblyLineTypeID, table.stationID], name: "ramAssemblyLineStations_assemblyLineTypeID_stationID_pk"})
	}
});

export const ramAssemblyLineTypes = sqliteTable("ramAssemblyLineTypes", {
	assemblyLineTypeID: integer("assemblyLineTypeID").primaryKey().notNull(),
	assemblyLineTypeName: text("assemblyLineTypeName", { length: 100 }),
	description: text("description", { length: 1000 }),
	baseTimeMultiplier: real("baseTimeMultiplier"),
	baseMaterialMultiplier: real("baseMaterialMultiplier"),
	baseCostMultiplier: real("baseCostMultiplier"),
	volume: real("volume"),
	activityID: integer("activityID"),
	minCostPerHour: real("minCostPerHour"),
});

export const invMarketGroups = sqliteTable("invMarketGroups", {
	marketGroupID: integer("marketGroupID").primaryKey().notNull(),
	parentGroupID: integer("parentGroupID"),
	marketGroupName: text("marketGroupName", { length: 100 }),
	description: text("description", { length: 3000 }),
	iconID: integer("iconID"),
	hasTypes: numeric("hasTypes"),
});

export const trnTranslationLanguages = sqliteTable("trnTranslationLanguages", {
	numericLanguageID: integer("numericLanguageID").primaryKey().notNull(),
	languageID: text("languageID", { length: 50 }),
	languageName: text("languageName", { length: 200 }),
});

export const chrAttributes = sqliteTable("chrAttributes", {
	attributeID: integer("attributeID").primaryKey().notNull(),
	attributeName: text("attributeName", { length: 100 }),
	description: text("description", { length: 1000 }),
	iconID: integer("iconID"),
	shortDescription: text("shortDescription", { length: 500 }),
	notes: text("notes", { length: 500 }),
});

export const industryActivityProducts = sqliteTable("industryActivityProducts", {
	typeID: integer("typeID"),
	activityID: integer("activityID"),
	productTypeID: integer("productTypeID"),
	quantity: integer("quantity"),
},
(table) => {
	return {
		ix_industryActivityProducts_productTypeID: index("ix_industryActivityProducts_productTypeID").on(table.productTypeID),
		ix_industryActivityProducts_typeID: index("ix_industryActivityProducts_typeID").on(table.typeID),
	}
});

export const planetSchematicsPinMap = sqliteTable("planetSchematicsPinMap", {
	schematicID: integer("schematicID").notNull(),
	pinTypeID: integer("pinTypeID").notNull(),
},
(table) => {
	return {
		pk0: primaryKey({ columns: [table.pinTypeID, table.schematicID], name: "planetSchematicsPinMap_pinTypeID_schematicID_pk"})
	}
});

export const mapRegionJumps = sqliteTable("mapRegionJumps", {
	fromRegionID: integer("fromRegionID").notNull(),
	toRegionID: integer("toRegionID").notNull(),
},
(table) => {
	return {
		pk0: primaryKey({ columns: [table.fromRegionID, table.toRegionID], name: "mapRegionJumps_fromRegionID_toRegionID_pk"})
	}
});

export const skinMaterials = sqliteTable("skinMaterials", {
	skinMaterialID: integer("skinMaterialID").primaryKey().notNull(),
	displayNameID: integer("displayNameID"),
	materialSetID: integer("materialSetID"),
});

export const mapSolarSystems = sqliteTable("mapSolarSystems", {
	regionID: integer("regionID"),
	constellationID: integer("constellationID"),
	solarSystemID: integer("solarSystemID").primaryKey().notNull(),
	solarSystemName: text("solarSystemName", { length: 100 }),
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
	factionID: integer("factionID"),
	radius: real("radius"),
	sunTypeID: integer("sunTypeID"),
	securityClass: text("securityClass", { length: 2 }),
},
(table) => {
	return {
		ix_mapSolarSystems_constellationID: index("ix_mapSolarSystems_constellationID").on(table.constellationID),
		ix_mapSolarSystems_regionID: index("ix_mapSolarSystems_regionID").on(table.regionID),
		ix_mapSolarSystems_security: index("ix_mapSolarSystems_security").on(table.security),
	}
});

export const trnTranslationColumns = sqliteTable("trnTranslationColumns", {
	tcGroupID: integer("tcGroupID"),
	tcID: integer("tcID").primaryKey().notNull(),
	tableName: text("tableName", { length: 256 }).notNull(),
	columnName: text("columnName", { length: 128 }).notNull(),
	masterID: text("masterID", { length: 128 }),
});

export const eveIcons = sqliteTable("eveIcons", {
	iconID: integer("iconID").primaryKey().notNull(),
	iconFile: text("iconFile", { length: 500 }),
	description: text("description"),
});

export const mapRegions = sqliteTable("mapRegions", {
	regionID: integer("regionID").primaryKey().notNull(),
	regionName: text("regionName", { length: 100 }),
	x: real("x"),
	y: real("y"),
	z: real("z"),
	xMin: real("xMin"),
	xMax: real("xMax"),
	yMin: real("yMin"),
	yMax: real("yMax"),
	zMin: real("zMin"),
	zMax: real("zMax"),
	factionID: integer("factionID"),
	nebula: integer("nebula"),
	radius: real("radius"),
});

export const industryActivityRaces = sqliteTable("industryActivityRaces", {
	typeID: integer("typeID"),
	activityID: integer("activityID"),
	productTypeID: integer("productTypeID"),
	raceID: integer("raceID"),
},
(table) => {
	return {
		ix_industryActivityRaces_productTypeID: index("ix_industryActivityRaces_productTypeID").on(table.productTypeID),
		ix_industryActivityRaces_typeID: index("ix_industryActivityRaces_typeID").on(table.typeID),
	}
});

export const skins = sqliteTable("skins", {
	skinID: integer("skinID").primaryKey().notNull(),
	internalName: text("internalName", { length: 70 }),
	skinMaterialID: integer("skinMaterialID"),
});

export const invTypeReactions = sqliteTable("invTypeReactions", {
	reactionTypeID: integer("reactionTypeID").notNull(),
	input: numeric("input").notNull(),
	typeID: integer("typeID").notNull(),
	quantity: integer("quantity"),
},
(table) => {
	return {
		pk0: primaryKey({ columns: [table.input, table.reactionTypeID, table.typeID], name: "invTypeReactions_input_reactionTypeID_typeID_pk"})
	}
});

export const eveUnits = sqliteTable("eveUnits", {
	unitID: integer("unitID").primaryKey().notNull(),
	unitName: text("unitName", { length: 100 }),
	displayName: text("displayName", { length: 50 }),
	description: text("description", { length: 1000 }),
});

export const agtAgentTypes = sqliteTable("agtAgentTypes", {
	agentTypeID: integer("agentTypeID").primaryKey().notNull(),
	agentType: text("agentType", { length: 50 }),
});

export const planetSchematicsTypeMap = sqliteTable("planetSchematicsTypeMap", {
	schematicID: integer("schematicID").notNull(),
	typeID: integer("typeID").notNull(),
	quantity: integer("quantity"),
	isInput: numeric("isInput"),
},
(table) => {
	return {
		pk0: primaryKey({ columns: [table.schematicID, table.typeID], name: "planetSchematicsTypeMap_schematicID_typeID_pk"})
	}
});

export const ramInstallationTypeContents = sqliteTable("ramInstallationTypeContents", {
	installationTypeID: integer("installationTypeID").notNull(),
	assemblyLineTypeID: integer("assemblyLineTypeID").notNull(),
	quantity: integer("quantity"),
},
(table) => {
	return {
		pk0: primaryKey({ columns: [table.assemblyLineTypeID, table.installationTypeID], name: "ramInstallationTypeContents_assemblyLineTypeID_installationTypeID_pk"})
	}
});

export const invUniqueNames = sqliteTable("invUniqueNames", {
	itemID: integer("itemID").primaryKey().notNull(),
	itemName: text("itemName", { length: 200 }).notNull(),
	groupID: integer("groupID"),
},
(table) => {
	return {
		IX_GroupName: index("invUniqueNames_IX_GroupName").on(table.groupID, table.itemName),
		ix_invUniqueNames_itemName: uniqueIndex("ix_invUniqueNames_itemName").on(table.itemName),
	}
});

export const chrAncestries = sqliteTable("chrAncestries", {
	ancestryID: integer("ancestryID").primaryKey().notNull(),
	ancestryName: text("ancestryName", { length: 100 }),
	bloodlineID: integer("bloodlineID"),
	description: text("description", { length: 1000 }),
	perception: integer("perception"),
	willpower: integer("willpower"),
	charisma: integer("charisma"),
	memory: integer("memory"),
	intelligence: integer("intelligence"),
	iconID: integer("iconID"),
	shortDescription: text("shortDescription", { length: 500 }),
});

export const mapLocationScenes = sqliteTable("mapLocationScenes", {
	locationID: integer("locationID").primaryKey().notNull(),
	graphicID: integer("graphicID"),
});

export const invTypes = sqliteTable("invTypes", {
	typeID: integer("typeID").primaryKey().notNull(),
	groupID: integer("groupID"),
	typeName: text("typeName", { length: 100 }),
	description: text("description"),
	mass: real("mass"),
	volume: real("volume"),
	capacity: real("capacity"),
	portionSize: integer("portionSize"),
	raceID: integer("raceID"),
	basePrice: numeric("basePrice"),
	published: numeric("published"),
	marketGroupID: integer("marketGroupID"),
	iconID: integer("iconID"),
	soundID: integer("soundID"),
	graphicID: integer("graphicID"),
},
(table) => {
	return {
		ix_invTypes_groupID: index("ix_invTypes_groupID").on(table.groupID),
	}
});

export const industryActivity = sqliteTable("industryActivity", {
	typeID: integer("typeID").notNull(),
	activityID: integer("activityID").notNull(),
	time: integer("time"),
},
(table) => {
	return {
		ix_industryActivity_activityID: index("ix_industryActivity_activityID").on(table.activityID),
		pk0: primaryKey({ columns: [table.activityID, table.typeID], name: "industryActivity_activityID_typeID_pk"})
	}
});

export const invControlTowerResources = sqliteTable("invControlTowerResources", {
	controlTowerTypeID: integer("controlTowerTypeID").notNull(),
	resourceTypeID: integer("resourceTypeID").notNull(),
	purpose: integer("purpose"),
	quantity: integer("quantity"),
	minSecurityLevel: real("minSecurityLevel"),
	factionID: integer("factionID"),
},
(table) => {
	return {
		pk0: primaryKey({ columns: [table.controlTowerTypeID, table.resourceTypeID], name: "invControlTowerResources_controlTowerTypeID_resourceTypeID_pk"})
	}
});

export const mapJumps = sqliteTable("mapJumps", {
	stargateID: integer("stargateID").primaryKey().notNull(),
	destinationID: integer("destinationID"),
});

export const certCerts = sqliteTable("certCerts", {
	certID: integer("certID").primaryKey().notNull(),
	description: text("description"),
	groupID: integer("groupID"),
	name: text("name", { length: 255 }),
});

export const industryBlueprints = sqliteTable("industryBlueprints", {
	typeID: integer("typeID").primaryKey().notNull(),
	maxProductionLimit: integer("maxProductionLimit"),
});

export const invTypeMaterials = sqliteTable("invTypeMaterials", {
	typeID: integer("typeID").notNull(),
	materialTypeID: integer("materialTypeID").notNull(),
	quantity: integer("quantity").notNull(),
},
(table) => {
	return {
		pk0: primaryKey({ columns: [table.materialTypeID, table.typeID], name: "invTypeMaterials_materialTypeID_typeID_pk"})
	}
});

export const ramAssemblyLineTypeDetailPerGroup = sqliteTable("ramAssemblyLineTypeDetailPerGroup", {
	assemblyLineTypeID: integer("assemblyLineTypeID").notNull(),
	groupID: integer("groupID").notNull(),
	timeMultiplier: real("timeMultiplier"),
	materialMultiplier: real("materialMultiplier"),
	costMultiplier: real("costMultiplier"),
},
(table) => {
	return {
		pk0: primaryKey({ columns: [table.assemblyLineTypeID, table.groupID], name: "ramAssemblyLineTypeDetailPerGroup_assemblyLineTypeID_groupID_pk"})
	}
});

export const trnTranslations = sqliteTable("trnTranslations", {
	tcID: integer("tcID").notNull(),
	keyID: integer("keyID").notNull(),
	languageID: text("languageID", { length: 50 }).notNull(),
	text: text("text").notNull(),
},
(table) => {
	return {
		pk0: primaryKey({ columns: [table.keyID, table.languageID, table.tcID], name: "trnTranslations_keyID_languageID_tcID_pk"})
	}
});

export const dgmAttributeTypes = sqliteTable("dgmAttributeTypes", {
	attributeID: integer("attributeID").primaryKey().notNull(),
	attributeName: text("attributeName", { length: 100 }),
	description: text("description", { length: 1000 }),
	iconID: integer("iconID"),
	defaultValue: real("defaultValue"),
	published: numeric("published"),
	displayName: text("displayName", { length: 150 }),
	unitID: integer("unitID"),
	stackable: numeric("stackable"),
	highIsGood: numeric("highIsGood"),
	categoryID: integer("categoryID"),
});

export const agtResearchAgents = sqliteTable("agtResearchAgents", {
	agentID: integer("agentID").notNull(),
	typeID: integer("typeID").notNull(),
},
(table) => {
	return {
		ix_agtResearchAgents_typeID: index("ix_agtResearchAgents_typeID").on(table.typeID),
		pk0: primaryKey({ columns: [table.agentID, table.typeID], name: "agtResearchAgents_agentID_typeID_pk"})
	}
});

export const mapSolarSystemJumps = sqliteTable("mapSolarSystemJumps", {
	fromRegionID: integer("fromRegionID"),
	fromConstellationID: integer("fromConstellationID"),
	fromSolarSystemID: integer("fromSolarSystemID").notNull(),
	toSolarSystemID: integer("toSolarSystemID").notNull(),
	toConstellationID: integer("toConstellationID"),
	toRegionID: integer("toRegionID"),
},
(table) => {
	return {
		pk0: primaryKey({ columns: [table.fromSolarSystemID, table.toSolarSystemID], name: "mapSolarSystemJumps_fromSolarSystemID_toSolarSystemID_pk"})
	}
});

export const mapCelestialStatistics = sqliteTable("mapCelestialStatistics", {
	celestialID: integer("celestialID").primaryKey().notNull(),
	temperature: real("temperature"),
	spectralClass: text("spectralClass", { length: 10 }),
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
	fromRegionID: integer("fromRegionID"),
	fromConstellationID: integer("fromConstellationID").notNull(),
	toConstellationID: integer("toConstellationID").notNull(),
	toRegionID: integer("toRegionID"),
},
(table) => {
	return {
		pk0: primaryKey({ columns: [table.fromConstellationID, table.toConstellationID], name: "mapConstellationJumps_fromConstellationID_toConstellationID_pk"})
	}
});

export const mapCelestialGraphics = sqliteTable("mapCelestialGraphics", {
	celestialID: integer("celestialID").primaryKey().notNull(),
	heightMap1: integer("heightMap1"),
	heightMap2: integer("heightMap2"),
	shaderPreset: integer("shaderPreset"),
	population: numeric("population"),
});

export const staServices = sqliteTable("staServices", {
	serviceID: integer("serviceID").primaryKey().notNull(),
	serviceName: text("serviceName", { length: 100 }),
	description: text("description", { length: 1000 }),
});

export const warCombatZoneSystems = sqliteTable("warCombatZoneSystems", {
	solarSystemID: integer("solarSystemID").primaryKey().notNull(),
	combatZoneID: integer("combatZoneID"),
});

export const industryActivityMaterials = sqliteTable("industryActivityMaterials", {
	typeID: integer("typeID"),
	activityID: integer("activityID"),
	materialTypeID: integer("materialTypeID"),
	quantity: integer("quantity"),
},
(table) => {
	return {
		idx1: index("industryActivityMaterials_idx1").on(table.typeID, table.activityID),
		ix_industryActivityMaterials_typeID: index("ix_industryActivityMaterials_typeID").on(table.typeID),
	}
});

export const mapLandmarks = sqliteTable("mapLandmarks", {
	landmarkID: integer("landmarkID").primaryKey().notNull(),
	landmarkName: text("landmarkName", { length: 100 }),
	description: text("description"),
	locationID: integer("locationID"),
	x: real("x"),
	y: real("y"),
	z: real("z"),
	iconID: integer("iconID"),
});

export const invFlags = sqliteTable("invFlags", {
	flagID: integer("flagID").primaryKey().notNull(),
	flagName: text("flagName", { length: 200 }),
	flagText: text("flagText", { length: 100 }),
	orderID: integer("orderID"),
});

export const invContrabandTypes = sqliteTable("invContrabandTypes", {
	factionID: integer("factionID").notNull(),
	typeID: integer("typeID").notNull(),
	standingLoss: real("standingLoss"),
	confiscateMinSec: real("confiscateMinSec"),
	fineByValue: real("fineByValue"),
	attackMinSec: real("attackMinSec"),
},
(table) => {
	return {
		ix_invContrabandTypes_typeID: index("ix_invContrabandTypes_typeID").on(table.typeID),
		pk0: primaryKey({ columns: [table.factionID, table.typeID], name: "invContrabandTypes_factionID_typeID_pk"})
	}
});

export const invControlTowerResourcePurposes = sqliteTable("invControlTowerResourcePurposes", {
	purpose: integer("purpose").primaryKey().notNull(),
	purposeText: text("purposeText", { length: 100 }),
});

export const staStationTypes = sqliteTable("staStationTypes", {
	stationTypeID: integer("stationTypeID").primaryKey().notNull(),
	dockEntryX: real("dockEntryX"),
	dockEntryY: real("dockEntryY"),
	dockEntryZ: real("dockEntryZ"),
	dockOrientationX: real("dockOrientationX"),
	dockOrientationY: real("dockOrientationY"),
	dockOrientationZ: real("dockOrientationZ"),
	operationID: integer("operationID"),
	officeSlots: integer("officeSlots"),
	reprocessingEfficiency: real("reprocessingEfficiency"),
	conquerable: numeric("conquerable"),
});

export const invTraits = sqliteTable("invTraits", {
	traitID: integer("traitID").primaryKey().notNull(),
	typeID: integer("typeID"),
	skillID: integer("skillID"),
	bonus: real("bonus"),
	bonusText: text("bonusText"),
	unitID: integer("unitID"),
});

export const invPositions = sqliteTable("invPositions", {
	itemID: integer("itemID").primaryKey().notNull(),
	x: real("x").notNull(),
	y: real("y").notNull(),
	z: real("z").notNull(),
	yaw: real("yaw"),
	pitch: real("pitch"),
	roll: real("roll"),
});

export const certSkills = sqliteTable("certSkills", {
	certID: integer("certID"),
	skillID: integer("skillID"),
	certLevelInt: integer("certLevelInt"),
	skillLevel: integer("skillLevel"),
	certLevelText: text("certLevelText", { length: 8 }),
},
(table) => {
	return {
		ix_certSkills_skillID: index("ix_certSkills_skillID").on(table.skillID),
	}
});

export const skinLicense = sqliteTable("skinLicense", {
	licenseTypeID: integer("licenseTypeID").primaryKey().notNull(),
	duration: integer("duration"),
	skinID: integer("skinID"),
});

export const dgmTypeAttributes = sqliteTable("dgmTypeAttributes", {
	typeID: integer("typeID").notNull(),
	attributeID: integer("attributeID").notNull(),
	valueInt: integer("valueInt"),
	valueFloat: real("valueFloat"),
},
(table) => {
	return {
		ix_dgmTypeAttributes_attributeID: index("ix_dgmTypeAttributes_attributeID").on(table.attributeID),
		pk0: primaryKey({ columns: [table.attributeID, table.typeID], name: "dgmTypeAttributes_attributeID_typeID_pk"})
	}
});

export const mapConstellations = sqliteTable("mapConstellations", {
	regionID: integer("regionID"),
	constellationID: integer("constellationID").primaryKey().notNull(),
	constellationName: text("constellationName", { length: 100 }),
	x: real("x"),
	y: real("y"),
	z: real("z"),
	xMin: real("xMin"),
	xMax: real("xMax"),
	yMin: real("yMin"),
	yMax: real("yMax"),
	zMin: real("zMin"),
	zMax: real("zMax"),
	factionID: integer("factionID"),
	radius: real("radius"),
});

export const crpNPCCorporationDivisions = sqliteTable("crpNPCCorporationDivisions", {
	corporationID: integer("corporationID").notNull(),
	divisionID: integer("divisionID").notNull(),
	size: integer("size"),
},
(table) => {
	return {
		pk0: primaryKey({ columns: [table.corporationID, table.divisionID], name: "crpNPCCorporationDivisions_corporationID_divisionID_pk"})
	}
});

export const dgmAttributeCategories = sqliteTable("dgmAttributeCategories", {
	categoryID: integer("categoryID").primaryKey().notNull(),
	categoryName: text("categoryName", { length: 50 }),
	categoryDescription: text("categoryDescription", { length: 200 }),
});

export const translationTables = sqliteTable("translationTables", {
	sourceTable: text("sourceTable", { length: 200 }).notNull(),
	destinationTable: text("destinationTable", { length: 200 }),
	translatedKey: text("translatedKey", { length: 200 }).notNull(),
	tcGroupID: integer("tcGroupID"),
	tcID: integer("tcID"),
},
(table) => {
	return {
		pk0: primaryKey({ columns: [table.sourceTable, table.translatedKey], name: "translationTables_sourceTable_translatedKey_pk"})
	}
});

export const planetSchematics = sqliteTable("planetSchematics", {
	schematicID: integer("schematicID").primaryKey().notNull(),
	schematicName: text("schematicName", { length: 255 }),
	cycleTime: integer("cycleTime"),
});

export const invMetaTypes = sqliteTable("invMetaTypes", {
	typeID: integer("typeID").primaryKey().notNull(),
	parentTypeID: integer("parentTypeID"),
	metaGroupID: integer("metaGroupID"),
});

export const certMasteries = sqliteTable("certMasteries", {
	typeID: integer("typeID"),
	masteryLevel: integer("masteryLevel"),
	certID: integer("certID"),
});

export const crpNPCCorporationResearchFields = sqliteTable("crpNPCCorporationResearchFields", {
	skillID: integer("skillID").notNull(),
	corporationID: integer("corporationID").notNull(),
},
(table) => {
	return {
		pk0: primaryKey({ columns: [table.corporationID, table.skillID], name: "crpNPCCorporationResearchFields_corporationID_skillID_pk"})
	}
});

export const crpNPCDivisions = sqliteTable("crpNPCDivisions", {
	divisionID: integer("divisionID").primaryKey().notNull(),
	divisionName: text("divisionName", { length: 100 }),
	description: text("description", { length: 1000 }),
	leaderType: text("leaderType", { length: 100 }),
});

export const dgmTypeEffects = sqliteTable("dgmTypeEffects", {
	typeID: integer("typeID").notNull(),
	effectID: integer("effectID").notNull(),
	isDefault: numeric("isDefault"),
},
(table) => {
	return {
		pk0: primaryKey({ columns: [table.effectID, table.typeID], name: "dgmTypeEffects_effectID_typeID_pk"})
	}
});

export const invNames = sqliteTable("invNames", {
	itemID: integer("itemID").primaryKey().notNull(),
	itemName: text("itemName", { length: 200 }).notNull(),
});

export const mapDenormalize = sqliteTable("mapDenormalize", {
	itemID: integer("itemID").primaryKey().notNull(),
	typeID: integer("typeID"),
	groupID: integer("groupID"),
	solarSystemID: integer("solarSystemID"),
	constellationID: integer("constellationID"),
	regionID: integer("regionID"),
	orbitID: integer("orbitID"),
	x: real("x"),
	y: real("y"),
	z: real("z"),
	radius: real("radius"),
	itemName: text("itemName", { length: 100 }),
	security: real("security"),
	celestialIndex: integer("celestialIndex"),
	orbitIndex: integer("orbitIndex"),
},
(table) => {
	return {
		IX_groupConstellation: index("mapDenormalize_IX_groupConstellation").on(table.groupID, table.constellationID),
		ix_mapDenormalize_orbitID: index("ix_mapDenormalize_orbitID").on(table.orbitID),
		ix_mapDenormalize_constellationID: index("ix_mapDenormalize_constellationID").on(table.constellationID),
		ix_mapDenormalize_solarSystemID: index("ix_mapDenormalize_solarSystemID").on(table.solarSystemID),
		IX_groupSystem: index("mapDenormalize_IX_groupSystem").on(table.groupID, table.solarSystemID),
		ix_mapDenormalize_typeID: index("ix_mapDenormalize_typeID").on(table.typeID),
		ix_mapDenormalize_regionID: index("ix_mapDenormalize_regionID").on(table.regionID),
		IX_groupRegion: index("mapDenormalize_IX_groupRegion").on(table.groupID, table.regionID),
	}
});

export const chrRaces = sqliteTable("chrRaces", {
	raceID: integer("raceID").primaryKey().notNull(),
	raceName: text("raceName", { length: 100 }),
	description: text("description", { length: 1000 }),
	iconID: integer("iconID"),
	shortDescription: text("shortDescription", { length: 500 }),
});

export const agtAgentsInSpace = sqliteTable("agtAgentsInSpace", {
	agentID: integer("agentID").primaryKey().notNull(),
	dungeonID: integer("dungeonID"),
	solarSystemID: integer("solarSystemID"),
	spawnPointID: integer("spawnPointID"),
	typeID: integer("typeID"),
},
(table) => {
	return {
		ix_agtAgentsInSpace_solarSystemID: index("ix_agtAgentsInSpace_solarSystemID").on(table.solarSystemID),
	}
});

export const crpActivities = sqliteTable("crpActivities", {
	activityID: integer("activityID").primaryKey().notNull(),
	activityName: text("activityName", { length: 100 }),
	description: text("description", { length: 1000 }),
});

export const chrFactions = sqliteTable("chrFactions", {
	factionID: integer("factionID").primaryKey().notNull(),
	factionName: text("factionName", { length: 100 }),
	description: text("description", { length: 2000 }),
	raceIDs: integer("raceIDs"),
	solarSystemID: integer("solarSystemID"),
	corporationID: integer("corporationID"),
	sizeFactor: real("sizeFactor"),
	stationCount: integer("stationCount"),
	stationSystemCount: integer("stationSystemCount"),
	militiaCorporationID: integer("militiaCorporationID"),
	iconID: integer("iconID"),
});

export const eveGraphics = sqliteTable("eveGraphics", {
	graphicID: integer("graphicID").primaryKey().notNull(),
	sofFactionName: text("sofFactionName", { length: 100 }),
	graphicFile: text("graphicFile", { length: 256 }),
	sofHullName: text("sofHullName", { length: 100 }),
	sofRaceName: text("sofRaceName", { length: 100 }),
	description: text("description"),
});

export const invCategories = sqliteTable("invCategories", {
	categoryID: integer("categoryID").primaryKey().notNull(),
	categoryName: text("categoryName", { length: 100 }),
	iconID: integer("iconID"),
	published: numeric("published"),
});

export const staStations = sqliteTable("staStations", {
	stationID: integer("stationID").primaryKey().notNull(),
	security: real("security"),
	dockingCostPerVolume: real("dockingCostPerVolume"),
	maxShipVolumeDockable: real("maxShipVolumeDockable"),
	officeRentalCost: integer("officeRentalCost"),
	operationID: integer("operationID"),
	stationTypeID: integer("stationTypeID"),
	corporationID: integer("corporationID"),
	solarSystemID: integer("solarSystemID"),
	constellationID: integer("constellationID"),
	regionID: integer("regionID"),
	stationName: text("stationName", { length: 100 }),
	x: real("x"),
	y: real("y"),
	z: real("z"),
	reprocessingEfficiency: real("reprocessingEfficiency"),
	reprocessingStationsTake: real("reprocessingStationsTake"),
	reprocessingHangarFlag: integer("reprocessingHangarFlag"),
},
(table) => {
	return {
		ix_staStations_constellationID: index("ix_staStations_constellationID").on(table.constellationID),
		ix_staStations_stationTypeID: index("ix_staStations_stationTypeID").on(table.stationTypeID),
		ix_staStations_solarSystemID: index("ix_staStations_solarSystemID").on(table.solarSystemID),
		ix_staStations_regionID: index("ix_staStations_regionID").on(table.regionID),
		ix_staStations_operationID: index("ix_staStations_operationID").on(table.operationID),
		ix_staStations_corporationID: index("ix_staStations_corporationID").on(table.corporationID),
	}
});

export const mapLocationWormholeClasses = sqliteTable("mapLocationWormholeClasses", {
	locationID: integer("locationID").primaryKey().notNull(),
	wormholeClassID: integer("wormholeClassID"),
});

export const invItems = sqliteTable("invItems", {
	itemID: integer("itemID").primaryKey().notNull(),
	typeID: integer("typeID").notNull(),
	ownerID: integer("ownerID").notNull(),
	locationID: integer("locationID").notNull(),
	flagID: integer("flagID").notNull(),
	quantity: integer("quantity").notNull(),
},
(table) => {
	return {
		ix_invItems_locationID: index("ix_invItems_locationID").on(table.locationID),
		items_IX_OwnerLocation: index("items_IX_OwnerLocation").on(table.ownerID, table.locationID),
	}
});

export const mapUniverse = sqliteTable("mapUniverse", {
	universeID: integer("universeID").primaryKey().notNull(),
	universeName: text("universeName", { length: 100 }),
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
	skinID: integer("skinID"),
	typeID: integer("typeID"),
},
(table) => {
	return {
		ix_skinShip_typeID: index("ix_skinShip_typeID").on(table.typeID),
		ix_skinShip_skinID: index("ix_skinShip_skinID").on(table.skinID),
	}
});

export const crpNPCCorporationTrades = sqliteTable("crpNPCCorporationTrades", {
	corporationID: integer("corporationID").notNull(),
	typeID: integer("typeID").notNull(),
},
(table) => {
	return {
		pk0: primaryKey({ columns: [table.corporationID, table.typeID], name: "crpNPCCorporationTrades_corporationID_typeID_pk"})
	}
});

export const chrBloodlines = sqliteTable("chrBloodlines", {
	bloodlineID: integer("bloodlineID").primaryKey().notNull(),
	bloodlineName: text("bloodlineName", { length: 100 }),
	raceID: integer("raceID"),
	description: text("description", { length: 1000 }),
	maleDescription: text("maleDescription", { length: 1000 }),
	femaleDescription: text("femaleDescription", { length: 1000 }),
	shipTypeID: integer("shipTypeID"),
	corporationID: integer("corporationID"),
	perception: integer("perception"),
	willpower: integer("willpower"),
	charisma: integer("charisma"),
	memory: integer("memory"),
	intelligence: integer("intelligence"),
	iconID: integer("iconID"),
	shortDescription: text("shortDescription", { length: 500 }),
	shortMaleDescription: text("shortMaleDescription", { length: 500 }),
	shortFemaleDescription: text("shortFemaleDescription", { length: 500 }),
});

export const warCombatZones = sqliteTable("warCombatZones", {
	combatZoneID: integer("combatZoneID").primaryKey().notNull(),
	combatZoneName: text("combatZoneName", { length: 100 }),
	factionID: integer("factionID"),
	centerSystemID: integer("centerSystemID"),
	description: text("description", { length: 500 }),
});

export const invMetaGroups = sqliteTable("invMetaGroups", {
	metaGroupID: integer("metaGroupID").primaryKey().notNull(),
	metaGroupName: text("metaGroupName", { length: 100 }),
	description: text("description", { length: 1000 }),
	iconID: integer("iconID"),
});

export const industryActivitySkills = sqliteTable("industryActivitySkills", {
	typeID: integer("typeID"),
	activityID: integer("activityID"),
	skillID: integer("skillID"),
	level: integer("level"),
},
(table) => {
	return {
		idx1: index("industryActivitySkills_idx1").on(table.typeID, table.activityID),
		ix_industryActivitySkills_skillID: index("ix_industryActivitySkills_skillID").on(table.skillID),
		ix_industryActivitySkills_typeID: index("ix_industryActivitySkills_typeID").on(table.typeID),
	}
});

export const staOperationServices = sqliteTable("staOperationServices", {
	operationID: integer("operationID").notNull(),
	serviceID: integer("serviceID").notNull(),
},
(table) => {
	return {
		pk0: primaryKey({ columns: [table.operationID, table.serviceID], name: "staOperationServices_operationID_serviceID_pk"})
	}
});

export const dgmEffects = sqliteTable("dgmEffects", {
	effectID: integer("effectID").primaryKey().notNull(),
	effectName: text("effectName", { length: 400 }),
	effectCategory: integer("effectCategory"),
	preExpression: integer("preExpression"),
	postExpression: integer("postExpression"),
	description: text("description", { length: 1000 }),
	guid: text("guid", { length: 60 }),
	iconID: integer("iconID"),
	isOffensive: numeric("isOffensive"),
	isAssistance: numeric("isAssistance"),
	durationAttributeID: integer("durationAttributeID"),
	trackingSpeedAttributeID: integer("trackingSpeedAttributeID"),
	dischargeAttributeID: integer("dischargeAttributeID"),
	rangeAttributeID: integer("rangeAttributeID"),
	falloffAttributeID: integer("falloffAttributeID"),
	disallowAutoRepeat: numeric("disallowAutoRepeat"),
	published: numeric("published"),
	displayName: text("displayName", { length: 100 }),
	isWarpSafe: numeric("isWarpSafe"),
	rangeChance: numeric("rangeChance"),
	electronicChance: numeric("electronicChance"),
	propulsionChance: numeric("propulsionChance"),
	distribution: integer("distribution"),
	sfxName: text("sfxName", { length: 20 }),
	npcUsageChanceAttributeID: integer("npcUsageChanceAttributeID"),
	npcActivationChanceAttributeID: integer("npcActivationChanceAttributeID"),
	fittingUsageChanceAttributeID: integer("fittingUsageChanceAttributeID"),
	modifierInfo: text("modifierInfo"),
});

export const ramAssemblyLineTypeDetailPerCategory = sqliteTable("ramAssemblyLineTypeDetailPerCategory", {
	assemblyLineTypeID: integer("assemblyLineTypeID").notNull(),
	categoryID: integer("categoryID").notNull(),
	timeMultiplier: real("timeMultiplier"),
	materialMultiplier: real("materialMultiplier"),
	costMultiplier: real("costMultiplier"),
},
(table) => {
	return {
		pk0: primaryKey({ columns: [table.assemblyLineTypeID, table.categoryID], name: "ramAssemblyLineTypeDetailPerCategory_assemblyLineTypeID_categoryID_pk"})
	}
});

export const dgmExpressions = sqliteTable("dgmExpressions", {
	expressionID: integer("expressionID").primaryKey().notNull(),
	operandID: integer("operandID"),
	arg1: integer("arg1"),
	arg2: integer("arg2"),
	expressionValue: text("expressionValue", { length: 100 }),
	description: text("description", { length: 1000 }),
	expressionName: text("expressionName", { length: 500 }),
	expressionTypeID: integer("expressionTypeID"),
	expressionGroupID: integer("expressionGroupID"),
	expressionAttributeID: integer("expressionAttributeID"),
});

export const ramActivities = sqliteTable("ramActivities", {
	activityID: integer("activityID").primaryKey().notNull(),
	activityName: text("activityName", { length: 100 }),
	iconNo: text("iconNo", { length: 5 }),
	description: text("description", { length: 1000 }),
	published: numeric("published"),
});

export const agtAgents = sqliteTable("agtAgents", {
	agentID: integer("agentID").primaryKey().notNull(),
	divisionID: integer("divisionID"),
	corporationID: integer("corporationID"),
	locationID: integer("locationID"),
	level: integer("level"),
	quality: integer("quality"),
	agentTypeID: integer("agentTypeID"),
	isLocator: numeric("isLocator"),
},
(table) => {
	return {
		ix_agtAgents_locationID: index("ix_agtAgents_locationID").on(table.locationID),
		ix_agtAgents_corporationID: index("ix_agtAgents_corporationID").on(table.corporationID),
	}
});

export const invGroups = sqliteTable("invGroups", {
	groupID: integer("groupID").primaryKey().notNull(),
	categoryID: integer("categoryID"),
	groupName: text("groupName", { length: 100 }),
	iconID: integer("iconID"),
	useBasePrice: numeric("useBasePrice"),
	anchored: numeric("anchored"),
	anchorable: numeric("anchorable"),
	fittableNonSingleton: numeric("fittableNonSingleton"),
	published: numeric("published"),
},
(table) => {
	return {
		ix_invGroups_categoryID: index("ix_invGroups_categoryID").on(table.categoryID),
	}
});