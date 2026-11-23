// Coarse, reproducible point-in-country comparison; this does not define cultural areas.
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import { feature } from 'topojson-client';

const require = createRequire(import.meta.url);
const atlasPath = require.resolve('world-atlas/countries-110m.json');
const rawAtlas = readFileSync(atlasPath);
const atlas = JSON.parse(rawAtlas);
const countries = feature(atlas, atlas.objects.countries).features;
const points = JSON.parse(readFileSync(0, 'utf8'));
if (!Array.isArray(points)) throw new Error('Expected an array of points.');

function insideRing(ring, [lng, lat]) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [x1, y1] = ring[i];
    const [x2, y2] = ring[j];
    if ((y1 > lat) !== (y2 > lat) && lng < (x2 - x1) * (lat - y1) / (y2 - y1) + x1) inside = !inside;
  }
  return inside;
}

function insideCountry(geometry, point) {
  const polygons = geometry.type === 'Polygon' ? [geometry.coordinates]
    : geometry.type === 'MultiPolygon' ? geometry.coordinates : [];
  return polygons.some(([outer, ...holes]) => insideRing(outer, point)
    && !holes.some((hole) => insideRing(hole, point)));
}

const results = points.map(({ area_id, lat, lng }) => {
  if (!Number.isInteger(area_id) || !Number.isFinite(lat) || !Number.isFinite(lng)) throw new Error('Invalid point.');
  const matching = countries.filter((country) => insideCountry(country.geometry, [lng, lat]));
  return { area_id, lat, lng, countries: matching.map((country) => country.properties.name) };
});
process.stdout.write(JSON.stringify({
  map: 'Natural Earth 1:110m countries via world-atlas',
  map_source: 'https://www.naturalearthdata.com/downloads/110m-cultural-vectors/110m-admin-0-countries/',
  map_sha256: createHash('sha256').update(rawAtlas).digest('hex'),
  limitation: '国界底图只用于粗略对照；空列表表示未落入低分辨率国界多边形，并非文化区边界或采录点。',
  results,
}, null, 2) + '\n');
