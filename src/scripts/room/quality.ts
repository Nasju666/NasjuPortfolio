// Picks a render quality tier for this device so cheap phones stay smooth.
// The room is cheap to draw either way; the tier mostly controls pixel count.

export type Tier = 'low' | 'mid' | 'high';

export interface Quality {
  tier: Tier;
  pixelRatio: number;
  antialias: boolean;
}

export function detectQuality(): Quality {
  const nav = navigator as Navigator & { deviceMemory?: number; connection?: { saveData?: boolean } };
  const memory = nav.deviceMemory ?? 4; // GB, Chrome/Android only; others report nothing
  const cores = nav.hardwareConcurrency ?? 4;
  const coarse = matchMedia('(pointer: coarse)').matches;
  const saveData = !!nav.connection?.saveData;

  let tier: Tier = 'high';
  if (memory <= 2 || cores <= 2 || saveData) tier = 'low';
  else if (coarse || memory <= 4 || cores <= 4) tier = 'mid';

  // Allow forcing a tier for testing: add ?quality=low to the URL.
  const forced = new URLSearchParams(location.search).get('quality');
  if (forced === 'low' || forced === 'mid' || forced === 'high') tier = forced;

  const dpr = window.devicePixelRatio || 1;
  const cap = tier === 'low' ? 1 : tier === 'mid' ? 1.5 : 2;
  return {
    tier,
    pixelRatio: Math.min(dpr, cap),
    // On high-DPR screens extra pixels already smooth edges, so MSAA is only worth it on desktop.
    antialias: tier === 'high',
  };
}

export function hasWebGL(): boolean {
  try {
    const c = document.createElement('canvas');
    return !!(c.getContext('webgl2') || c.getContext('webgl'));
  } catch {
    return false;
  }
}
