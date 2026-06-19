const PRODUCTION_API_URL = 'https://api.minmatar.org';

export function getApiUrl(): string {
  const value = process.env.EXPO_PUBLIC_API_URL?.trim();
  return value || PRODUCTION_API_URL;
}

export function getEveLoginUrl(redirectUrl: string): string {
  return `${getApiUrl()}/api/users/login/eve?redirect_url=${encodeURIComponent(redirectUrl)}`;
}

export const MY_MINMATAR_URL = 'https://my.minmatar.org';
