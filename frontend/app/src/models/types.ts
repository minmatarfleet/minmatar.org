// src/models/types.ts
import type { InferSelectModel } from 'drizzle-orm';
import {
    invTypeBonus,
    invTypeDogma,
    agtAgentTypes,
    staOperations,
    skinLicense,
    dbuffCollections,
    dgmAttributeTypes,
    mapRegions,
    invDynamicItemAttributes,
    agtAgentsInSpace,
    planetSchematics,
    eveUnits,
    dgmAttributeCategories,
    chrNpcCharacters,
    mapPlanets,
    crpActivities,
    chrAttributes,
    mercenaryTacticalOperations,
    mapConstellations,
    invMarketGroups,
    chrMasteries,
    chrCertificates,
    mapSecondarySuns,
    chrAncestries,
    chrCloneGrades,
    planetResources,
    mapLandmarks,
    invCategories,
    mapAsteroidBelts,
    mapStargates,
    industryBlueprints,
    mapStars,
    invGroups,
    invTypes,
    mapSolarSystems,
    staServices,
    invMetaGroups,
    invCompressibleTypes,
    crpNpcCorporations,
    chrBloodlines,
    skins,
    dgmEffects,
    chrFactions,
    staStations,
    chrRaces,
    eveIcons,
    mapMoons,
    crpNpcDivisions,
    eveGraphics,
    sovUpgrades,
    translationLanguages,
    skinMaterials,
    agtAgents,
    agtResearchAgents,
    dgmTypeAttributes,
    dgmTypeEffects,
    invTypeMaterials,
    invContrabandTypes,
    invControlTowerResources,
    crpNpcCorporationDivisions,
    crpNpcCorporationTrades,
    crpNpcCorporationRaces,
    crpNpcCorporationLpOfferTables,
    crpNpcCorporationExchangeRates,
    planetSchematicsTypeMap,
    planetSchematicsPinMap,
    staOperationServices,
    staOperationStationTypes,
    skinShip,
    sovUpgradeFuels,
    chrFactionRaces,
    chrCloneGradeSkills,
    chrRaceSkills,
    invDynamicItemAttributeRanges,
    invDynamicItemInputOutput,
    mapMoonStations,
    mapPlanetAsteroidBelts,
    mapPlanetMoons,
    mapPlanetStations,
    industryActivity,
    industryActivityMaterials,
    industryActivityProducts,
    industryActivityProbabilities,
    industryActivitySkills,
    certCerts,
    certSkills,
    certMasteries,
    crpNpcCorporationResearchFields,
    mapCelestialStatistics,
    mapCelestialGraphics,
    mapSolarSystemJumps,
    mapConstellationJumps,
    mapRegionJumps,
    invTraits,
    mapLocationWormholeClasses,
    freelanceJobSchemas,
    freelanceJobSchemaParameters,
    dbuffCollectionModifiers,
    mapDenormalize,
    invMetaTypes,
    invItems,
    invUniqueNames,
} from './sde/schema.ts';

export type invTypeBonus = InferSelectModel<typeof invTypeBonus>
export type invTypeDogma = InferSelectModel<typeof invTypeDogma>
export type agtAgentTypes = InferSelectModel<typeof agtAgentTypes>
export type staOperations = InferSelectModel<typeof staOperations>
export type skinLicense = InferSelectModel<typeof skinLicense>
export type dbuffCollections = InferSelectModel<typeof dbuffCollections>
export type dgmAttributeTypes = InferSelectModel<typeof dgmAttributeTypes>
export type mapRegions = InferSelectModel<typeof mapRegions>
export type invDynamicItemAttributes = InferSelectModel<typeof invDynamicItemAttributes>
export type agtAgentsInSpace = InferSelectModel<typeof agtAgentsInSpace>
export type planetSchematics = InferSelectModel<typeof planetSchematics>
export type eveUnits = InferSelectModel<typeof eveUnits>
export type dgmAttributeCategories = InferSelectModel<typeof dgmAttributeCategories>
export type chrNpcCharacters = InferSelectModel<typeof chrNpcCharacters>
export type mapPlanets = InferSelectModel<typeof mapPlanets>
export type crpActivities = InferSelectModel<typeof crpActivities>
export type chrAttributes = InferSelectModel<typeof chrAttributes>
export type mercenaryTacticalOperations = InferSelectModel<typeof mercenaryTacticalOperations>
export type mapConstellations = InferSelectModel<typeof mapConstellations>
export type invMarketGroups = InferSelectModel<typeof invMarketGroups>
export type chrMasteries = InferSelectModel<typeof chrMasteries>
export type chrCertificates = InferSelectModel<typeof chrCertificates>
export type mapSecondarySuns = InferSelectModel<typeof mapSecondarySuns>
export type chrAncestries = InferSelectModel<typeof chrAncestries>
export type chrCloneGrades = InferSelectModel<typeof chrCloneGrades>
export type planetResources = InferSelectModel<typeof planetResources>
export type mapLandmarks = InferSelectModel<typeof mapLandmarks>
export type invCategories = InferSelectModel<typeof invCategories>
export type mapAsteroidBelts = InferSelectModel<typeof mapAsteroidBelts>
export type mapStargates = InferSelectModel<typeof mapStargates>
export type industryBlueprints = InferSelectModel<typeof industryBlueprints>
export type mapStars = InferSelectModel<typeof mapStars>
export type invGroups = InferSelectModel<typeof invGroups>
export type invTypes = InferSelectModel<typeof invTypes>
export type mapSolarSystems = InferSelectModel<typeof mapSolarSystems>
export type staServices = InferSelectModel<typeof staServices>
export type invMetaGroups = InferSelectModel<typeof invMetaGroups>
export type invCompressibleTypes = InferSelectModel<typeof invCompressibleTypes>
export type crpNpcCorporations = InferSelectModel<typeof crpNpcCorporations>
export type chrBloodlines = InferSelectModel<typeof chrBloodlines>
export type skins = InferSelectModel<typeof skins>
export type dgmEffects = InferSelectModel<typeof dgmEffects>
export type chrFactions = InferSelectModel<typeof chrFactions>
export type staStations = InferSelectModel<typeof staStations>
export type chrRaces = InferSelectModel<typeof chrRaces>
export type eveIcons = InferSelectModel<typeof eveIcons>
export type mapMoons = InferSelectModel<typeof mapMoons>
export type crpNpcDivisions = InferSelectModel<typeof crpNpcDivisions>
export type eveGraphics = InferSelectModel<typeof eveGraphics>
export type sovUpgrades = InferSelectModel<typeof sovUpgrades>
export type translationLanguages = InferSelectModel<typeof translationLanguages>
export type skinMaterials = InferSelectModel<typeof skinMaterials>
export type agtAgents = InferSelectModel<typeof agtAgents>
export type agtResearchAgents = InferSelectModel<typeof agtResearchAgents>
export type dgmTypeAttributes = InferSelectModel<typeof dgmTypeAttributes>
export type dgmTypeEffects = InferSelectModel<typeof dgmTypeEffects>
export type invTypeMaterials = InferSelectModel<typeof invTypeMaterials>
export type invContrabandTypes = InferSelectModel<typeof invContrabandTypes>
export type invControlTowerResources = InferSelectModel<typeof invControlTowerResources>
export type crpNpcCorporationDivisions = InferSelectModel<typeof crpNpcCorporationDivisions>
export type crpNpcCorporationTrades = InferSelectModel<typeof crpNpcCorporationTrades>
export type crpNpcCorporationRaces = InferSelectModel<typeof crpNpcCorporationRaces>
export type crpNpcCorporationLpOfferTables = InferSelectModel<typeof crpNpcCorporationLpOfferTables>
export type crpNpcCorporationExchangeRates = InferSelectModel<typeof crpNpcCorporationExchangeRates>
export type planetSchematicsTypeMap = InferSelectModel<typeof planetSchematicsTypeMap>
export type planetSchematicsPinMap = InferSelectModel<typeof planetSchematicsPinMap>
export type staOperationServices = InferSelectModel<typeof staOperationServices>
export type staOperationStationTypes = InferSelectModel<typeof staOperationStationTypes>
export type skinShip = InferSelectModel<typeof skinShip>
export type sovUpgradeFuels = InferSelectModel<typeof sovUpgradeFuels>
export type chrFactionRaces = InferSelectModel<typeof chrFactionRaces>
export type chrCloneGradeSkills = InferSelectModel<typeof chrCloneGradeSkills>
export type chrRaceSkills = InferSelectModel<typeof chrRaceSkills>
export type invDynamicItemAttributeRanges = InferSelectModel<typeof invDynamicItemAttributeRanges>
export type invDynamicItemInputOutput = InferSelectModel<typeof invDynamicItemInputOutput>
export type mapMoonStations = InferSelectModel<typeof mapMoonStations>
export type mapPlanetAsteroidBelts = InferSelectModel<typeof mapPlanetAsteroidBelts>
export type mapPlanetMoons = InferSelectModel<typeof mapPlanetMoons>
export type mapPlanetStations = InferSelectModel<typeof mapPlanetStations>
export type industryActivity = InferSelectModel<typeof industryActivity>
export type industryActivityMaterials = InferSelectModel<typeof industryActivityMaterials>
export type industryActivityProducts = InferSelectModel<typeof industryActivityProducts>
export type industryActivityProbabilities = InferSelectModel<typeof industryActivityProbabilities>
export type industryActivitySkills = InferSelectModel<typeof industryActivitySkills>
export type certCerts = InferSelectModel<typeof certCerts>
export type certSkills = InferSelectModel<typeof certSkills>
export type certMasteries = InferSelectModel<typeof certMasteries>
export type crpNpcCorporationResearchFields = InferSelectModel<typeof crpNpcCorporationResearchFields>
export type mapCelestialStatistics = InferSelectModel<typeof mapCelestialStatistics>
export type mapCelestialGraphics = InferSelectModel<typeof mapCelestialGraphics>
export type mapSolarSystemJumps = InferSelectModel<typeof mapSolarSystemJumps>
export type mapConstellationJumps = InferSelectModel<typeof mapConstellationJumps>
export type mapRegionJumps = InferSelectModel<typeof mapRegionJumps>
export type invTraits = InferSelectModel<typeof invTraits>
export type mapLocationWormholeClasses = InferSelectModel<typeof mapLocationWormholeClasses>
export type freelanceJobSchemas = InferSelectModel<typeof freelanceJobSchemas>
export type freelanceJobSchemaParameters = InferSelectModel<typeof freelanceJobSchemaParameters>
export type dbuffCollectionModifiers = InferSelectModel<typeof dbuffCollectionModifiers>
export type mapDenormalize = InferSelectModel<typeof mapDenormalize>
export type invMetaTypes = InferSelectModel<typeof invMetaTypes>
export type invItems = InferSelectModel<typeof invItems>
export type invUniqueNames = InferSelectModel<typeof invUniqueNames>