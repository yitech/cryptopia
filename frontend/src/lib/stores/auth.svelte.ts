import { api } from '$lib/api';
import type { Me } from '$lib/types';

let _me = $state<Me | null>(null);
let _loading = $state(true);
let _loaded = false;

async function refresh() {
  try {
    _me = await api.me();
  } catch {
    _me = null;
  } finally {
    _loading = false;
    _loaded = true;
  }
}

export const auth = {
  get me() {
    if (!_loaded && typeof window !== 'undefined') {
      void refresh();
    }
    return _me;
  },
  get loading() {
    return _loading;
  },
  refresh
};

export function loginUrl(returnTo: string): string {
  const me = _me;
  // Authelia redirects back to whichever URL we send via the `rd` parameter.
  // We let the reverse proxy handle that contract — Cryptopia just makes
  // sure the user lands somewhere useful afterwards.
  const base = me?.authelia_url ?? 'https://auth.lynxlinkage.com';
  const url = new URL('/', base);
  url.searchParams.set('rd', returnTo);
  return url.toString();
}
