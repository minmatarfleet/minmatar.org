import { MY_MINMATAR_URL } from '@/src/config/env';

/** Minmatar Fleet Alliance (FL33T) */
export const MINMATAR_FLEET_ALLIANCE_ID = 99011978;

export type EveImageSize = 32 | 64 | 128 | 256 | 512 | 1024;

export function getPlayerIcon(id: number, size: EveImageSize = 64): string {
  return `https://images.evetech.net/characters/${id}/portrait?size=${size}`;
}

export function getTypeIcon(typeId: number, size: EveImageSize = 32): string {
  return `https://images.evetech.net/types/${typeId}/icon?size=${size}`;
}

export function getTypeRender(typeId: number, size: EveImageSize = 256): string {
  return `https://images.evetech.net/types/${typeId}/render?size=${size}`;
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

/** Site card covers (PictureCard / GroupCard pattern on my.minmatar.org). */
export function getWarzoneCardCover(): string {
  return `${MY_MINMATAR_URL}/images/warzone-card.jpg`;
}

export function getFrontlinesCover(): string {
  return `${MY_MINMATAR_URL}/images/frontlines-cover.png`;
}
