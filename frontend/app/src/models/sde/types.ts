// src/models/types.ts
import type { InferSelectModel } from 'drizzle-orm';
import {
    crpNPCCorporations,
    staOperations,
    invVolumes,
    industryActivityProbabilities,
    ramAssemblyLineStations,
    ramAssemblyLineTypes,
    invMarketGroups,
    trnTranslationLanguages,
    chrAttributes,
    industryActivityProducts,
    planetSchematicsPinMap,
    mapRegionJumps,
    skinMaterials,
    mapSolarSystems,
    trnTranslationColumns,
    eveIcons,
    mapRegions,
    industryActivityRaces,
    skins,
    invTypeReactions,
    eveUnits,
    agtAgentTypes,
    planetSchematicsTypeMap,
    ramInstallationTypeContents,
    invUniqueNames,
    chrAncestries,
    mapLocationScenes,
    invTypes,
    industryActivity,
    invControlTowerResources,
    mapJumps,
    certCerts,
    industryBlueprints,
    invTypeMaterials,
    ramAssemblyLineTypeDetailPerGroup,
    trnTranslations,
    dgmAttributeTypes,
    agtResearchAgents,
    mapSolarSystemJumps,
    mapCelestialStatistics,
    mapConstellationJumps,
    mapCelestialGraphics,
    staServices,
    warCombatZoneSystems,
    industryActivityMaterials,
    mapLandmarks,
    invFlags,
    invContrabandTypes,
    invControlTowerResourcePurposes,
    staStationTypes,
    invTraits,
    invPositions,
    certSkills,
    skinLicense,
    dgmTypeAttributes,
    mapConstellations,
    crpNPCCorporationDivisions,
    dgmAttributeCategories,
    translationTables,
    planetSchematics,
    invMetaTypes,
    certMasteries,
    crpNPCCorporationResearchFields,
    crpNPCDivisions,
    dgmTypeEffects,
    invNames,
    mapDenormalize,
    chrRaces,
    agtAgentsInSpace,
    crpActivities,
    chrFactions,
    eveGraphics,
    invCategories,
    staStations,
    mapLocationWormholeClasses,
    invItems,
    mapUniverse,
    skinShip,
    crpNPCCorporationTrades,
    chrBloodlines,
    warCombatZones,
    invMetaGroups,
    industryActivitySkills,
    staOperationServices,
    dgmEffects,
    ramAssemblyLineTypeDetailPerCategory,
    dgmExpressions,
    ramActivities,
    agtAgents,
    invGroups,
} from './schema.ts';

export type crpNPCCorporations = InferSelectModel<typeof crpNPCCorporations>
export type staOperations = InferSelectModel<typeof staOperations>
export type invVolumes = InferSelectModel<typeof invVolumes>
export type industryActivityProbabilities = InferSelectModel<typeof industryActivityProbabilities>
export type ramAssemblyLineStations = InferSelectModel<typeof ramAssemblyLineStations>
export type ramAssemblyLineTypes = InferSelectModel<typeof ramAssemblyLineTypes>
export type invMarketGroups = InferSelectModel<typeof invMarketGroups>
export type trnTranslationLanguages = InferSelectModel<typeof trnTranslationLanguages>
export type chrAttributes = InferSelectModel<typeof chrAttributes>
export type industryActivityProducts = InferSelectModel<typeof industryActivityProducts>
export type planetSchematicsPinMap = InferSelectModel<typeof planetSchematicsPinMap>
export type mapRegionJumps = InferSelectModel<typeof mapRegionJumps>
export type skinMaterials = InferSelectModel<typeof skinMaterials>
export type mapSolarSystems = InferSelectModel<typeof mapSolarSystems>
export type trnTranslationColumns = InferSelectModel<typeof trnTranslationColumns>
export type eveIcons = InferSelectModel<typeof eveIcons>
export type mapRegions = InferSelectModel<typeof mapRegions>
export type industryActivityRaces = InferSelectModel<typeof industryActivityRaces>
export type skins = InferSelectModel<typeof skins>
export type invTypeReactions = InferSelectModel<typeof invTypeReactions>
export type eveUnits = InferSelectModel<typeof eveUnits>
export type agtAgentTypes = InferSelectModel<typeof agtAgentTypes>
export type planetSchematicsTypeMap = InferSelectModel<typeof planetSchematicsTypeMap>
export type ramInstallationTypeContents = InferSelectModel<typeof ramInstallationTypeContents>
export type invUniqueNames = InferSelectModel<typeof invUniqueNames>
export type chrAncestries = InferSelectModel<typeof chrAncestries>
export type mapLocationScenes = InferSelectModel<typeof mapLocationScenes>
export type invTypes = InferSelectModel<typeof invTypes>
export type industryActivity = InferSelectModel<typeof industryActivity>
export type invControlTowerResources = InferSelectModel<typeof invControlTowerResources>
export type mapJumps = InferSelectModel<typeof mapJumps>
export type certCerts = InferSelectModel<typeof certCerts>
export type industryBlueprints = InferSelectModel<typeof industryBlueprints>
export type invTypeMaterials = InferSelectModel<typeof invTypeMaterials>
export type ramAssemblyLineTypeDetailPerGroup = InferSelectModel<typeof ramAssemblyLineTypeDetailPerGroup>
export type trnTranslations = InferSelectModel<typeof trnTranslations>
export type dgmAttributeTypes = InferSelectModel<typeof dgmAttributeTypes>
export type agtResearchAgents = InferSelectModel<typeof agtResearchAgents>
export type mapSolarSystemJumps = InferSelectModel<typeof mapSolarSystemJumps>
export type mapCelestialStatistics = InferSelectModel<typeof mapCelestialStatistics>
export type mapConstellationJumps = InferSelectModel<typeof mapConstellationJumps>
export type mapCelestialGraphics = InferSelectModel<typeof mapCelestialGraphics>
export type staServices = InferSelectModel<typeof staServices>
export type warCombatZoneSystems = InferSelectModel<typeof warCombatZoneSystems>
export type industryActivityMaterials = InferSelectModel<typeof industryActivityMaterials>
export type mapLandmarks = InferSelectModel<typeof mapLandmarks>
export type invFlags = InferSelectModel<typeof invFlags>
export type invContrabandTypes = InferSelectModel<typeof invContrabandTypes>
export type invControlTowerResourcePurposes = InferSelectModel<typeof invControlTowerResourcePurposes>
export type staStationTypes = InferSelectModel<typeof staStationTypes>
export type invTraits = InferSelectModel<typeof invTraits>
export type invPositions = InferSelectModel<typeof invPositions>
export type certSkills = InferSelectModel<typeof certSkills>
export type skinLicense = InferSelectModel<typeof skinLicense>
export type dgmTypeAttributes = InferSelectModel<typeof dgmTypeAttributes>
export type mapConstellations = InferSelectModel<typeof mapConstellations>
export type crpNPCCorporationDivisions = InferSelectModel<typeof crpNPCCorporationDivisions>
export type dgmAttributeCategories = InferSelectModel<typeof dgmAttributeCategories>
export type translationTables = InferSelectModel<typeof translationTables>
export type planetSchematics = InferSelectModel<typeof planetSchematics>
export type invMetaTypes = InferSelectModel<typeof invMetaTypes>
export type certMasteries = InferSelectModel<typeof certMasteries>
export type crpNPCCorporationResearchFields = InferSelectModel<typeof crpNPCCorporationResearchFields>
export type crpNPCDivisions = InferSelectModel<typeof crpNPCDivisions>
export type dgmTypeEffects = InferSelectModel<typeof dgmTypeEffects>
export type invNames = InferSelectModel<typeof invNames>
export type mapDenormalize = InferSelectModel<typeof mapDenormalize>
export type chrRaces = InferSelectModel<typeof chrRaces>
export type agtAgentsInSpace = InferSelectModel<typeof agtAgentsInSpace>
export type crpActivities = InferSelectModel<typeof crpActivities>
export type chrFactions = InferSelectModel<typeof chrFactions>
export type eveGraphics = InferSelectModel<typeof eveGraphics>
export type invCategories = InferSelectModel<typeof invCategories>
export type staStations = InferSelectModel<typeof staStations>
export type mapLocationWormholeClasses = InferSelectModel<typeof mapLocationWormholeClasses>
export type invItems = InferSelectModel<typeof invItems>
export type mapUniverse = InferSelectModel<typeof mapUniverse>
export type skinShip = InferSelectModel<typeof skinShip>
export type crpNPCCorporationTrades = InferSelectModel<typeof crpNPCCorporationTrades>
export type chrBloodlines = InferSelectModel<typeof chrBloodlines>
export type warCombatZones = InferSelectModel<typeof warCombatZones>
export type invMetaGroups = InferSelectModel<typeof invMetaGroups>
export type industryActivitySkills = InferSelectModel<typeof industryActivitySkills>
export type staOperationServices = InferSelectModel<typeof staOperationServices>
export type dgmEffects = InferSelectModel<typeof dgmEffects>
export type ramAssemblyLineTypeDetailPerCategory = InferSelectModel<typeof ramAssemblyLineTypeDetailPerCategory>
export type dgmExpressions = InferSelectModel<typeof dgmExpressions>
export type ramActivities = InferSelectModel<typeof ramActivities>
export type agtAgents = InferSelectModel<typeof agtAgents>
export type invGroups = InferSelectModel<typeof invGroups>