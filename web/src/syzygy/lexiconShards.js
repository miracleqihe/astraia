import { publicAssetUrl } from '../publicAssetUrl.js';

const taxonomyCache = new Map();
const inflightTaxonomy = new Map();
const shardCache = new Map();

function normalizeRoot(root) {
  if (root == null) return './';
  const text = String(root);
  if (!text) return '';
  return text.endsWith('/') ? text : `${text}/`;
}

function normalizeText(value) {
  return String(value ?? '').normalize('NFKC').toLocaleLowerCase();
}

function decodeUtf8Json(bytes) {
  return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes));
}

function resolveShard(taxonomyOrManifest, domainId) {
  if (!taxonomyOrManifest || typeof taxonomyOrManifest !== 'object') return null;

  if (Array.isArray(taxonomyOrManifest.domains)) {
    const domain = taxonomyOrManifest.domains.find((item) => item && item.id === domainId);
    return domain?.lexicon_shard ?? null;
  }

  if (taxonomyOrManifest.domains && typeof taxonomyOrManifest.domains === 'object') {
    return taxonomyOrManifest.domains[domainId] ?? null;
  }

  if (taxonomyOrManifest.lexicon_shard && (!taxonomyOrManifest.id || taxonomyOrManifest.id === domainId)) {
    return taxonomyOrManifest.lexicon_shard;
  }

  if (taxonomyOrManifest.hub_to_domain && typeof taxonomyOrManifest.hub_to_domain === 'object') {
    for (const info of Object.values(taxonomyOrManifest.hub_to_domain)) {
      if (info && info.domain_id === domainId && info.shard) return info.shard;
    }
  }

  if (typeof taxonomyOrManifest.file === 'string') {
    return taxonomyOrManifest;
  }

  return null;
}

export function clearLexiconCache() {
  taxonomyCache.clear();
  inflightTaxonomy.clear();
  shardCache.clear();
}

/**
 * Fetch and cache syzygy/taxonomy.json, returning null gracefully when unavailable or 404.
 */
export async function loadTaxonomy(root = './') {
  const base = normalizeRoot(root);
  if (taxonomyCache.has(base)) return taxonomyCache.get(base);
  if (inflightTaxonomy.has(base)) return inflightTaxonomy.get(base);

  if (typeof globalThis.fetch !== 'function') return null;

  const pending = (async () => {
    try {
      const response = await globalThis.fetch(publicAssetUrl(base, 'syzygy/taxonomy.json'), { cache: 'no-cache' });
      if (!response || !response.ok) return null;
      const bytes = await response.arrayBuffer();
      const data = decodeUtf8Json(bytes);
      if (!data || typeof data !== 'object' || !Array.isArray(data.domains)) return null;
      taxonomyCache.set(base, data);
      return data;
    } catch {
      return null;
    } finally {
      inflightTaxonomy.delete(base);
    }
  })();

  inflightTaxonomy.set(base, pending);
  return pending;
}

/**
 * Lazily fetch, SHA-256 verify, and cache a domain lexicon shard.
 */
export async function loadLexiconShard(root, taxonomyOrManifest, domainId) {
  if (!domainId) throw new Error('缺少专题域标识。');
  const shard = resolveShard(taxonomyOrManifest, domainId);
  if (!shard || typeof shard.file !== 'string' || !shard.file.trim()) {
    throw new Error(`专题辞条分片尚未就绪：${domainId}`);
  }

  const rawFile = shard.file.replace(/^\/+/, '');
  if (!rawFile || rawFile.includes('..') || rawFile.includes('\\')) {
    throw new Error('专题辞条分片路径无效。');
  }

  const base = normalizeRoot(root);
  const assetPath = rawFile.startsWith('syzygy/') ? rawFile : `syzygy/${rawFile}`;
  const expectedSha = typeof shard.sha256 === 'string' ? shard.sha256.toLowerCase() : '';
  const cacheKey = `${base}::${domainId}::${assetPath}::${expectedSha}`;

  if (!shardCache.has(cacheKey)) {
    if (typeof globalThis.fetch !== 'function') {
      throw new Error('当前运行环境不支持获取专题辞条。');
    }

    const pending = (async () => {
      const response = await globalThis.fetch(publicAssetUrl(base, assetPath));
      if (!response || !response.ok) {
        throw new Error(`专题辞条分片读取失败 (${response?.status ?? 'network'})`);
      }

      const bytes = await response.arrayBuffer();
      let computedSha = '';
      if (globalThis.crypto?.subtle) {
        const digest = await globalThis.crypto.subtle.digest('SHA-256', bytes);
        computedSha = [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, '0')).join('');
        if (expectedSha && computedSha !== expectedSha) {
          throw new Error(`专题辞条分片校验失败 (${domainId})`);
        }
      }

      const data = decodeUtf8Json(bytes);
      if (!data || typeof data !== 'object' || !Array.isArray(data.entries)) {
        throw new Error('专题辞条分片格式无效。');
      }
      if (data.domain_id && data.domain_id !== domainId) {
        throw new Error('专题辞条分片域标识不匹配。');
      }

      return {
        domain_id: data.domain_id || domainId,
        sha256: computedSha || expectedSha || String(data.sha256 ?? ''),
        count: Number.isFinite(data.count) ? data.count : data.entries.length,
        entries: data.entries,
      };
    })().catch((error) => {
      shardCache.delete(cacheKey);
      throw error;
    });

    shardCache.set(cacheKey, pending);
  }

  return shardCache.get(cacheKey);
}

/**
 * Look up lexicon shard metadata for an L2/L3 hub node ID.
 */
export function getHubLexiconInfo(taxonomy, nodeId) {
  if (!taxonomy || !nodeId || typeof taxonomy !== 'object') return null;

  const domains = Array.isArray(taxonomy.domains) ? taxonomy.domains : [];
  const mapped = taxonomy.hub_to_domain?.[nodeId];
  if (mapped && mapped.domain_id) {
    const domain = domains.find((item) => item && item.id === mapped.domain_id);
    const shard = mapped.shard ?? domain?.lexicon_shard ?? null;
    return {
      domain_id: mapped.domain_id,
      domain_name: mapped.domain_name || domain?.name || mapped.domain_id,
      count: Number.isFinite(mapped.count) ? mapped.count : (shard?.count ?? 0),
      shard,
    };
  }

  for (const domain of domains) {
    if (!domain || !domain.lexicon_shard) continue;
    const shardHubs = Array.isArray(domain.lexicon_shard.hub_ids) ? domain.lexicon_shard.hub_ids : [];
    const groupMatch = Array.isArray(domain.groups)
      && domain.groups.some((group) => Array.isArray(group?.hub_ids) && group.hub_ids.includes(nodeId));
    if (shardHubs.includes(nodeId) || groupMatch) {
      return {
        domain_id: domain.id,
        domain_name: domain.name || domain.id,
        count: Number.isFinite(domain.lexicon_shard.count) ? domain.lexicon_shard.count : 0,
        shard: domain.lexicon_shard,
      };
    }
  }

  return null;
}

/**
 * Case-insensitively filter lexicon entries across term, aliases, summary, region, era, and category.
 */
export function filterLexiconEntries(entries, query = '', category = '') {
  if (!Array.isArray(entries)) return [];
  const cat = normalizeText(category).trim();
  const words = normalizeText(query).trim().split(/\s+/).filter(Boolean);

  return entries.filter((entry) => {
    if (!entry || typeof entry !== 'object') return false;
    if (cat && cat !== 'all' && cat !== '全部') {
      if (normalizeText(entry.category).trim() !== cat) return false;
    }
    if (!words.length) return true;

    const parts = [
      entry.term,
      ...(Array.isArray(entry.aliases) ? entry.aliases : []),
      entry.summary,
      entry.region,
      entry.era,
      entry.category,
    ];
    const haystack = normalizeText(parts.filter(Boolean).join(' '));
    return words.every((word) => haystack.includes(word));
  });
}
