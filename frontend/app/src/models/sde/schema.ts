import { sqliteTable, integer, text, real, numeric, index, primaryKey } from "drizzle-orm/sqlite-core"
import { sql } from "drizzle-orm"

export const invTypeBonus = sqliteTable("invTypeBonus", {
	typeId: integer().primaryKey(),
	iconId: integer(),
});

export const invTypeDogma = sqliteTable("invTypeDogma", {
	typeId: integer().primaryKey(),
});

export const agtAgentTypes = sqliteTable("agtAgentTypes", {
	agentTypeId: integer().primaryKey(),
	agentType: text(),
});

export const staOperations = sqliteTable("staOperations", {
	operationId: integer().primaryKey(),
	activityId: integer(),
	border: integer(),
	corridor: integer(),
	description: text(),
	fringe: integer(),
	hub: integer(),
	manufacturingFactor: real(),
	operationName: text(),
	ratio: integer(),
	researchFactor: real(),
	caldariStationTypeId: integer(),
	minmatarStationTypeId: integer(),
	amarrStationTypeId: integer(),
	gallenteStationTypeId: integer(),
	joveStationTypeId: integer(),
});

export const skinLicense = sqliteTable("skinLicense", {
	duration: integer(),
	licenseTypeId: integer().primaryKey(),
	skinId: integer(),
	isSingleUse: numeric(),
});

export const dbuffCollections = sqliteTable("dbuffCollections", {
	dbuffCollectionId: integer().primaryKey(),
	aggregateMode: text(),
	developerDescription: text(),
	operationName: text(),
	showOutputValueInUi: text(),
	displayName: text(),
});

export const dgmAttributeTypes = sqliteTable("dgmAttributeTypes", {
	attributeId: integer().primaryKey(),
	categoryId: integer(),
	dataType: integer(),
	defaultValue: real(),
	description: text(),
	displayWhenZero: numeric(),
	highIsGood: numeric(),
	attributeName: text(),
	published: numeric(),
	stackable: numeric(),
	displayName: text(),
	iconId: integer(),
	tooltipDescription: text(),
	tooltipTitle: text(),
	unitId: integer(),
	chargeRechargeTimeId: integer(),
	maxAttributeId: integer(),
	minAttributeId: integer(),
});

export const mapRegions = sqliteTable("mapRegions", {
	regionId: integer().primaryKey(),
	description: text(),
	factionId: integer(),
	regionName: text(),
	nebulaId: integer(),
	wormholeClassId: integer(),
	x: real(),
	y: real(),
	z: real(),
});

export const invDynamicItemAttributes = sqliteTable("invDynamicItemAttributes", {
	typeId: integer().primaryKey(),
});

export const agtAgentsInSpace = sqliteTable("agtAgentsInSpace", {
	agentId: integer().primaryKey(),
	dungeonId: integer(),
	solarSystemId: integer(),
	spawnPointId: integer(),
	typeId: integer(),
},
(table) => [
	index("ix_agtAgentsInSpace_solarSystemID").on(table.solarSystemId),
]);

export const planetSchematics = sqliteTable("planetSchematics", {
	schematicId: integer().primaryKey(),
	cycleTime: integer(),
	schematicName: text(),
});

export const eveUnits = sqliteTable("eveUnits", {
	unitId: integer().primaryKey(),
	description: text(),
	displayName: text(),
	unitName: text(),
});

export const dgmAttributeCategories = sqliteTable("dgmAttributeCategories", {
	categoryId: integer().primaryKey(),
	categoryDescription: text(),
	categoryName: text(),
});

export const chrNpcCharacters = sqliteTable("chrNPCCharacters", {
	characterId: integer().primaryKey(),
	bloodlineId: integer(),
	ceo: numeric(),
	corporationId: integer(),
	gender: numeric(),
	locationId: integer(),
	name: text(),
	raceId: integer(),
	startDate: text(),
	uniqueName: numeric(),
	ancestryId: integer(),
	careerId: integer(),
	schoolId: integer(),
	specialityId: integer(),
	description: text(),
},
(table) => [
	index("ix_chrNPCCharacters_corporationID").on(table.corporationId),
]);

export const mapPlanets = sqliteTable("mapPlanets", {
	celestialId: integer().primaryKey(),
	celestialIndex: integer(),
	orbitId: integer(),
	radius: integer(),
	solarSystemId: integer(),
	typeId: integer(),
	x: real(),
	y: real(),
	z: real(),
	uniqueName: text(),
},
(table) => [
	index("ix_mapPlanets_solarSystemID").on(table.solarSystemId),
]);

export const crpActivities = sqliteTable("crpActivities", {
	activityId: integer().primaryKey(),
	activityName: text(),
});

export const chrAttributes = sqliteTable("chrAttributes", {
	attributeId: integer().primaryKey(),
	description: text(),
	iconId: integer(),
	attributeName: text(),
	notes: text(),
	shortDescription: text(),
});

export const mercenaryTacticalOperations = sqliteTable("mercenaryTacticalOperations", {
	operationId: integer().primaryKey(),
	anarchyImpact: integer(),
	description: text(),
	developmentImpact: integer(),
	infomorphBonus: integer(),
	name: text(),
});

export const mapConstellations = sqliteTable("mapConstellations", {
	constellationId: integer().primaryKey(),
	factionId: integer(),
	constellationName: text(),
	regionId: integer(),
	wormholeClassId: integer(),
	x: real(),
	y: real(),
	z: real(),
},
(table) => [
	index("ix_mapConstellations_regionID").on(table.regionId),
]);

export const invMarketGroups = sqliteTable("invMarketGroups", {
	marketGroupId: integer().primaryKey(),
	description: text(),
	hasTypes: numeric(),
	iconId: integer(),
	marketGroupName: text(),
	parentGroupId: integer(),
});

export const chrMasteries = sqliteTable("chrMasteries", {
	typeId: integer().primaryKey(),
});

export const chrCertificates = sqliteTable("chrCertificates", {
	certId: integer().primaryKey(),
	description: text(),
	groupId: integer(),
	certName: text(),
});

export const mapSecondarySuns = sqliteTable("mapSecondarySuns", {
	itemId: integer().primaryKey(),
	effectBeaconTypeId: integer(),
	solarSystemId: integer(),
	typeId: integer(),
	x: real(),
	y: real(),
	z: real(),
});

export const chrAncestries = sqliteTable("chrAncestries", {
	ancestryId: integer().primaryKey(),
	bloodlineId: integer(),
	charisma: integer(),
	description: text(),
	iconId: integer(),
	intelligence: integer(),
	memory: integer(),
	ancestryName: text(),
	perception: integer(),
	shortDescription: text(),
	willpower: integer(),
});

export const chrCloneGrades = sqliteTable("chrCloneGrades", {
	gradeId: integer().primaryKey(),
	name: text(),
});

export const planetResources = sqliteTable("planetResources", {
	celestialId: integer().primaryKey(),
	power: integer(),
	workforce: integer(),
	reagentAmountPerCycle: integer(),
	reagentCyclePeriod: integer(),
	reagentSecuredCapacity: integer(),
	reagentTypeId: integer(),
	reagentUnsecuredCapacity: integer(),
});

export const mapLandmarks = sqliteTable("mapLandmarks", {
	landmarkId: integer().primaryKey(),
	description: text(),
	landmarkName: text(),
	x: real(),
	y: real(),
	z: real(),
	iconId: integer(),
	locationId: integer(),
});

export const invCategories = sqliteTable("invCategories", {
	categoryId: integer().primaryKey(),
	categoryName: text(),
	published: numeric(),
	iconId: integer(),
});

export const mapAsteroidBelts = sqliteTable("mapAsteroidBelts", {
	celestialId: integer().primaryKey(),
	celestialIndex: integer(),
	orbitId: integer(),
	orbitIndex: integer(),
	radius: real(),
	solarSystemId: integer(),
	typeId: integer(),
	x: real(),
	y: real(),
	z: real(),
	uniqueName: text(),
},
(table) => [
	index("ix_mapAsteroidBelts_solarSystemID").on(table.solarSystemId),
]);

export const mapStargates = sqliteTable("mapStargates", {
	stargateId: integer().primaryKey(),
	solarSystemId: integer(),
	typeId: integer(),
	x: real(),
	y: real(),
	z: real(),
	destinationSolarSystemId: integer(),
	destinationStargateId: integer(),
},
(table) => [
	index("ix_mapStargates_solarSystemID").on(table.solarSystemId),
]);

export const industryBlueprints = sqliteTable("industryBlueprints", {
	typeId: integer().primaryKey(),
	blueprintTypeId: integer(),
	maxProductionLimit: integer(),
});

export const mapStars = sqliteTable("mapStars", {
	celestialId: integer().primaryKey(),
	radius: integer(),
	solarSystemId: integer(),
	typeId: integer(),
});

export const invGroups = sqliteTable("invGroups", {
	groupId: integer().primaryKey(),
	anchorable: numeric(),
	anchored: numeric(),
	categoryId: integer(),
	fittableNonSingleton: numeric(),
	groupName: text(),
	published: numeric(),
	useBasePrice: numeric(),
	iconId: integer(),
},
(table) => [
	index("ix_invGroups_categoryID").on(table.categoryId),
]);

export const invTypes = sqliteTable("invTypes", {
	typeId: integer().primaryKey(),
	groupId: integer(),
	mass: real(),
	typeName: text(),
	portionSize: integer(),
	published: numeric(),
	volume: real(),
	radius: real(),
	description: text(),
	graphicId: integer(),
	soundId: integer(),
	iconId: integer(),
	raceId: integer(),
	basePrice: real(),
	marketGroupId: integer(),
	capacity: real(),
	metaGroupId: integer(),
	metaLevel: integer(),
	variationParentTypeId: integer(),
	factionId: integer(),
},
(table) => [
	index("ix_invTypes_groupID").on(table.groupId),
]);

export const mapSolarSystems = sqliteTable("mapSolarSystems", {
	solarSystemId: integer().primaryKey(),
	border: numeric(),
	constellationId: integer(),
	hub: numeric(),
	international: numeric(),
	luminosity: real(),
	solarSystemName: text(),
	radius: real(),
	regionId: integer(),
	regional: numeric(),
	securityClass: text(),
	securityStatus: real(),
	starId: integer(),
	x: real(),
	y: real(),
	z: real(),
	corridor: numeric(),
	fringe: numeric(),
	wormholeClassId: integer(),
	visualEffect: text(),
	disallowedAnchorCategories: text(),
	disallowedAnchorGroups: text(),
	factionId: integer(),
	sunTypeId: integer(),
	security: real(),
},
(table) => [
	index("ix_mapSolarSystems_securityStatus").on(table.securityStatus),
	index("ix_mapSolarSystems_regionID").on(table.regionId),
	index("ix_mapSolarSystems_constellationID").on(table.constellationId),
]);

export const staServices = sqliteTable("staServices", {
	serviceId: integer().primaryKey(),
	serviceName: text(),
	description: text(),
});

export const invMetaGroups = sqliteTable("invMetaGroups", {
	metaGroupId: integer().primaryKey(),
	metaGroupName: text(),
	colorB: real(),
	colorG: real(),
	colorR: real(),
	iconId: integer(),
	iconSuffix: text(),
	description: text(),
});

export const invCompressibleTypes = sqliteTable("invCompressibleTypes", {
	typeId: integer().primaryKey(),
	compressedTypeId: integer(),
});

export const crpNpcCorporations = sqliteTable("crpNPCCorporations", {
	corporationId: integer().primaryKey(),
	ceoId: integer(),
	deleted: numeric(),
	description: text(),
	extent: text(),
	hasPlayerPersonnelManager: numeric(),
	initialPrice: integer(),
	memberLimit: integer(),
	minSecurity: real(),
	minimumJoinStanding: integer(),
	corporationName: text(),
	sendCharTerminationMessage: numeric(),
	shares: integer(),
	size: text(),
	stationId: integer(),
	taxRate: real(),
	tickerName: text(),
	uniqueName: numeric(),
	enemyId: integer(),
	factionId: integer(),
	friendId: integer(),
	iconId: integer(),
	mainActivityId: integer(),
	raceId: integer(),
	sizeFactor: real(),
	solarSystemId: integer(),
	investorId1: integer(),
	investorShares1: integer(),
	investorId2: integer(),
	investorShares2: integer(),
	investorId3: integer(),
	investorShares3: integer(),
	secondaryActivityId: integer(),
	investorId4: integer(),
	investorShares4: integer(),
});

export const chrBloodlines = sqliteTable("chrBloodlines", {
	bloodlineId: integer().primaryKey(),
	charisma: integer(),
	corporationId: integer(),
	description: text(),
	iconId: integer(),
	intelligence: integer(),
	memory: integer(),
	bloodlineName: text(),
	perception: integer(),
	raceId: integer(),
	willpower: integer(),
});

export const skins = sqliteTable("skins", {
	skinId: integer().primaryKey(),
	allowCcpDevs: numeric(),
	internalName: text(),
	skinMaterialId: integer(),
	visibleSerenity: numeric(),
	visibleTranquility: numeric(),
	isStructureSkin: numeric(),
	skinDescription: text(),
});

export const dgmEffects = sqliteTable("dgmEffects", {
	effectId: integer().primaryKey(),
	disallowAutoRepeat: numeric(),
	dischargeAttributeId: integer(),
	durationAttributeId: integer(),
	effectCategory: integer(),
	electronicChance: numeric(),
	guid: text(),
	isAssistance: numeric(),
	isOffensive: numeric(),
	isWarpSafe: numeric(),
	effectName: text(),
	propulsionChance: numeric(),
	published: numeric(),
	rangeChance: numeric(),
	distribution: integer(),
	falloffAttributeId: integer(),
	rangeAttributeId: integer(),
	trackingSpeedAttributeId: integer(),
	description: text(),
	displayName: text(),
	iconId: integer(),
	modifierInfo: text(),
	npcUsageChanceAttributeId: integer(),
	npcActivationChanceAttributeId: integer(),
	fittingUsageChanceAttributeId: integer(),
	resistanceAttributeId: integer(),
});

export const chrFactions = sqliteTable("chrFactions", {
	factionId: integer().primaryKey(),
	corporationId: integer(),
	description: text(),
	flatLogo: text(),
	flatLogoWithName: text(),
	iconId: integer(),
	militiaCorporationId: integer(),
	factionName: text(),
	shortDescription: text(),
	sizeFactor: real(),
	solarSystemId: integer(),
	uniqueName: numeric(),
});

export const staStations = sqliteTable("staStations", {
	stationId: integer().primaryKey(),
	celestialIndex: integer(),
	operationId: integer(),
	orbitId: integer(),
	orbitIndex: integer(),
	ownerId: integer(),
	reprocessingEfficiency: real(),
	reprocessingHangarFlag: integer(),
	reprocessingStationsTake: real(),
	solarSystemId: integer(),
	typeId: integer(),
	useOperationName: numeric(),
	x: real(),
	y: real(),
	z: real(),
},
(table) => [
	index("ix_staStations_operationID").on(table.operationId),
	index("ix_staStations_solarSystemID").on(table.solarSystemId),
]);

export const chrRaces = sqliteTable("chrRaces", {
	raceId: integer().primaryKey(),
	description: text(),
	iconId: integer(),
	raceName: text(),
	shipTypeId: integer(),
});

export const eveIcons = sqliteTable("eveIcons", {
	iconId: integer().primaryKey(),
	iconFile: text(),
});

export const mapMoons = sqliteTable("mapMoons", {
	celestialId: integer().primaryKey(),
	celestialIndex: integer(),
	orbitId: integer(),
	orbitIndex: integer(),
	radius: real(),
	solarSystemId: integer(),
	typeId: integer(),
	x: real(),
	y: real(),
	z: real(),
	uniqueName: text(),
},
(table) => [
	index("ix_mapMoons_solarSystemID").on(table.solarSystemId),
]);

export const crpNpcDivisions = sqliteTable("crpNPCDivisions", {
	divisionId: integer().primaryKey(),
	displayName: text(),
	internalName: text(),
	leaderTypeName: text(),
	divisionName: text(),
	description: text(),
});

export const eveGraphics = sqliteTable("eveGraphics", {
	graphicId: integer().primaryKey(),
	graphicFile: text(),
	iconFolder: text(),
	sofFactionName: text(),
	sofHullName: text(),
	sofRaceName: text(),
	sofMaterialSetId: integer(),
	sofLayout: text(),
});

export const sovUpgrades = sqliteTable("sovUpgrades", {
	upgradeId: integer().primaryKey(),
	mutuallyExclusiveGroup: text(),
	powerAllocation: integer(),
	workforceAllocation: integer(),
	powerProduction: integer(),
	workforceProduction: integer(),
});

export const translationLanguages = sqliteTable("translationLanguages", {
	languageId: text().primaryKey(),
	name: text(),
});

export const skinMaterials = sqliteTable("skinMaterials", {
	skinMaterialId: integer().primaryKey(),
	displayName: text(),
	materialSetId: integer(),
});

export const agtAgents = sqliteTable("agtAgents", {
	agentId: integer().primaryKey(),
	corporationId: integer(),
	locationId: integer(),
	agentTypeId: integer(),
	divisionId: integer(),
	isLocator: numeric(),
	level: integer(),
},
(table) => [
	index("ix_agtAgents_locationID").on(table.locationId),
	index("ix_agtAgents_corporationID").on(table.corporationId),
]);

export const agtResearchAgents = sqliteTable("agtResearchAgents", {
	agentId: integer(),
	typeId: integer(),
},
(table) => [
	index("ix_agtResearchAgents_typeID").on(table.typeId),
	primaryKey({ columns: [table.agentId, table.typeId], name: "agtResearchAgents_agentID_typeID_pk"})
]);

export const dgmTypeAttributes = sqliteTable("dgmTypeAttributes", {
	typeId: integer(),
	attributeId: integer(),
	value: real(),
	valueInt: integer(),
	valueFloat: real(),
},
(table) => [
	index("ix_dgmTypeAttributes_attributeID").on(table.attributeId),
	primaryKey({ columns: [table.typeId, table.attributeId], name: "dgmTypeAttributes_typeID_attributeID_pk"})
]);

export const dgmTypeEffects = sqliteTable("dgmTypeEffects", {
	typeId: integer(),
	effectId: integer(),
	isDefault: numeric(),
},
(table) => [
	index("ix_dgmTypeEffects_effectID").on(table.effectId),
	primaryKey({ columns: [table.typeId, table.effectId], name: "dgmTypeEffects_typeID_effectID_pk"})
]);

export const invTypeMaterials = sqliteTable("invTypeMaterials", {
	typeId: integer(),
	materialTypeId: integer(),
	quantity: integer(),
},
(table) => [
	index("ix_invTypeMaterials_materialTypeID").on(table.materialTypeId),
	primaryKey({ columns: [table.typeId, table.materialTypeId], name: "invTypeMaterials_typeID_materialTypeID_pk"})
]);

export const invContrabandTypes = sqliteTable("invContrabandTypes", {
	typeId: integer(),
	factionId: integer(),
	attackMinSec: real(),
	confiscateMinSec: real(),
	fineByValue: real(),
	standingLoss: real(),
},
(table) => [
	index("ix_invContrabandTypes_typeID").on(table.typeId),
	primaryKey({ columns: [table.typeId, table.factionId], name: "invContrabandTypes_typeID_factionID_pk"})
]);

export const invControlTowerResources = sqliteTable("invControlTowerResources", {
	controlTowerTypeId: integer(),
	purpose: integer(),
	quantity: integer(),
	resourceTypeId: integer(),
	factionId: integer(),
	minSecurityLevel: real(),
},
(table) => [
	primaryKey({ columns: [table.controlTowerTypeId, table.resourceTypeId], name: "invControlTowerResources_controlTowerTypeID_resourceTypeID_pk"})
]);

export const crpNpcCorporationDivisions = sqliteTable("crpNPCCorporationDivisions", {
	corporationId: integer(),
	divisionId: integer(),
	size: integer(),
},
(table) => [
	primaryKey({ columns: [table.corporationId, table.divisionId], name: "crpNPCCorporationDivisions_corporationID_divisionID_pk"})
]);

export const crpNpcCorporationTrades = sqliteTable("crpNPCCorporationTrades", {
	corporationId: integer(),
	typeId: integer(),
},
(table) => [
	index("ix_crpNPCCorporationTrades_typeID").on(table.typeId),
	primaryKey({ columns: [table.corporationId, table.typeId], name: "crpNPCCorporationTrades_corporationID_typeID_pk"})
]);

export const crpNpcCorporationRaces = sqliteTable("crpNPCCorporationRaces", {
	corporationId: integer(),
	raceId: integer(),
},
(table) => [
	primaryKey({ columns: [table.corporationId, table.raceId], name: "crpNPCCorporationRaces_corporationID_raceID_pk"})
]);

export const crpNpcCorporationLpOfferTables = sqliteTable("crpNPCCorporationLPOfferTables", {
	corporationId: integer(),
	offerTableId: integer(),
},
(table) => [
	primaryKey({ columns: [table.corporationId, table.offerTableId], name: "crpNPCCorporationLPOfferTables_corporationID_offerTableID_pk"})
]);

export const crpNpcCorporationExchangeRates = sqliteTable("crpNPCCorporationExchangeRates", {
	corporationId: integer(),
	targetCorporationId: integer(),
	rate: real(),
},
(table) => [
	primaryKey({ columns: [table.corporationId, table.targetCorporationId], name: "crpNPCCorporationExchangeRates_corporationID_targetCorporationID_pk"})
]);

export const planetSchematicsTypeMap = sqliteTable("planetSchematicsTypeMap", {
	schematicId: integer(),
	typeId: integer(),
	isInput: numeric(),
	quantity: integer(),
},
(table) => [
	primaryKey({ columns: [table.schematicId, table.typeId], name: "planetSchematicsTypeMap_schematicID_typeID_pk"})
]);

export const planetSchematicsPinMap = sqliteTable("planetSchematicsPinMap", {
	schematicId: integer(),
	pinTypeId: integer(),
},
(table) => [
	primaryKey({ columns: [table.schematicId, table.pinTypeId], name: "planetSchematicsPinMap_schematicID_pinTypeID_pk"})
]);

export const staOperationServices = sqliteTable("staOperationServices", {
	operationId: integer(),
	serviceId: integer(),
},
(table) => [
	primaryKey({ columns: [table.operationId, table.serviceId], name: "staOperationServices_operationID_serviceID_pk"})
]);

export const staOperationStationTypes = sqliteTable("staOperationStationTypes", {
	operationId: integer(),
	raceId: integer(),
	stationTypeId: integer(),
},
(table) => [
	primaryKey({ columns: [table.operationId, table.raceId], name: "staOperationStationTypes_operationID_raceID_pk"})
]);

export const skinShip = sqliteTable("skinShip", {
	skinId: integer(),
	typeId: integer(),
},
(table) => [
	index("ix_skinShip_typeID").on(table.typeId),
	primaryKey({ columns: [table.skinId, table.typeId], name: "skinShip_skinID_typeID_pk"})
]);

export const sovUpgradeFuels = sqliteTable("sovUpgradeFuels", {
	upgradeId: integer().primaryKey(),
	hourlyUpkeep: integer(),
	startupCost: integer(),
	fuelTypeId: integer(),
});

export const chrFactionRaces = sqliteTable("chrFactionRaces", {
	factionId: integer(),
	raceId: integer(),
},
(table) => [
	primaryKey({ columns: [table.factionId, table.raceId], name: "chrFactionRaces_factionID_raceID_pk"})
]);

export const chrCloneGradeSkills = sqliteTable("chrCloneGradeSkills", {
	gradeId: integer(),
	level: integer(),
	typeId: integer(),
},
(table) => [
	primaryKey({ columns: [table.gradeId, table.typeId], name: "chrCloneGradeSkills_gradeID_typeID_pk"})
]);

export const chrRaceSkills = sqliteTable("chrRaceSkills", {
	raceId: integer(),
	skillTypeId: integer(),
	level: integer(),
},
(table) => [
	primaryKey({ columns: [table.raceId, table.skillTypeId], name: "chrRaceSkills_raceID_skillTypeID_pk"})
]);

export const invDynamicItemAttributeRanges = sqliteTable("invDynamicItemAttributeRanges", {
	typeId: integer(),
	attributeId: integer(),
	max: real(),
	min: real(),
	highIsGood: numeric(),
},
(table) => [
	index("ix_invDynamicItemAttributeRanges_attributeID").on(table.attributeId),
	primaryKey({ columns: [table.typeId, table.attributeId], name: "invDynamicItemAttributeRanges_typeID_attributeID_pk"})
]);

export const invDynamicItemInputOutput = sqliteTable("invDynamicItemInputOutput", {
	typeId: integer(),
	applicableTypes: text(),
	resultingType: integer(),
},
(table) => [
	primaryKey({ columns: [table.typeId, table.resultingType], name: "invDynamicItemInputOutput_typeID_resultingType_pk"})
]);

export const mapMoonStations = sqliteTable("mapMoonStations", {
	celestialId: integer(),
	stationId: integer(),
},
(table) => [
	index("ix_mapMoonStations_stationID").on(table.stationId),
	primaryKey({ columns: [table.celestialId, table.stationId], name: "mapMoonStations_celestialID_stationID_pk"})
]);

export const mapPlanetAsteroidBelts = sqliteTable("mapPlanetAsteroidBelts", {
	celestialId: integer(),
	asteroidBeltId: integer(),
},
(table) => [
	primaryKey({ columns: [table.celestialId, table.asteroidBeltId], name: "mapPlanetAsteroidBelts_celestialID_asteroidBeltID_pk"})
]);

export const mapPlanetMoons = sqliteTable("mapPlanetMoons", {
	celestialId: integer(),
	moonId: integer(),
},
(table) => [
	index("ix_mapPlanetMoons_moonID").on(table.moonId),
	primaryKey({ columns: [table.celestialId, table.moonId], name: "mapPlanetMoons_celestialID_moonID_pk"})
]);

export const mapPlanetStations = sqliteTable("mapPlanetStations", {
	celestialId: integer(),
	stationId: integer(),
},
(table) => [
	primaryKey({ columns: [table.celestialId, table.stationId], name: "mapPlanetStations_celestialID_stationID_pk"})
]);

export const industryActivity = sqliteTable("industryActivity", {
	typeId: integer(),
	activityId: integer(),
	time: integer(),
},
(table) => [
	index("ix_industryActivity_activityID").on(table.activityId),
	primaryKey({ columns: [table.typeId, table.activityId], name: "industryActivity_typeID_activityID_pk"})
]);

export const industryActivityMaterials = sqliteTable("industryActivityMaterials", {
	typeId: integer(),
	activityId: integer(),
	materialTypeId: integer(),
	quantity: integer(),
},
(table) => [
	index("ix_industryActivityMaterials_typeID_activityID").on(table.typeId, table.activityId),
	index("ix_industryActivityMaterials_typeID").on(table.typeId),
	primaryKey({ columns: [table.typeId, table.activityId, table.materialTypeId], name: "industryActivityMaterials_typeID_activityID_materialTypeID_pk"})
]);

export const industryActivityProducts = sqliteTable("industryActivityProducts", {
	typeId: integer(),
	activityId: integer(),
	productTypeId: integer(),
	quantity: integer(),
},
(table) => [
	index("ix_industryActivityProducts_productTypeID").on(table.productTypeId),
	index("ix_industryActivityProducts_typeID").on(table.typeId),
	primaryKey({ columns: [table.typeId, table.activityId, table.productTypeId], name: "industryActivityProducts_typeID_activityID_productTypeID_pk"})
]);

export const industryActivityProbabilities = sqliteTable("industryActivityProbabilities", {
	typeId: integer(),
	activityId: integer(),
	productTypeId: integer(),
	probability: real(),
},
(table) => [
	index("ix_industryActivityProbabilities_productTypeID").on(table.productTypeId),
	index("ix_industryActivityProbabilities_typeID").on(table.typeId),
	primaryKey({ columns: [table.typeId, table.activityId, table.productTypeId], name: "industryActivityProbabilities_typeID_activityID_productTypeID_pk"})
]);

export const industryActivitySkills = sqliteTable("industryActivitySkills", {
	typeId: integer(),
	activityId: integer(),
	skillId: integer(),
	level: integer(),
},
(table) => [
	index("ix_industryActivitySkills_skillID").on(table.skillId),
	index("ix_industryActivitySkills_typeID_activityID").on(table.typeId, table.activityId),
	index("ix_industryActivitySkills_typeID").on(table.typeId),
]);

export const certCerts = sqliteTable("certCerts", {
	certId: integer().primaryKey(),
	description: text(),
	groupId: integer(),
	name: text(),
});

export const certSkills = sqliteTable("certSkills", {
	certId: integer(),
	skillId: integer(),
	certLevelInt: integer(),
	skillLevel: integer(),
	certLevelText: text(),
},
(table) => [
	index("ix_certSkills_skillID").on(table.skillId),
	primaryKey({ columns: [table.certId, table.skillId, table.certLevelInt], name: "certSkills_certID_skillID_certLevelInt_pk"})
]);

export const certMasteries = sqliteTable("certMasteries", {
	typeId: integer(),
	masteryLevel: integer(),
	certId: integer(),
},
(table) => [
	index("ix_certMasteries_certID").on(table.certId),
	primaryKey({ columns: [table.typeId, table.masteryLevel, table.certId], name: "certMasteries_typeID_masteryLevel_certID_pk"})
]);

export const crpNpcCorporationResearchFields = sqliteTable("crpNPCCorporationResearchFields", {
	skillId: integer(),
	corporationId: integer(),
},
(table) => [
	primaryKey({ columns: [table.skillId, table.corporationId], name: "crpNPCCorporationResearchFields_skillID_corporationID_pk"})
]);

export const mapCelestialStatistics = sqliteTable("mapCelestialStatistics", {
	celestialId: integer().primaryKey(),
	age: real(),
	life: real(),
	luminosity: real(),
	spectralClass: text(),
	temperature: real(),
	density: real(),
	eccentricity: real(),
	escapeVelocity: real(),
	locked: numeric(),
	massDust: real(),
	massGas: real(),
	orbitPeriod: real(),
	orbitRadius: real(),
	pressure: real(),
	rotationRate: real(),
	surfaceGravity: real(),
});

export const mapCelestialGraphics = sqliteTable("mapCelestialGraphics", {
	celestialId: integer().primaryKey(),
	heightMap1: integer(),
	heightMap2: integer(),
	population: numeric(),
	shaderPreset: integer(),
});

export const mapSolarSystemJumps = sqliteTable("mapSolarSystemJumps", {
	fromRegionId: integer(),
	fromConstellationId: integer(),
	fromSolarSystemId: integer(),
	toSolarSystemId: integer(),
	toConstellationId: integer(),
	toRegionId: integer(),
},
(table) => [
	primaryKey({ columns: [table.fromSolarSystemId, table.toSolarSystemId], name: "mapSolarSystemJumps_fromSolarSystemID_toSolarSystemID_pk"})
]);

export const mapConstellationJumps = sqliteTable("mapConstellationJumps", {
	fromRegionId: integer(),
	fromConstellationId: integer(),
	toConstellationId: integer(),
	toRegionId: integer(),
},
(table) => [
	primaryKey({ columns: [table.fromConstellationId, table.toConstellationId], name: "mapConstellationJumps_fromConstellationID_toConstellationID_pk"})
]);

export const mapRegionJumps = sqliteTable("mapRegionJumps", {
	fromRegionId: integer(),
	toRegionId: integer(),
},
(table) => [
	primaryKey({ columns: [table.fromRegionId, table.toRegionId], name: "mapRegionJumps_fromRegionID_toRegionID_pk"})
]);

export const invTraits = sqliteTable("invTraits", {
	traitId: integer().primaryKey(),
	typeId: integer(),
	skillId: integer(),
	bonus: real(),
	bonusText: text(),
	unitId: integer(),
},
(table) => [
	index("ix_invTraits_typeID").on(table.typeId),
]);

export const mapLocationWormholeClasses = sqliteTable("mapLocationWormholeClasses", {
	locationId: integer().primaryKey(),
	wormholeClassId: integer(),
});

export const freelanceJobSchemas = sqliteTable("freelanceJobSchemas", {
	schemaId: text().primaryKey(),
	title: text(),
	description: text(),
	iconId: text(),
	progressDescription: text(),
	rewardDescription: text(),
	targetDescription: text(),
	contentTags: text(),
	maxContributionsPerParticipant: text(),
	contributionMultiplier: real(),
	maxProgressPerContribution: real(),
});

export const freelanceJobSchemaParameters = sqliteTable("freelanceJobSchemaParameters", {
	schemaId: text(),
	parameterId: text(),
	type: text(),
	maxEntries: integer(),
	optional: numeric(),
	title: text(),
	description: text(),
	acceptedValueTypes: text(),
},
(table) => [
	primaryKey({ columns: [table.schemaId, table.parameterId], name: "freelanceJobSchemaParameters_schemaID_parameterID_pk"})
]);

export const dbuffCollectionModifiers = sqliteTable("dbuffCollectionModifiers", {
	dbuffCollectionId: integer(),
	modifierType: text(),
	dogmaAttributeId: integer(),
	groupId: integer(),
	skillId: integer(),
},
(table) => [
	index("ix_dbuffCollectionModifiers_dbuffCollectionID").on(table.dbuffCollectionId),
]);

export const mapDenormalize = sqliteTable("mapDenormalize", {
	itemId: integer().primaryKey(),
	typeId: integer(),
	groupId: integer(),
	solarSystemId: integer(),
	constellationId: integer(),
	regionId: integer(),
	orbitId: integer(),
	x: real(),
	y: real(),
	z: real(),
	radius: real(),
	itemName: text(),
	security: real(),
	celestialIndex: integer(),
	orbitIndex: integer(),
},
(table) => [
	index("mapDenormalize_IX_groupRegion").on(table.groupId, table.regionId),
	index("mapDenormalize_IX_groupConstellation").on(table.groupId, table.constellationId),
	index("mapDenormalize_IX_groupSystem").on(table.groupId, table.solarSystemId),
	index("ix_mapDenormalize_typeID").on(table.typeId),
	index("ix_mapDenormalize_orbitID").on(table.orbitId),
	index("ix_mapDenormalize_regionID").on(table.regionId),
	index("ix_mapDenormalize_constellationID").on(table.constellationId),
	index("ix_mapDenormalize_solarSystemID").on(table.solarSystemId),
]);

export const invMetaTypes = sqliteTable("invMetaTypes", {
	typeId: integer().primaryKey().notNull(),
	parentTypeId: integer(),
	metaGroupId: integer(),
});

export const invItems = sqliteTable("invItems", {
	itemId: integer().primaryKey().notNull(),
	typeId: integer().notNull(),
	ownerId: integer().notNull(),
	locationId: integer().notNull(),
	flagId: integer().notNull(),
	quantity: integer().notNull(),
},
(table) => [
	index("items_IX_OwnerLocation").on(table.ownerId, table.locationId),
	index("ix_invItems_locationID").on(table.locationId),
]);

export const invUniqueNames = sqliteTable("invUniqueNames", {
	itemId: integer().primaryKey().notNull(),
	itemName: text().notNull(),
	groupId: integer(),
},
(table) => [
	index("ix_invUniqueNames_itemName").on(table.itemName),
	index("invUniqueNames_IX_GroupName").on(table.groupId, table.itemName),
]);