import { greatCircle } from '@turf/great-circle';
import { Map as GlobeMap, Marker, type GeoJSONSource, type StyleSpecification } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useEffect, useMemo, useRef, useState } from 'react';
import { feature } from 'topojson-client';
import type { GeometryCollection, Topology } from 'topojson-specification';
import type { FeatureCollection, LineString, MultiLineString, Point } from 'geojson';
import atlas from 'world-atlas/countries-110m.json';
import { coordinatesOf, nodeColor, type Coordinates, type GraphIndex, type GraphNode, type ViewSelection } from '../graph';
import { motionDuration, ViewControls } from './ViewControls';

const DEFAULT_CENTER: Coordinates = [-27, 26];
const MAX_CONTEXT_ARCS = 14;
const COUNTRIES = feature(atlas as unknown as Topology<{ countries: GeometryCollection }>,
  atlas.objects.countries as unknown as GeometryCollection);

function graticule(): FeatureCollection<LineString> {
  const features: FeatureCollection<LineString>['features'] = [];
  for (let longitude = -180; longitude < 180; longitude += 30) {
    features.push({ type: 'Feature', properties: {}, geometry: {
      type: 'LineString',
      coordinates: Array.from({ length: 57 }, (_, index) => [longitude, -84 + 3 * index]),
    } });
  }
  for (let latitude = -60; latitude <= 60; latitude += 30) {
    features.push({ type: 'Feature', properties: {}, geometry: {
      type: 'LineString',
      coordinates: Array.from({ length: 121 }, (_, index) => [-180 + 3 * index, latitude]),
    } });
  }
  return { type: 'FeatureCollection', features };
}

function mapStyle(): StyleSpecification {
  return {
    version: 8,
    projection: { type: 'globe' },
    sky: {
      'sky-color': '#101722',
      'horizon-color': '#101722',
      'atmosphere-blend': 0,
    },
    sources: {
      land: { type: 'geojson', data: COUNTRIES },
      grid: { type: 'geojson', data: graticule() },
      context: { type: 'geojson', data: { type: 'FeatureCollection', features: [] } },
      records: { type: 'geojson', data: { type: 'FeatureCollection', features: [] }, cluster: true, clusterRadius: 34, clusterMaxZoom: 8 },
    },
    layers: [
      { id: 'oceans', type: 'background', paint: { 'background-color': '#162231' } },
      { id: 'land', type: 'fill', source: 'land', paint: { 'fill-color': '#253346', 'fill-outline-color': '#706e69' } },
      { id: 'grid', type: 'line', source: 'grid', paint: { 'line-color': '#EFECE6', 'line-opacity': 0.12, 'line-width': 0.75 } },
      { id: 'context', type: 'line', source: 'context', paint: {
        'line-color': '#C29D59', 'line-opacity': 0.82, 'line-width': 1.25, 'line-dasharray': [2, 3.5],
      } },
      { id: 'record-clusters', type: 'circle', source: 'records', filter: ['has', 'point_count'], paint: {
        'circle-color': '#C29D59', 'circle-opacity': 0.72,
        'circle-radius': ['step', ['get', 'point_count'], 8, 25, 11, 100, 15],
        'circle-stroke-color': '#EFECE6', 'circle-stroke-width': 1,
      } },
      { id: 'record-points', type: 'circle', source: 'records', filter: ['!', ['has', 'point_count']], paint: {
        'circle-color': '#C29D59', 'circle-opacity': 0.82, 'circle-radius': 4,
        'circle-stroke-width': 1, 'circle-stroke-color': '#101722',
      } },
    ],
  };
}

interface MappedNode { node: GraphNode; coordinates: Coordinates }

function mappedNodes(graph: GraphIndex): MappedNode[] {
  return graph.nodes.flatMap((node) => {
    const coordinates = coordinatesOf(node);
    return coordinates ? [{ node, coordinates }] : [];
  });
}

function centerOf(points: readonly MappedNode[]): Coordinates {
  if (points.length === 0) return DEFAULT_CENTER;
  if (points.length === 1) return points[0].coordinates;
  let x = 0;
  let y = 0;
  let z = 0;
  const radians = Math.PI / 180;
  for (const { coordinates: [longitude, latitude] } of points) {
    x += Math.cos(latitude * radians) * Math.cos(longitude * radians);
    y += Math.cos(latitude * radians) * Math.sin(longitude * radians);
    z += Math.sin(latitude * radians);
  }
  if (Math.hypot(x, y, z) < 0.001) return points[0].coordinates;
  return [Math.atan2(y, x) / radians, Math.atan2(z, Math.hypot(x, y)) / radians];
}

function connectPoints(anchor: Coordinates | null, points: MappedNode[], maxArcs: number): FeatureCollection<LineString | MultiLineString> {
  const features: FeatureCollection<LineString | MultiLineString>['features'] = [];
  const seen = new Set<string>();
  if (anchor) {
    for (const { coordinates } of points) {
      const deltaLongitude = Math.abs((anchor[0] - coordinates[0] + 540) % 360 - 180);
      const samePoint = deltaLongitude === 0 && anchor[1] === coordinates[1];
      const oppositePoint = Math.abs(deltaLongitude - 180) < 0.00001 && Math.abs(anchor[1] + coordinates[1]) < 0.00001;
      if (samePoint || oppositePoint) continue;
      const key = coordinates.join(',');
      if (seen.has(key)) continue;
      seen.add(key);
      features.push(greatCircle(anchor, coordinates, { npoints: 48 }));
      if (features.length === maxArcs) break;
    }
  }
  return { type: 'FeatureCollection', features };
}

function pointFeatures(points: MappedNode[]): FeatureCollection<Point> {
  return { type: 'FeatureCollection', features: points.map(({ node, coordinates }) => ({
    type: 'Feature', properties: { nodeId: node.id }, geometry: { type: 'Point', coordinates },
  })) };
}

function zoomFor(element: HTMLElement): number {
  const diameter = Math.min(element.clientWidth * 0.84, element.clientHeight * 0.75);
  return Math.max(0, Math.min(2.2, Math.log2(diameter * Math.PI / 512)));
}

function mapMarker(node: GraphNode, onSelect: (id: string) => void): HTMLButtonElement {
  const element = document.createElement('button');
  element.type = 'button';
  element.className = 'atlas-marker';
  element.setAttribute('aria-label', `地图节点 ${node.title}`);
  element.dataset.nodeId = node.id;
  element.style.setProperty('--node-color', nodeColor(node));
  const dot = document.createElement('span');
  dot.className = 'atlas-dot';
  const label = document.createElement('span');
  label.className = 'atlas-marker-label';
  label.textContent = node.spatial?.location_name.replace(/（[^）]*）/g, '') ?? node.title;
  dot.setAttribute('aria-hidden', 'true');
  label.setAttribute('aria-hidden', 'true');
  element.append(dot, label);
  element.onclick = (event) => {
    event.stopPropagation();
    onSelect(node.id);
  };
  return element;
}

interface Props {
  graph: GraphIndex;
  selection: ViewSelection;
  onSelect: (id: string) => void;
  onOpenGraph: () => void;
}

export default function GeoView({ graph, selection, onSelect, onOpenGraph }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<GlobeMap | null>(null);
  const markerRef = useRef(new Map<string, Marker>());
  const [ready, setReady] = useState(false);
  const [error, setError] = useState(false);
  const selectedId = selection.node?.id ?? null;
  const points = useMemo(() => mappedNodes(graph), [graph]);
  const regionIds = useMemo(() => new Set((graph.adjacency.get(selectedId ?? '') ?? [])
    .filter((link) => link.type === 'ATTESTS_MOTIF' && link.target === selectedId).map((link) => link.source)),
  [graph.adjacency, selectedId]);
  const regionDistribution = regionIds.size > 0;
  const visiblePoints = useMemo(() => regionDistribution ? points.filter(({ node }) => regionIds.has(node.id)) : points,
    [points, regionDistribution, regionIds]);
  const context = useMemo(() => visiblePoints.filter(({ node }) => selection.neighbors.has(node.id)), [visiblePoints, selection]);
  const viewCenter = useMemo<Coordinates>(() => {
    const [longitude, latitude] = centerOf(context);
    return [longitude, regionDistribution ? Math.max(-36, Math.min(36, latitude)) : latitude];
  }, [context, regionDistribution]);
  const clustered = visiblePoints.length > 160;
  const [initialCenter] = useState(viewCenter);
  const lastFocusedId = useRef(selectedId);
  const anchor = useMemo(() => selection.node ? coordinatesOf(selection.node) : null, [selection.node]);
  const linkAnchor = anchor ?? (selection.node?.z_layer === 3 && context.length > 1 ? context[0].coordinates : null);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    let map: GlobeMap;
    try {
      map = new GlobeMap({
        container: host,
        style: mapStyle(),
        center: initialCenter,
        zoom: zoomFor(host),
        minZoom: 0,
        maxZoom: 15,
        maxPitch: 60,
        attributionControl: false,
        renderWorldCopies: false,
        fadeDuration: 0,
      });
    } catch (reason) {
      console.warn('Unable to initialize the globe', reason);
      setError(true);
      return;
    }
    mapRef.current = map;
    map.getCanvas().setAttribute('aria-label', '可拖动与缩放的 3D 地球');
    map.once('load', () => setReady(true));
    const observer = new ResizeObserver(() => map.resize());
    observer.observe(host);
    return () => {
      observer.disconnect();
      map.remove();
      mapRef.current = null;
    };
  }, [initialCenter]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    const markers = markerRef.current;
    const pins = clustered ? visiblePoints.filter(({ node }) => node.id === selectedId) : visiblePoints;
    const records = map.getSource<GeoJSONSource>('records');
    records?.setData(pointFeatures(clustered ? visiblePoints : []));
    for (const { node, coordinates } of pins) {
      const element = mapMarker(node, onSelect);
      const marker = new Marker({ element, anchor: 'center', opacityWhenCovered: 0 })
        .setLngLat(coordinates).addTo(map);
      markers.set(node.id, marker);
    }
    return () => {
      for (const marker of markers.values()) marker.remove();
      markers.clear();
    };
  }, [clustered, onSelect, ready, selectedId, visiblePoints]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map || !clustered) return;
    const pointClick = map.on('click', 'record-points', (event) => {
      const id = event.features?.[0]?.properties.nodeId;
      if (typeof id === 'string') onSelect(id);
    });
    const clusterClick = map.on('click', 'record-clusters', (event) => {
      const feature = event.features?.[0];
      if (feature?.geometry.type !== 'Point') return;
      const center = feature.geometry.coordinates.slice(0, 2) as Coordinates;
      const clusterId = Number(feature.properties.cluster_id);
      void map.getSource<GeoJSONSource>('records')?.getClusterExpansionZoom(clusterId)
        .then((zoom) => map.easeTo({ center, zoom, duration: motionDuration(400) })).catch(() => {});
    });
    return () => { pointClick.unsubscribe(); clusterClick.unsubscribe(); };
  }, [clustered, onSelect, ready]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    for (const [id, marker] of markerRef.current) {
      const element = marker.getElement();
      const related = selection.neighbors.has(id);
      element.dataset.emphasis = id === selectedId ? 'selected' : related ? 'related' : 'normal';
      element.setAttribute('aria-pressed', String(id === selectedId));
    }
    const source = map.getSource<GeoJSONSource>('context');
    source?.setData(connectPoints(linkAnchor, context, regionDistribution ? context.length : MAX_CONTEXT_ARCS));
    if (lastFocusedId.current !== selectedId) {
      lastFocusedId.current = selectedId;
      if (context.length) {
        const center = anchor ?? viewCenter;
        const host = hostRef.current;
        const zoom = !anchor && host ? zoomFor(host) : map.getZoom();
        map.easeTo({ center, zoom, pitch: anchor ? map.getPitch() : 0, duration: motionDuration(680) });
      }
    }
  }, [anchor, context, linkAnchor, ready, regionDistribution, selectedId, selection, viewCenter]);

  function reset() {
    const host = hostRef.current;
    if (host) mapRef.current?.easeTo({ center: viewCenter, zoom: zoomFor(host),
      bearing: 0, pitch: 0, duration: motionDuration(520) });
  }

  return (
    <>
      <div className="scene-viewport geo-viewport" ref={hostRef} data-ready={ready} data-distribution={regionDistribution} />
      {!ready && !error && <div className="stage-message" role="status">正在加载本地底图…</div>}
      {error && <div className="stage-message" role="alert">无法启动 3D 地图。请在支持 WebGL 的浏览器中打开。</div>}
      {ready && !error && (
        <>
          <ViewControls onReset={reset} onZoom={(direction) => {
            const map = mapRef.current;
            if (map) map.zoomTo(map.getZoom() + direction * 0.62, { duration: motionDuration(310) });
          }} />
          {selection.node && !anchor && (
            <div className="geo-context-note" role="status">
              {regionDistribution ? `母题共现 · ${context.length} 个研究地区`
                : context.length ? `所选节点无坐标 · 显示 ${context.length} 个关联地点` : '所选节点暂无可显示的地点'}
              {!context.length && <button type="button" onClick={onOpenGraph}>在星图查看</button>}
            </div>
          )}
          <div className="scene-footer">
            <span>拖动旋转 · 滚轮缩放</span>
            <span className="geo-legend">
              {linkAnchor && context.length > 1 && <span><i />{regionDistribution ? '研究地区共现'
                : context.length > MAX_CONTEXT_ARCS + 1 ? '两跳内关联（部分）' : '两跳内关联'}</span>}
              <span>底图 Natural Earth</span>
            </span>
          </div>
        </>
      )}
    </>
  );
}
