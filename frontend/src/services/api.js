/**
 * API Service Client for Link Analytics Platform
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
export const DISPLAY_DOMAIN = import.meta.env.VITE_DISPLAY_DOMAIN || 'lnk.dev';

export function getLinkUrls(shortCode) {
  return {
    display: `${DISPLAY_DOMAIN}/${shortCode}`,
    target: `${API_BASE_URL}/${shortCode}`,
  };
}

async function handleResponse(response) {
  if (!response.ok) {
    let errorDetail = 'An unexpected error occurred';
    try {
      const errorData = await response.json();
      if (typeof errorData.detail === 'string') {
        errorDetail = errorData.detail;
      } else if (Array.isArray(errorData.detail)) {
        errorDetail = errorData.detail.map((err) => `${err.loc.slice(-1)[0]}: ${err.msg}`).join(', ');
      }
    } catch {
      if (response.status === 429) {
        errorDetail = 'Rate limit exceeded (Too many requests). Please slow down.';
      } else {
        errorDetail = `Server responded with status ${response.status}`;
      }
    }
    const error = new Error(errorDetail);
    error.status = response.status;
    throw error;
  }
  if (response.status === 204) return null;
  return response.json();
}

export async function createShortLink(originalUrl, customAlias = '') {
  const payload = { original_url: originalUrl };
  if (customAlias.trim()) {
    payload.custom_alias = customAlias.trim();
  }

  const res = await fetch(`${API_BASE_URL}/links`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return handleResponse(res);
}

export async function getLinkStats(shortCode) {
  const res = await fetch(`${API_BASE_URL}/links/${encodeURIComponent(shortCode)}/stats`);
  return handleResponse(res);
}

export async function getLinkAnalytics(shortCode) {
  const res = await fetch(`${API_BASE_URL}/links/${encodeURIComponent(shortCode)}/analytics`);
  return handleResponse(res);
}

export async function getHealth() {
  const res = await fetch(`${API_BASE_URL}/health`);
  return handleResponse(res);
}

export { API_BASE_URL };
