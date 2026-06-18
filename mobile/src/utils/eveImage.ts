/** Minmatar Fleet Alliance (FL33T) */
export const MINMATAR_FLEET_ALLIANCE_ID = 99011978;

export type EveImageSize = 32 | 64 | 128 | 256 | 512 | 1024;

export function getPlayerIcon(id: number, size: EveImageSize = 64): string {
  return `https://images.evetech.net/characters/${id}/portrait?size=${size}`;
}

export function getCorporationLogo(id: number, size: EveImageSize = 32): string {
  return `https://images.evetech.net/corporations/${id}/logo?size=${size}`;
}

export function getAllianceLogo(id: number, size: EveImageSize = 64): string {
  return `https://images.evetech.net/alliances/${id}/logo?size=${size}`;
}

export function getMinmatarFleetAllianceLogo(size: EveImageSize = 64): string {
  return getAllianceLogo(MINMATAR_FLEET_ALLIANCE_ID, size);
}
