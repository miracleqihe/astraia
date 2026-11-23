import type { FeatureCollection, LineString, Point } from 'geojson';
import type { ExpressionSpecification, LayerSpecification, Map, StyleSpecification } from 'maplibre-gl';
import { feature } from 'topojson-client';
import type { GeometryCollection, Topology } from 'topojson-specification';
import atlas from 'world-atlas/countries-50m.json';
import overviewPlaces from './overviewPlaces.json';

const COUNTRIES = feature(atlas as unknown as Topology<{ countries: GeometryCollection }>,
  atlas.objects.countries as unknown as GeometryCollection);
const EMPTY = { type: 'FeatureCollection', features: [] } as const;
const MAP_FONTS = ['Noto Sans SC', 'Astraia CJK Supplemental', 'Noto Sans Thai', 'Noto Sans Khmer', 'Noto Sans Lao', 'Inter', 'sans-serif'];
const INK = '#172232';
const WATER = '#172736';
const NAME: ExpressionSpecification = ['coalesce', ['get', 'name:zh-Hans'], ['get', 'name:zh'],
  ['get', 'name:nonlatin'], ['get', 'name_en'], ['get', 'name:latin'], ['get', 'name'], ''];

function graticule(): FeatureCollection<LineString> {
  const features: FeatureCollection<LineString>['features'] = [];
  for (let longitude = -180; longitude < 180; longitude += 15) {
    features.push({ type: 'Feature', properties: {}, geometry: {
      type: 'LineString',
      coordinates: Array.from({ length: 57 }, (_, index) => [longitude, -84 + 3 * index]),
    } });
  }
  for (let latitude = -75; latitude <= 75; latitude += 15) {
    features.push({ type: 'Feature', properties: {}, geometry: {
      type: 'LineString',
      coordinates: Array.from({ length: 121 }, (_, index) => [-180 + 3 * index, latitude]),
    } });
  }
  return { type: 'FeatureCollection', features };
}

// Natural Earth populated places v5.1.2. Display names are translated locally.
const OVERVIEW_CITIES: FeatureCollection<Point> = {
  type: 'FeatureCollection',
  features: overviewPlaces.map(([name, longitude, latitude, rank]) => ({
    type: 'Feature',
    properties: { name, rank },
    geometry: { type: 'Point', coordinates: [Number(longitude), Number(latitude)] },
  })),
};

export function loadOverviewMapFonts(): Promise<unknown> {
  const labels = overviewPlaces.map(([name]) => name).join('') + '0123456789';
  return document.fonts.load('400 14px "Noto Sans SC"', labels).catch(() => {});
}

export function mapStyle(): StyleSpecification {
  return {
    version: 8,
    projection: { type: 'globe' },
    sky: { 'sky-color': '#101722', 'horizon-color': '#101722', 'atmosphere-blend': 0 },
    sources: {
      land: { type: 'geojson', data: COUNTRIES, tolerance: .2 },
      grid: { type: 'geojson', data: graticule() },
      overview: { type: 'geojson', data: OVERVIEW_CITIES },
      context: { type: 'geojson', data: { ...EMPTY, features: [] } },
      records: {
        type: 'geojson', data: { ...EMPTY, features: [] }, cluster: true, clusterRadius: 33, clusterMaxZoom: 13,
        clusterProperties: { records_total: ['+', ['get', 'records']] },
      },
    },
    layers: [
      { id: 'oceans', type: 'background', paint: { 'background-color': WATER } },
      { id: 'land', type: 'fill', source: 'land', paint: { 'fill-color': '#29394a', 'fill-antialias': false } },
      { id: 'coast', type: 'line', source: 'land', paint: {
        'line-color': '#aba391', 'line-opacity': ['interpolate', ['linear'], ['zoom'], 0, .54, 6, .33, 8, .05],
        'line-width': ['interpolate', ['linear'], ['zoom'], 1, .7, 5, 1.1],
      } },
      { id: 'grid', type: 'line', source: 'grid', maxzoom: 6, paint: {
        'line-color': '#EFECE6', 'line-opacity': ['interpolate', ['linear'], ['zoom'], 1, .19, 6, .03], 'line-width': .75,
      } },
      { id: 'overview-cities', type: 'symbol', source: 'overview', minzoom: 2, maxzoom: 6,
        layout: { 'text-field': ['get', 'name'], 'text-font': MAP_FONTS, 'text-size': 11,
          'symbol-sort-key': ['get', 'rank'], 'text-padding': 5, 'text-offset': [0, .45], 'text-anchor': 'top' },
        paint: { 'text-color': '#d4d3ca', 'text-halo-color': INK, 'text-halo-width': 1.1,
          'text-opacity': ['step', ['zoom'], ['case', ['==', ['get', 'rank'], 0], .86, 0], 4, .85] } },
      { id: 'context', type: 'line', source: 'context', maxzoom: 10, paint: {
        'line-color': '#C29D59', 'line-opacity': .72, 'line-width': 1.25, 'line-dasharray': [2, 3.5],
      } },
      { id: 'record-clusters', type: 'circle', source: 'records', filter: ['has', 'point_count'], paint: {
        'circle-color': '#354353', 'circle-opacity': .94,
        'circle-radius': ['step', ['get', 'records_total'], 10, 10, 12, 60, 15, 250, 18],
        'circle-stroke-color': '#C29D59', 'circle-stroke-width': 1.25,
      } },
      { id: 'record-points', type: 'circle', source: 'records', filter: ['!', ['has', 'point_count']], paint: {
        'circle-color': ['case', ['boolean', ['get', 'highlight'], false], '#9bc3b1',
          ['boolean', ['get', 'fiction'], false], '#bd8074',
          ['boolean', ['get', 'precise'], false], '#ecd098', '#6a6255'],
        'circle-radius': ['case', ['>', ['get', 'records'], 1], 9, 4.4],
        'circle-stroke-width': 1.25, 'circle-stroke-color': '#dfc795',
      } },
      { id: 'record-count', type: 'symbol', source: 'records',
        filter: ['any', ['has', 'point_count'], ['>', ['get', 'records'], 1]],
        layout: { 'text-field': ['to-string', ['coalesce', ['get', 'records_total'], ['get', 'records']]],
          'text-font': MAP_FONTS, 'text-size': 10, 'text-allow-overlap': true, 'text-ignore-placement': true },
        paint: { 'text-color': '#f3e6cd' } },
    ],
  };
}

const STREET_SOURCE = 'street-map';
const STREET_LAYERS: LayerSpecification[] = [
  { id: 'street-parks', type: 'fill', source: STREET_SOURCE, 'source-layer': 'park', minzoom: 7,
    paint: { 'fill-color': '#2d413f', 'fill-opacity': .78 } },
  { id: 'street-water', type: 'fill', source: STREET_SOURCE, 'source-layer': 'water', minzoom: 6,
    paint: { 'fill-color': WATER, 'fill-outline-color': '#495f69' } },
  { id: 'street-rivers', type: 'line', source: STREET_SOURCE, 'source-layer': 'waterway', minzoom: 7,
    paint: { 'line-color': '#547883', 'line-opacity': .7, 'line-width': ['interpolate', ['linear'], ['zoom'], 7, .6, 15, 2] } },
  { id: 'street-regions', type: 'line', source: STREET_SOURCE, 'source-layer': 'boundary', minzoom: 6, maxzoom: 11,
    filter: ['all', ['>=', ['get', 'admin_level'], 3], ['<=', ['get', 'admin_level'], 6]],
    paint: { 'line-color': '#8d99a1', 'line-opacity': .35, 'line-dasharray': [3, 3] } },
  { id: 'street-buildings', type: 'fill', source: STREET_SOURCE, 'source-layer': 'building', minzoom: 13,
    paint: { 'fill-color': '#495462', 'fill-outline-color': '#727978', 'fill-opacity': .72 } },
  { id: 'street-minor', type: 'line', source: STREET_SOURCE, 'source-layer': 'transportation', minzoom: 11,
    filter: ['match', ['get', 'class'], ['minor', 'service', 'track', 'path'], true, false],
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': '#79776d', 'line-opacity': .72, 'line-width': ['interpolate', ['linear'], ['zoom'], 11, .45, 17, 2.2] } },
  { id: 'street-major', type: 'line', source: STREET_SOURCE, 'source-layer': 'transportation', minzoom: 7,
    filter: ['match', ['get', 'class'], ['motorway', 'trunk', 'primary', 'secondary', 'tertiary'], true, false],
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': '#c1a679', 'line-opacity': .71, 'line-width': ['interpolate', ['linear'], ['zoom'], 7, .54, 12, 1.25, 17, 4] } },
  { id: 'street-rail', type: 'line', source: STREET_SOURCE, 'source-layer': 'transportation', minzoom: 11,
    filter: ['match', ['get', 'class'], ['rail', 'transit'], true, false],
    paint: { 'line-color': '#a8b9bf', 'line-opacity': .72, 'line-width': 1, 'line-dasharray': [4, 2] } },
  { id: 'street-city-names', type: 'symbol', source: STREET_SOURCE, 'source-layer': 'place', minzoom: 6,
    filter: ['match', ['get', 'class'], ['city', 'town', 'state'], true, false],
    layout: { 'text-field': NAME, 'text-font': MAP_FONTS, 'text-size': 12, 'symbol-sort-key': ['coalesce', ['get', 'rank'], 99],
      'text-padding': 4, 'text-max-width': 9 },
    paint: { 'text-color': '#ebe1cb', 'text-halo-color': INK, 'text-halo-width': 1.25 } },
  { id: 'street-neighborhood-names', type: 'symbol', source: STREET_SOURCE, 'source-layer': 'place', minzoom: 11,
    filter: ['match', ['get', 'class'], ['suburb', 'quarter', 'neighbourhood', 'village'], true, false],
    layout: { 'text-field': NAME, 'text-font': MAP_FONTS, 'text-size': 11, 'text-padding': 2 },
    paint: { 'text-color': '#b5c5cb', 'text-halo-color': INK, 'text-halo-width': 1 } },
  { id: 'street-road-names', type: 'symbol', source: STREET_SOURCE, 'source-layer': 'transportation_name', minzoom: 13,
    filter: ['match', ['get', 'class'], ['trunk', 'primary', 'secondary', 'tertiary', 'minor'], true, false],
    layout: { 'symbol-placement': 'line', 'text-field': NAME, 'text-font': MAP_FONTS,
      'text-size': 10, 'symbol-spacing': 250, 'text-padding': 3, 'text-max-angle': 30 },
    paint: { 'text-color': '#d8cbb0', 'text-halo-color': INK, 'text-halo-width': 1.05 } },
  { id: 'street-landmarks', type: 'symbol', source: STREET_SOURCE, 'source-layer': 'poi', minzoom: 14,
    filter: ['match', ['get', 'class'], ['attraction', 'museum', 'park', 'monument', 'castle', 'place_of_worship'], true, false],
    layout: { 'text-field': NAME, 'text-font': MAP_FONTS, 'text-size': 11, 'text-padding': 5,
      'text-max-width': 9, 'symbol-sort-key': ['coalesce', ['get', 'rank'], 99] },
    paint: { 'text-color': '#d2d8bb', 'text-halo-color': INK, 'text-halo-width': 1.1 } },
];

export function addStreetDetail(map: Map): void {
  if (map.getSource(STREET_SOURCE)) return;
  map.addSource(STREET_SOURCE, {
    type: 'vector', url: 'https://tiles.openfreemap.org/planet', minzoom: 6, maxzoom: 14,
  });
  for (const layer of STREET_LAYERS) map.addLayer(layer, 'context');
}
