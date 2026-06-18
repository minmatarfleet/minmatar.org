const DEFAULT_API_URL = 'http://localhost:8000';

export function getApiUrl(): string {
  const value = process.env.EXPO_PUBLIC_API_URL?.trim();
  return value || DEFAULT_API_URL;
}

export function getEveLoginUrl(redirectUrl: string): string {
  return `${getApiUrl()}/api/users/login/eve?redirect_url=${encodeURIComponent(redirectUrl)}`;
}
