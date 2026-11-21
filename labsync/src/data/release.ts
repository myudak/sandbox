/*
 * Releases come from GitHub (myudak/sandbox, tags `labsync-v*`), read once at build time.
 * If GitHub can't be reached (rate limit, offline build), the page falls back to FALLBACK below,
 * so keep it in step with the newest release.
 */

export interface Release {
  version: string;
  tag: string;
  date: string;
  notes: string[];
  apkUrl: string;
  apkSize?: number;
  pageUrl: string;
}

const REPO = 'myudak/sandbox';
const PREFIX = 'labsync-v';
export const RELEASES_URL = `https://github.com/${REPO}/releases?q=${PREFIX}&expanded=true`;

const FALLBACK: Release = {
  version: '1.0.0',
  tag: 'labsync-v1.0.0',
  date: '2026-11-21',
  notes: [
    'Presensi berbasis lokasi (radius lab) dan QR bertanda tangan yang berganti tiap 15 detik.',
    'Izin praktikum dengan lampiran, dipilah otomatis, ditinjau asisten.',
    'Kuis di pertemuan dengan mode terkunci: peringatan, kirim otomatis setelah pelanggaran ke-4.',
    'Rekap kehadiran live, buku nilai, dan ekspor Excel.',
    'Log audit berantai hash per kelas dan global.',
    'Peta lab dengan foto ruangan, bagikan pertemuan ke WhatsApp, tata letak tablet.',
  ],
  apkUrl: `https://github.com/${REPO}/releases/download/labsync-v1.0.0/labsync-1.0.0.apk`,
  pageUrl: `https://github.com/${REPO}/releases/tag/labsync-v1.0.0`,
};

interface GhRelease {
  tag_name: string;
  name: string | null;
  body: string | null;
  draft: boolean;
  prerelease: boolean;
  published_at: string | null;
  html_url: string;
  assets: { name: string; size: number; browser_download_url: string }[];
}

/** "- item" lines of a release body become the bullet list. */
const bullets = (body: string | null) =>
  (body ?? '')
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter((l) => /^[-*] /.test(l))
    .map((l) => l.slice(2).replace(/\*\*(.+?)\*\*/g, '$1').trim());

export async function getReleases(): Promise<Release[]> {
  try {
    const res = await fetch(`https://api.github.com/repos/${REPO}/releases?per_page=50`, {
      headers: { Accept: 'application/vnd.github+json', 'User-Agent': 'labsync-landing' },
    });
    if (!res.ok) throw new Error(`github ${res.status}`);
    const all = (await res.json()) as GhRelease[];
    const mine = all
      .filter((r) => r.tag_name.startsWith(PREFIX) && !r.draft)
      .map((r): Release | null => {
        const apk = r.assets.find((a) => a.name.endsWith('.apk'));
        if (!apk) return null;
        const notes = bullets(r.body);
        return {
          version: r.tag_name.slice(PREFIX.length),
          tag: r.tag_name,
          date: (r.published_at ?? '').slice(0, 10),
          notes: notes.length ? notes : FALLBACK.notes,
          apkUrl: apk.browser_download_url,
          apkSize: apk.size,
          pageUrl: r.html_url,
        };
      })
      .filter((r): r is Release => r !== null);
    return mine.length ? mine : [FALLBACK];
  } catch (e) {
    console.warn('[releases] using fallback:', (e as Error).message);
    return [FALLBACK];
  }
}

export const formatSize = (bytes?: number) => (bytes ? `${(bytes / 1024 / 1024).toFixed(0)} MB` : '');

export const formatDate = (iso: string) =>
  new Date(`${iso}T00:00:00Z`).toLocaleDateString('id-ID', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });
