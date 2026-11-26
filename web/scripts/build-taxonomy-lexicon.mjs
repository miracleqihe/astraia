import { createHash } from 'node:crypto';
import { lstat, mkdir, readFile, readdir, unlink, writeFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = fileURLToPath(new URL('../../', import.meta.url));
const digest = (bytes) => createHash('sha256').update(bytes).digest('hex');

function parseArgs(argv) {
  const options = {
    taxonomyPath: resolve(repoRoot, 'reference/thematic_taxonomy.json'),
    lexiconDir: resolve(repoRoot, 'reference/lexicon'),
    graphPath: resolve(repoRoot, 'web/public/data/graph_data.json'),
    outDir: resolve(repoRoot, 'web/public/syzygy'),
    dryRun: false,
    allowMissing: false,
  };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--input' || arg === '--taxonomy') {
      options.taxonomyPath = resolve(argv[++i]);
    } else if (arg === '--lexicon-dir') {
      options.lexiconDir = resolve(argv[++i]);
    } else if (arg === '--graph') {
      options.graphPath = resolve(argv[++i]);
    } else if (arg === '--out-dir' || arg === '--out') {
      options.outDir = resolve(argv[++i]);
    } else if (arg === '--dry-run') {
      options.dryRun = true;
    } else if (arg === '--allow-missing') {
      options.allowMissing = true;
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }
  return options;
}

async function saveIfChanged(path, bytes) {
  let previous;
  try {
    previous = await readFile(path);
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }
  if (!previous || !previous.equals(bytes)) {
    await writeFile(path, bytes);
  }
}

function validateLexiconEntry(entry, fileDomainId, seenIds, validDomainIds) {
  if (!entry || typeof entry !== 'object') {
    throw new Error('Lexicon entry must be an object.');
  }
  for (const key of ['id', 'hub_id', 'term', 'summary', 'primary_sources']) {
    if (!(key in entry)) {
      throw new Error(`Lexicon entry ${entry.id ?? '<unknown>'} is missing required key "${key}".`);
    }
  }
  if (typeof entry.id !== 'string' || !entry.id.trim()) {
    throw new Error('Lexicon entry "id" must be a non-empty string.');
  }
  if (seenIds.has(entry.id)) {
    throw new Error(`Duplicate lexicon entry id: ${entry.id}`);
  }
  seenIds.add(entry.id);

  if (typeof entry.hub_id !== 'string' || !entry.hub_id.trim()) {
    throw new Error(`Lexicon entry ${entry.id} has invalid "hub_id".`);
  }
  if (typeof entry.term !== 'string' || !entry.term.trim()) {
    throw new Error(`Lexicon entry ${entry.id} has invalid "term".`);
  }
  if (typeof entry.summary !== 'string' || !entry.summary.trim()) {
    throw new Error(`Lexicon entry ${entry.id} has invalid "summary".`);
  }
  for (const key of ['case_id', 'knowledge_id', 'knowledge_note']) {
    if (entry[key] != null && (typeof entry[key] !== 'string' || !entry[key].trim())) {
      throw new Error(`Lexicon entry ${entry.id} has invalid "${key}".`);
    }
  }
  if (!Array.isArray(entry.primary_sources) || entry.primary_sources.length === 0) {
    throw new Error(`Lexicon entry ${entry.id} must have a non-empty "primary_sources" array.`);
  }
  let hasHttps = false;
  let hasLocatedPrintSource = false;
  for (const src of entry.primary_sources) {
    if (!src || typeof src !== 'object' || typeof src.citation !== 'string' || !src.citation.trim()) {
      throw new Error(`Lexicon entry ${entry.id} has invalid primary_sources item.`);
    }
    const url = typeof src.url === 'string' ? src.url.trim() : '';
    const locator = typeof src.locator === 'string' ? src.locator.trim() : '';
    if (url && !/^https?:\/\//i.test(url)) {
      throw new Error(`Lexicon entry ${entry.id} has invalid source URL.`);
    }
    if (!url && !locator) {
      throw new Error(`Lexicon entry ${entry.id} needs a page or chapter for an offline source.`);
    }
    if (/^https:\/\//i.test(url)) hasHttps = true;
    if (!url && locator) hasLocatedPrintSource = true;
  }
  if (!hasHttps && !hasLocatedPrintSource) {
    throw new Error(`Lexicon entry ${entry.id} needs an HTTPS source or a located print source.`);
  }

  const domainId = entry.domain_id ?? fileDomainId;
  if (typeof domainId !== 'string' || !validDomainIds.has(domainId)) {
    throw new Error(`Lexicon entry ${entry.id} references unknown domain_id "${domainId}".`);
  }

  return {
    id: entry.id.trim(),
    hub_id: entry.hub_id.trim(),
    term: entry.term.trim(),
    aliases: Array.isArray(entry.aliases) ? entry.aliases.map((a) => String(a)) : [],
    category: typeof entry.category === 'string' ? entry.category.trim() : '',
    region: typeof entry.region === 'string' ? entry.region.trim() : '',
    era: typeof entry.era === 'string' ? entry.era.trim() : '',
    summary: entry.summary.trim(),
    primary_sources: entry.primary_sources.map((src) => ({
      citation: src.citation.trim(),
      url: typeof src.url === 'string' && src.url.trim() ? src.url.trim() : null,
      ...(typeof src.locator === 'string' && src.locator.trim() ? { locator: src.locator.trim() } : {}),
    })),
    ...(entry.secondary_ref != null ? { secondary_ref: String(entry.secondary_ref) } : {}),
    ...(entry.case_id != null ? { case_id: String(entry.case_id).trim() } : {}),
    ...(entry.knowledge_id != null ? { knowledge_id: String(entry.knowledge_id).trim() } : {}),
    ...(entry.knowledge_note != null ? { knowledge_note: String(entry.knowledge_note).trim() } : {}),
  };
}

function normalizeEditorialPreface(preface) {
  if (preface == null) return null;
  if (typeof preface !== 'object' || Array.isArray(preface)) {
    throw new Error('Invalid taxonomy editorial_preface (expected an object).');
  }
  const title = typeof preface.title === 'string' ? preface.title.trim() : '';
  const subtitle = typeof preface.subtitle === 'string' ? preface.subtitle.trim() : '';
  const paragraphs = Array.isArray(preface.paragraphs)
    ? preface.paragraphs.map((item) => String(item ?? '').trim()).filter(Boolean)
    : [];
  const principles = Array.isArray(preface.principles)
    ? preface.principles.map((item, idx) => {
        if (!item || typeof item !== 'object' || Array.isArray(item)) {
          throw new Error(`Invalid editorial_preface.principles[${idx}] (expected an object).`);
        }
        return {
          ...item,
          label: typeof item.label === 'string' ? item.label.trim() : '',
          text: typeof item.text === 'string' ? item.text.trim() : '',
        };
      })
    : [];
  return {
    ...preface,
    title,
    subtitle,
    paragraphs,
    principles,
  };
}

function normalizeEditorialIntro(intro, domainId) {
  if (intro == null) return null;
  if (typeof intro !== 'object' || Array.isArray(intro)) {
    throw new Error(`Invalid editorial_intro on domain ${domainId} (expected an object).`);
  }
  const heading = typeof intro.heading === 'string' ? intro.heading.trim() : '';
  const epigraphThesis = typeof intro.epigraph_thesis === 'string' ? intro.epigraph_thesis.trim() : '';
  const paragraphs = Array.isArray(intro.paragraphs)
    ? intro.paragraphs.map((item) => String(item ?? '').trim()).filter(Boolean)
    : [];
  const lenses = Array.isArray(intro.lenses)
    ? intro.lenses.map((item) => String(item ?? '').trim()).filter(Boolean)
    : [];
  return {
    ...intro,
    heading,
    epigraph_thesis: epigraphThesis,
    paragraphs,
    lenses,
  };
}

function normalizeTaxonomyGroup(group, domainId) {
  if (!group || typeof group !== 'object' || group.chapter_intro == null) return group;
  if (typeof group.chapter_intro !== 'string') {
    throw new Error(`Invalid chapter_intro on ${domainId}/${group.id ?? '<unknown>'} (expected a string).`);
  }
  return {
    ...group,
    chapter_intro: group.chapter_intro.trim(),
  };
}

export async function buildTaxonomyLexicon(options) {
  let taxonomyBytes;
  try {
    taxonomyBytes = await readFile(options.taxonomyPath);
  } catch (error) {
    if (options.allowMissing && error.code === 'ENOENT') {
      console.log(`Taxonomy source missing (${options.taxonomyPath}); skipped due to --allow-missing.`);
      return null;
    }
    throw error;
  }

  const taxonomy = JSON.parse(taxonomyBytes.toString('utf8'));
  if (!taxonomy || typeof taxonomy !== 'object' || !Array.isArray(taxonomy.domains) || taxonomy.domains.length !== 7) {
    throw new Error(`Invalid thematic taxonomy (expected 7 domains): ${options.taxonomyPath}`);
  }

  const domainMap = new Map();
  for (const [idx, domain] of taxonomy.domains.entries()) {
    if (!domain || typeof domain.id !== 'string' || !domain.id.trim() || !domain.name) {
      throw new Error(`Invalid domain at index ${idx}`);
    }
    if (domainMap.has(domain.id)) {
      throw new Error(`Duplicate taxonomy domain id: ${domain.id}`);
    }
    domainMap.set(domain.id, domain);
  }

  const graph = JSON.parse(await readFile(options.graphPath, 'utf8'));
  if (graph.schema_version !== 1 || !Array.isArray(graph.nodes)) {
    throw new Error(`Invalid graph snapshot: ${options.graphPath}`);
  }
  const graphNodeIds = new Set(graph.nodes.map((node) => node.id));
  const graphById = new Map(graph.nodes.map((node) => [node.id, node]));
  let bookById = null;

  let lexiconFiles = [];
  try {
    const entries = await readdir(options.lexiconDir, { withFileTypes: true });
    lexiconFiles = entries
      .filter((item) => item.isFile() && item.name.endsWith('.json'))
      .map((item) => item.name)
      .sort((a, b) => a.localeCompare(b, 'en'));
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }

  const entriesByDomain = new Map([...domainMap.keys()].map((id) => [id, []]));
  const seenIds = new Set();

  for (const filename of lexiconFiles) {
    const filePath = join(options.lexiconDir, filename);
    const payload = JSON.parse(await readFile(filePath, 'utf8'));
    if (!payload || typeof payload !== 'object' || !Array.isArray(payload.entries)) {
      throw new Error(`Invalid lexicon shard source: ${filePath}`);
    }
    const fileDomainId = payload.domain_id;
    for (const rawEntry of payload.entries) {
      const normalized = validateLexiconEntry(rawEntry, fileDomainId, seenIds, new Set(domainMap.keys()));
      if (normalized.case_id) {
        const story = graphById.get(normalized.case_id);
        if (!story || story.z_layer !== 1 || !Number.isFinite(story.spatial?.lat) || !Number.isFinite(story.spatial?.lng)) {
          throw new Error(`Lexicon entry ${normalized.id} has an invalid geographic story reference.`);
        }
      }
      if (normalized.knowledge_id) {
        if (!bookById) {
          const bookPath = options.bookPath ?? resolve(repoRoot, 'web/public/knowledge/data.json');
          const book = JSON.parse(await readFile(bookPath, 'utf8'));
          bookById = new Map((book.entries ?? []).map((item) => [item.id, item]));
        }
        if (!bookById.get(normalized.knowledge_id)?.body?.trim() || !normalized.knowledge_note) {
          throw new Error(`Lexicon entry ${normalized.id} has an invalid thematic knowledge reference.`);
        }
      } else if (normalized.knowledge_note) {
        throw new Error(`Lexicon entry ${normalized.id} has a thematic note without a knowledge reference.`);
      }
      const domainId = rawEntry.domain_id ?? fileDomainId;
      entriesByDomain.get(domainId).push(normalized);
    }
  }

  const shardPayloads = new Map();
  const manifestDomains = {};
  const manifestHubToDomain = {};
  const taxonomyHubToDomain = {};

  for (const domain of taxonomy.domains) {
    const domainEntries = entriesByDomain.get(domain.id) ?? [];
    if (domainEntries.length === 0) continue;

    const shardObj = {
      version: 1,
      domain_id: domain.id,
      title: domain.name,
      entries: domainEntries,
    };
    const shardBytes = Buffer.from(JSON.stringify(shardObj) + '\n', 'utf8');
    const sha256 = digest(shardBytes);
    const sha12 = sha256.slice(0, 12);
    const fileName = `${domain.id}-${sha12}.json`;
    const relativeFile = `lexicon/${fileName}`;

    const categories = [];
    const seenCategories = new Set();
    const hubIds = [];
    const hubCounts = new Map();
    for (const entry of domainEntries) {
      if (entry.category && !seenCategories.has(entry.category)) {
        seenCategories.add(entry.category);
        categories.push(entry.category);
      }
      if (!hubCounts.has(entry.hub_id)) hubIds.push(entry.hub_id);
      hubCounts.set(entry.hub_id, (hubCounts.get(entry.hub_id) ?? 0) + 1);
    }

    const shardRef = {
      file: relativeFile,
      sha256,
      count: domainEntries.length,
      categories,
      hub_ids: hubIds,
    };
    shardPayloads.set(fileName, { domainId: domain.id, bytes: shardBytes, meta: shardRef });
    manifestDomains[domain.id] = {
      file: relativeFile,
      sha256,
      count: domainEntries.length,
      bytes: shardBytes.length,
      categories,
      hub_ids: hubIds,
    };

    for (const [hubId, count] of hubCounts.entries()) {
      manifestHubToDomain[hubId] = {
        domain_id: domain.id,
        domain_name: domain.name,
        count,
      };
      taxonomyHubToDomain[hubId] = {
        domain_id: domain.id,
        domain_name: domain.name,
        count,
        shard: shardRef,
      };
    }
  }

  const manifestObj = {
    version: 1,
    domains: manifestDomains,
    hub_to_domain: manifestHubToDomain,
  };
  const manifestBytes = Buffer.from(JSON.stringify(manifestObj) + '\n', 'utf8');
  const manifestSha256 = digest(manifestBytes);

  const enrichedDomains = taxonomy.domains.map((domain, index) => {
    const groups = (Array.isArray(domain.groups) ? domain.groups : []).map((group) =>
      normalizeTaxonomyGroup(group, domain.id),
    );
    const resolvedNodes = new Set();
    for (const group of groups) {
      for (const id of [...(group.hub_ids ?? []), ...(group.featured_nodes ?? [])]) {
        if (graphNodeIds.has(id)) resolvedNodes.add(id);
      }
    }
    const manifestEntry = manifestDomains[domain.id];
    const lexiconShard = manifestEntry
      ? {
          file: manifestEntry.file,
          sha256: manifestEntry.sha256,
          count: manifestEntry.count,
          categories: manifestEntry.categories,
          hub_ids: manifestEntry.hub_ids,
        }
      : null;
    const editorialIntro = normalizeEditorialIntro(domain.editorial_intro, domain.id);

    return {
      ...domain,
      order: domain.order ?? index + 1,
      ...(editorialIntro ? { editorial_intro: editorialIntro } : {}),
      node_count: resolvedNodes.size,
      lexicon_count: manifestEntry ? manifestEntry.count : 0,
      lexicon_shard: lexiconShard,
      groups,
    };
  });

  const editorialPreface = normalizeEditorialPreface(taxonomy.editorial_preface);
  const taxonomyOut = {
    version: taxonomy.version ?? 1,
    snapshot_id: graph.snapshot_id,
    lexicon_manifest_sha256: manifestSha256,
    ...(taxonomy.bibliography ? { bibliography: taxonomy.bibliography } : {}),
    ...(editorialPreface ? { editorial_preface: editorialPreface } : {}),
    domains: enrichedDomains,
    hub_to_domain: taxonomyHubToDomain,
  };
  const taxonomyBytesOut = Buffer.from(JSON.stringify(taxonomyOut) + '\n', 'utf8');

  if (!options.dryRun) {
    const lexiconOutDir = join(options.outDir, 'lexicon');
    await mkdir(lexiconOutDir, { recursive: true });
    if ((await lstat(lexiconOutDir)).isSymbolicLink()) {
      throw new Error(`Lexicon output directory must not be a symbolic link: ${lexiconOutDir}`);
    }

    const activeFileNames = new Set([...shardPayloads.keys(), 'manifest.json']);
    const domainPrefixes = taxonomy.domains.map((domain) => `${domain.id}-`);
    for (const name of await readdir(lexiconOutDir)) {
      const isShardLike = domainPrefixes.some((prefix) => name.startsWith(prefix)) && name.endsWith('.json');
      if (isShardLike && !activeFileNames.has(name)) {
        const stalePath = join(lexiconOutDir, name);
        if (!(await lstat(stalePath)).isFile()) {
          throw new Error(`Unexpected lexicon path: ${stalePath}`);
        }
        await unlink(stalePath);
      }
    }

    for (const [fileName, item] of shardPayloads.entries()) {
      await saveIfChanged(join(lexiconOutDir, fileName), item.bytes);
    }
    await saveIfChanged(join(lexiconOutDir, 'manifest.json'), manifestBytes);
    await saveIfChanged(join(options.outDir, 'taxonomy.json'), taxonomyBytesOut);
  }

  const totalEntries = seenIds.size;
  const activeShards = Object.keys(manifestDomains).length;
  console.log(
    `${options.dryRun ? '[dry-run] ' : ''}Taxonomy lexicon: ${enrichedDomains.length} domains, `
    + `${activeShards} active shard(s), ${totalEntries} entries, ${Object.keys(taxonomyHubToDomain).length} mapped hubs.`,
  );

  return {
    taxonomy: taxonomyOut,
    manifest: manifestObj,
    manifestSha256,
    totalEntries,
    activeShards,
  };
}

const isMain = process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  await buildTaxonomyLexicon(parseArgs(process.argv.slice(2)));
}
