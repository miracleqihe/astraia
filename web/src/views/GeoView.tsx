import { greatCircle } from '@turf/great-circle';
import { LngLat, Map as GlobeMap, Marker, ScaleControl, type GeoJSONSource, type MapMouseEvent } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import type { FeatureCollection, LineString, MultiLineString, Point } from 'geojson';
import { coordinatesOf, geographicCases, isFiction, isModernReading, locationPrecision, mapLabel, readingLabel,
  type Coordinates, type GraphIndex, type GraphNode, type ViewSelection } from '../graph';
import { addStreetDetail, mapStyle } from './geoStyle';
import { loadOverviewMapFonts } from './geoFonts';
import { arcProjector, makeArcRoute, type HubArc } from './geoArcGeometry';
import { motionDuration, ViewControls } from './ViewControls';

const DEFAULT_CENTER: Coordinates = [105, 30];
const EAST_ASIA_CENTER: Coordinates = [111, 34];
const MAX_CONTEXT_ARCS = 14;
const HUB_ARC_LAYER = 'hub-arc-projection';

interface MappedNode { node: GraphNode; coordinates: Coordinates }
interface Place { key: string; coordinates: Coordinates; nodes: GraphNode[] }
interface PlaceList { title: string; nodes: string[] }

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

function placeKey(coordinates: Coordinates): string {
  return coordinates.map((value) => value.toFixed(6)).join(',');
}

function groupPlaces(points: MappedNode[]): Map<string, Place> {
  const groups = new Map<string, Place>();
  for (const { coordinates, node } of points) {
    const key = placeKey(coordinates);
    const place = groups.get(key);
    if (place) place.nodes.push(node);
    else groups.set(key, { key, coordinates, nodes: [node] });
  }
  return groups;
}

function geographicBounds(places: readonly Place[]) {
  const longitudes = places.map(({ coordinates }) => (coordinates[0] + 360) % 360).sort((a, b) => a - b);
  let gap = -1;
  let start = longitudes[0];
  for (let index = 0; index < longitudes.length; index++) {
    const current = longitudes[index];
    const next = longitudes[index + 1] ?? longitudes[0] + 360;
    if (next - current > gap) {
      gap = next - current;
      start = next;
    }
  }
  const west = (start + 180) % 360 - 180;
  const span = 360 - gap;
  const latitudes = places.map(({ coordinates }) => coordinates[1]);
  const south = Math.min(...latitudes), north = Math.max(...latitudes);
  const bounds: [Coordinates, Coordinates] = [[west, south], [west + span, north]];
  return { bounds, wide: span > 125 || north - south > 95 };
}

function frameDistribution(map: GlobeMap, places: readonly Place[]) {
  if (places.length === 1) {
    map.setProjection({ type: 'globe' });
    map.setRenderWorldCopies(false);
    map.easeTo({ center: places[0].coordinates, zoom: 5.2, bearing: 0, pitch: 0, duration: motionDuration(650) });
    return;
  }
  const { bounds, wide } = geographicBounds(places);
  map.setProjection({ type: wide ? 'mercator' : 'globe' });
  map.setRenderWorldCopies(wide);
  const horizontal = Math.min(map.getContainer().clientWidth / 5, 118);
  map.fitBounds(bounds, { padding: { left: horizontal, right: horizontal / 2, top: 105, bottom: 100 },
    bearing: 0, pitch: 0, maxZoom: 6.6, duration: motionDuration(700) });
}

function pointFeatures(places: Map<string, Place>, highlighted: ReadonlySet<string>): FeatureCollection<Point> {
  return { type: 'FeatureCollection', features: [...places.values()].map(({ key, nodes, coordinates }) => ({
    type: 'Feature',
    properties: {
      key, records: nodes.length, highlight: nodes.some((node) => highlighted.has(node.id)),
      precise: nodes.some((node) => node.spatial?.precision === 'exact'),
      fiction: nodes.every(isFiction),
    },
    geometry: { type: 'Point', coordinates },
  })) };
}

function zoomFor(element: HTMLElement): number {
  const diameter = Math.min(element.clientWidth * 0.84, element.clientHeight * 0.75);
  return Math.max(0, Math.min(2.2, Math.log2(diameter * Math.PI / 512)));
}

function zoomForPoint(node: GraphNode): number {
  if (node.spatial?.precision === 'exact') return 15.3;
  if (node.spatial?.precision === 'city') return 10.8;
  return node.spatial?.precision === 'province' ? 6.6 : 4.7;
}

function mapMarker(node: GraphNode, place: Place | undefined, open: (event: MouseEvent) => void): HTMLButtonElement {
  const element = document.createElement('button');
  element.type = 'button';
  element.className = 'atlas-marker';
  element.title = node.title;
  element.setAttribute('aria-label', place && place.nodes.length > 1
    ? `查看${mapLabel(node)}的 ${place.nodes.length} 条资料` : `地图节点 ${node.title}`);
  element.dataset.nodeId = node.id;
  element.dataset.emphasis = 'selected';
  element.dataset.precision = node.spatial?.precision;
  const dot = document.createElement('span');
  dot.className = 'atlas-dot';
  const label = document.createElement('span');
  label.className = 'atlas-marker-label';
  label.textContent = mapLabel(node);
  dot.setAttribute('aria-hidden', 'true');
  label.setAttribute('aria-hidden', 'true');
  element.append(dot, label);
  element.onclick = (event) => {
    event.stopPropagation();
    open(event);
  };
  return element;
}

interface Props {
  graph: GraphIndex;
  selection: ViewSelection;
  codeIds: ReadonlySet<string>;
  focus: { id: string } | null;
  onSelect: (id: string, compare?: boolean) => void;
  onOpenGraph: () => void;
}

function relatedArcs(graph: GraphIndex, selection: ViewSelection): HubArc[] {
  const arcs: HubArc[] = [], seen = new Set<string>();
  for (const origin of [selection.node, selection.compareNode]) {
    if (!origin || origin.z_layer !== 1) continue;
    const from = coordinatesOf(origin);
    if (!from) continue;
    for (const edge of graph.adjacency.get(origin.id) ?? []) {
      const hubId = edge.source === origin.id ? edge.target : edge.source;
      const hub = graph.byId.get(hubId);
      if (!hub || hub.z_layer < 3) continue;
      for (const connection of graph.adjacency.get(hubId) ?? []) {
        const id = connection.source === hubId ? connection.target : connection.source;
        const other = graph.byId.get(id), to = other && coordinatesOf(other);
        if (!other || other.id === origin.id || other.z_layer !== 1 || !to) continue;
        const key = [origin.id, other.id].sort().join('/') + '/' + hubId;
        if (seen.has(key)) continue;
        seen.add(key);
        arcs.push({ from, to, hubId, name: hub.title, layer: hub.z_layer, type: edge.type });
        if (arcs.length >= 30) return arcs;
      }
    }
  }
  return arcs;
}

function arcHubAt(event: MapMouseEvent): string | undefined {
  const target = event.originalEvent.target;
  return target instanceof Element ? target.closest<SVGGElement>('[data-arc-hub]')?.dataset.arcHub : undefined;
}

export default function GeoView({ graph, selection, codeIds, focus, onSelect, onOpenGraph }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<GlobeMap | null>(null);
  const arcsRef = useRef<SVGSVGElement>(null);
  const clusterRequest = useRef(0);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState(false);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; arc: HubArc } | null>(null);
  const [placeTooltip, setPlaceTooltip] = useState<{ x: number; y: number; label: string; count: number } | null>(null);
  const [placeList, setPlaceList] = useState<PlaceList | null>(null);
  const [tilted, setTilted] = useState(false);
  const [streetLevel, setStreetLevel] = useState(false);
  const selectedId = selection.node?.id ?? null;
  const points = useMemo(() => mappedNodes(graph), [graph]);
  const distributionNode = (focus && graph.byId.get(focus.id)) || selection.node;
  const caseIds = useMemo(() => new Set(geographicCases(graph, distributionNode).map((node) => node.id)),
    [graph, distributionNode]);
  const casePoints = useMemo(() => points.filter(({ node }) => caseIds.has(node.id)), [points, caseIds]);
  const casePlaces = useMemo(() => [...groupPlaces(casePoints).values()], [casePoints]);
  const regionIds = useMemo(() => new Set((graph.adjacency.get(selectedId ?? '') ?? [])
    .filter((link) => link.type === 'ATTESTS_MOTIF' && link.target === selectedId).map((link) => link.source)),
  [graph.adjacency, selectedId]);
  const regionDistribution = regionIds.size > 0 && casePlaces.length === 0;
  const visiblePoints = useMemo(() => casePlaces.length ? casePoints
    : regionDistribution ? points.filter(({ node }) => regionIds.has(node.id)) : points,
  [points, casePlaces.length, casePoints, regionDistribution, regionIds]);
  const places = useMemo(() => groupPlaces(visiblePoints), [visiblePoints]);
  const context = useMemo(() => visiblePoints.filter(({ node }) => selection.neighbors.has(node.id)), [visiblePoints, selection]);
  const hubArcs = useMemo<HubArc[]>(() => {
    if (!distributionNode || casePlaces.length < 2) return relatedArcs(graph, selection);
    return casePlaces.slice(1, 31).map((place) => ({
      from: casePlaces[0].coordinates, to: place.coordinates, hubId: distributionNode.id,
      name: distributionNode.title, layer: distributionNode.z_layer, type: 'DISTRIBUTION',
    }));
  }, [graph, selection, casePlaces, distributionNode]);
  const routes = useMemo(() => hubArcs.map(makeArcRoute).filter((route) => route !== null), [hubArcs]);
  const codedPoints = useMemo(() => visiblePoints.filter(({ node }) => codeIds.has(node.id)), [visiblePoints, codeIds]);
  const highlights = useMemo(() => new Set([...codeIds, ...caseIds]), [codeIds, caseIds]);
  const anchor = useMemo(() => selection.node ? coordinatesOf(selection.node) : null, [selection.node]);
  const viewCenter = useMemo<Coordinates>(() => {
    const [longitude, latitude] = anchor ?? centerOf(context);
    return [longitude, regionDistribution ? Math.max(-36, Math.min(36, latitude)) : latitude];
  }, [anchor, context, regionDistribution]);
  const [regionalOverview] = useState(() => !focus && !!selection.node && isModernReading(selection.node));
  const [initialCenter] = useState(() => regionalOverview ? EAST_ASIA_CENTER : viewCenter);
  const lastFocusedId = useRef(selectedId);
  const lastFocus = useRef<Props['focus']>(null);
  const lastFramed = useRef<readonly Place[] | null>(null);
  const linkAnchor = anchor ?? (selection.node?.z_layer === 3 && context.length > 1 ? context[0].coordinates : null);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    let active = true;
    let observer: ResizeObserver | undefined;
    void loadOverviewMapFonts().then(() => {
      if (!active) return;
      try {
        const map = new GlobeMap({
          container: host,
          style: mapStyle(),
          center: initialCenter,
          zoom: zoomFor(host) + (regionalOverview ? 1.3 : 0),
          minZoom: 0,
          maxZoom: 17,
          maxPitch: 60,
          attributionControl: false,
          renderWorldCopies: false,
          fadeDuration: 0,
        });
        mapRef.current = map;
        map.getCanvas().setAttribute('aria-label', '可拖动与缩放的 3D 地球');
        map.addControl(new ScaleControl({ unit: 'metric', maxWidth: 88 }), 'bottom-left');
        map.once('load', () => {
          setReady(true);
          const addDetail = () => {
            if (map.getZoom() < 5.8) return;
            addStreetDetail(map);
            map.off('zoom', addDetail);
          };
          map.on('zoom', addDetail);
          addDetail();
        });
        map.on('pitchend', () => setTilted(map.getPitch() > 15));
        map.on('zoomend', () => setStreetLevel(map.getZoom() >= 10));
        observer = new ResizeObserver(() => map.resize());
        observer.observe(host);
      } catch (reason) {
        console.warn('Unable to initialize the globe', reason);
        setError(true);
      }
    });
    return () => {
      active = false;
      observer?.disconnect();
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, [initialCenter, regionalOverview]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    map.getSource<GeoJSONSource>('records')?.setData(pointFeatures(places, highlights));
    return () => { clusterRequest.current++; };
  }, [ready, places, highlights]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    const markers = [selection.node, selection.compareNode].flatMap((node) => {
      if (!node) return [];
      const coordinates = coordinatesOf(node);
      const place = coordinates ? places.get(placeKey(coordinates)) : undefined;
      if (!coordinates || !place) return [];
      const element = mapMarker(node, place, (event) => {
        if (place.nodes.length > 1 && !event.shiftKey) {
          setPlaceList({ title: mapLabel(node), nodes: place.nodes.map((item) => item.id) });
        } else {
          onSelect(node.id, event.shiftKey);
        }
      });
      element.setAttribute('aria-pressed', 'true');
      return [new Marker({ element, anchor: 'center', opacityWhenCovered: 0 }).setLngLat(coordinates).addTo(map)];
    });
    return () => { for (const marker of markers) marker.remove(); };
  }, [ready, selection.node, selection.compareNode, places, onSelect]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    const hit = (event: MapMouseEvent, tolerance: number) => {
      const { x, y } = event.point;
      return map.queryRenderedFeatures([[x - tolerance, y - tolerance], [x + tolerance, y + tolerance]], {
        layers: ['record-clusters', 'record-points'],
      })[0];
    };
    const click = (event: MapMouseEvent) => {
      const request = ++clusterRequest.current;
      const arcHub = arcHubAt(event);
      if (arcHub) {
        setTooltip(null);
        setPlaceList(null);
        onSelect(arcHub);
        return;
      }
      const feature = hit(event, 8);
      if (!feature) {
        const city = map.queryRenderedFeatures(event.point, { layers: ['overview-cities', 'street-city-names']
          .filter((layer) => map.getLayer(layer)) })[0];
        if (city?.geometry.type === 'Point') {
          map.easeTo({ center: city.geometry.coordinates as Coordinates, zoom: 10.2, duration: motionDuration(520) });
        }
        setPlaceList(null);
        return;
      }
      if (feature.geometry.type !== 'Point') return;
      if (!feature.properties.cluster) {
        const place = places.get(String(feature.properties.key));
        if (!place) return;
        if (place.nodes.length === 1) {
          setPlaceList(null);
          onSelect(place.nodes[0].id, event.originalEvent.shiftKey);
        } else {
          setPlaceList({ title: mapLabel(place.nodes[0]), nodes: place.nodes.map((node) => node.id) });
        }
        return;
      }
      const source = map.getSource<GeoJSONSource>('records');
      if (!source) return;
      const center = feature.geometry.coordinates as Coordinates;
      const clusterId = Number(feature.properties.cluster_id);
      void Promise.all([
        source.getClusterExpansionZoom(clusterId),
        source.getClusterLeaves(clusterId, Number(feature.properties.point_count), 0),
      ]).then(([zoom, leaves]) => {
        if (clusterRequest.current !== request) return;
        setPlaceList({ title: '区域资料', nodes: leaves.flatMap((leaf) => (
          places.get(String(leaf.properties?.key))?.nodes.map((node) => node.id) ?? []
        )) });
        map.easeTo({ center, zoom: Math.min(zoom + .2, 14), duration: motionDuration(480) });
      }).catch(() => {});
    };
    const hover = (event: MapMouseEvent) => {
      if (map.isMoving() || arcHubAt(event)) return;
      const feature = hit(event, 4);
      map.getCanvas().style.cursor = feature ? 'pointer' : '';
      if (!feature) {
        setPlaceTooltip(null);
        return;
      }
      const first = places.get(String(feature.properties.key))?.nodes[0];
      setPlaceTooltip({ x: event.point.x, y: event.point.y, label: first ? mapLabel(first) : '区域资料',
        count: Number(feature.properties.records_total ?? feature.properties.records) });
    };
    function clearTooltip() { setPlaceTooltip(null); map?.getCanvas().style.removeProperty('cursor'); }
    map.on('click', click); map.on('mousemove', hover); map.on('movestart', clearTooltip);
    map.getCanvas().addEventListener('mouseleave', clearTooltip);
    return () => {
      clusterRequest.current++;
      map.off('click', click); map.off('mousemove', hover); map.off('movestart', clearTooltip);
      map.getCanvas().removeEventListener('mouseleave', clearTooltip);
    };
  }, [ready, onSelect, places]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    const target = focus && graph.byId.get(focus.id);
    const targetCoordinates = target ? coordinatesOf(target) : null;
    const source = map.getSource<GeoJSONSource>('context');
    source?.setData(codedPoints.length > 1
      ? connectPoints(codedPoints[0].coordinates, codedPoints.slice(1), MAX_CONTEXT_ARCS)
      : connectPoints(casePlaces.length ? null : linkAnchor, context, regionDistribution ? context.length : MAX_CONTEXT_ARCS));
    if (casePlaces.length) {
      if (lastFramed.current !== casePlaces || lastFocus.current !== focus) {
        lastFramed.current = casePlaces;
        lastFocus.current = focus;
        lastFocusedId.current = selectedId;
        clusterRequest.current++;
        setPlaceList(null);
        frameDistribution(map, casePlaces);
      }
      return;
    }
    if (lastFramed.current) {
      lastFramed.current = null;
      map.setProjection({ type: 'globe' });
      map.setRenderWorldCopies(false);
    }
    if (focus && lastFocus.current !== focus && target && targetCoordinates) {
      lastFocus.current = focus;
      lastFocusedId.current = selectedId;
      clusterRequest.current++;
      setPlaceList(null);
      map.easeTo({ center: targetCoordinates, zoom: zoomForPoint(target), pitch: 0, bearing: 0, duration: motionDuration(740) });
    }
    if (lastFocusedId.current !== selectedId) {
      lastFocusedId.current = selectedId;
      if (anchor || context.length) {
        const center = anchor ?? viewCenter;
        const host = hostRef.current;
        const zoom = !anchor && host ? zoomFor(host) : map.getZoom();
        map.easeTo({ center, zoom, pitch: anchor ? map.getPitch() : 0, duration: motionDuration(680) });
      }
    }
  }, [anchor, casePlaces, codedPoints, context, focus, graph.byId, linkAnchor, ready, regionDistribution, selectedId, viewCenter]);

  useEffect(() => {
    const map = mapRef.current, svg = arcsRef.current;
    setTooltip(null);
    if (!ready || !map || !svg) return;
    const elements = [...svg.querySelectorAll<SVGGElement>('[data-arc-hub]')].map((group) => ({
      group,
      line: group.querySelector<SVGPathElement>('.arc-visible')!,
      hit: group.querySelector<SVGPathElement>('.arc-hit')!,
      anchor: group.querySelector<SVGGElement>('.arc-anchor')!,
    }));
    const clearTooltip = () => setTooltip(null);
    // Update the SVG on the map's own render frame so it follows every camera change.
    map.addLayer({ id: HUB_ARC_LAYER, type: 'custom', render(_gl, input) {
      const opacity = Math.min(1, Math.max(0, (10 - map.getZoom()) / 1.25));
      if (opacity === 0) {
        svg.dataset.visible = 'false';
        return;
      }
      const host = map.getContainer();
      const project = arcProjector(input, host.clientWidth, host.clientHeight,
        map.getCenter().lng, map.getRenderWorldCopies());
      let visible = false;
      for (let i = 0; i < routes.length; i++) {
        const { group, line, hit, anchor } = elements[i];
        const route = project(routes[i]);
        group.style.display = route.path ? '' : 'none';
        if (!route.path) continue;
        visible = true;
        if (line.getAttribute('d') !== route.strokes) line.setAttribute('d', route.strokes);
        if (hit.getAttribute('d') !== route.path) hit.setAttribute('d', route.path);
        anchor.style.display = route.anchor ? '' : 'none';
        if (route.anchor) anchor.setAttribute('transform', `translate(${route.anchor.join(' ')})`);
      }
      svg.style.opacity = String(opacity);
      svg.dataset.visible = String(visible);
    } });
    map.on('movestart', clearTooltip);
    return () => {
      map.off('movestart', clearTooltip);
      if (mapRef.current === map && map.getLayer(HUB_ARC_LAYER)) map.removeLayer(HUB_ARC_LAYER);
    };
  }, [ready, routes]);

  function showArcTooltip(arc: HubArc, element: SVGElement, pointer?: { clientX: number; clientY: number }) {
    const viewport = element.ownerSVGElement?.getBoundingClientRect();
    if (!viewport || mapRef.current?.isMoving()) return;
    if (pointer) {
      setTooltip({ arc, x: pointer.clientX - viewport.left, y: pointer.clientY - viewport.top });
    } else {
      const rect = element.getBoundingClientRect();
      setTooltip({ arc, x: rect.left + rect.width / 2 - viewport.left, y: rect.top + rect.height / 2 - viewport.top });
    }
  }

  function reset() {
    const host = hostRef.current;
    setPlaceList(null);
    if (casePlaces.length && mapRef.current) {
      frameDistribution(mapRef.current, casePlaces);
      return;
    }
    if (host) mapRef.current?.easeTo({ center: regionalOverview ? EAST_ASIA_CENTER : viewCenter,
      zoom: zoomFor(host) + (regionalOverview ? 1.3 : 0),
      bearing: 0, pitch: 0, duration: motionDuration(520) });
  }
  function showVisiblePlaces() {
    if (placeList) { setPlaceList(null); clusterRequest.current++; return; }
    const map = mapRef.current;
    if (!map) return;
    const bounds = map.getBounds();
    const center = map.getCenter();
    const inView = visiblePoints.filter(({ coordinates }) => bounds.contains(coordinates))
      .map(({ node, coordinates }) => ({ id: node.id, distance: center.distanceTo(LngLat.convert(coordinates)) }))
      .sort((left, right) => left.distance - right.distance);
    setPlaceList({ title: '视野内资料', nodes: inView.map(({ id }) => id) });
  }
  const placeNodes = useMemo(() => placeList?.nodes.flatMap((id) => {
    const node = graph.byId.get(id);
    if (!node) return [];
    if (regionDistribution && !regionIds.has(id)) return [];
    return [node];
  }) ?? [], [placeList, graph.byId, regionDistribution, regionIds]);

  return (
    <>
      <div className="scene-viewport geo-viewport" ref={hostRef} data-ready={ready} data-distribution={regionDistribution}
        data-hub-count={casePlaces.length} data-point-count={visiblePoints.length} data-location-count={places.size} />
      {ready && routes.length > 0 && mapRef.current && createPortal(
        <svg className="geo-arcs" ref={arcsRef} data-visible="false" aria-label="共同母题或机制连接">
          {routes.map(({ arc }, index) => <g key={`${arc.hubId}-${index}`} data-arc-hub={arc.hubId}>
            <path className="arc-visible" data-layer={arc.layer} data-type={arc.type} />
            <path className="arc-hit" aria-hidden="true"
              onMouseMove={(event) => showArcTooltip(arc, event.currentTarget, event)}
              onMouseLeave={() => setTooltip(null)} />
            <g className="arc-anchor" role="button" tabIndex={0}
              aria-label={`查看共享 L${arc.layer} ${arc.name}`}
              onMouseEnter={(event) => showArcTooltip(arc, event.currentTarget)} onMouseLeave={() => setTooltip(null)}
              onFocus={(event) => showArcTooltip(arc, event.currentTarget)} onBlur={() => setTooltip(null)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault();
                  setTooltip(null);
                  onSelect(arc.hubId);
                }
              }}>
              <rect x="-8" y="-8" width="16" height="16" className="arc-anchor-hit" />
              <path d="M 0 -4 L 4 0 L 0 4 L -4 0 Z" className="arc-anchor-glyph" />
            </g>
          </g>)}
        </svg>, mapRef.current.getCanvasContainer())}
      {tooltip && <div className="geo-arc-tooltip" role="tooltip" style={{ left: Math.max(14, Math.min(tooltip.x + 12,
        (hostRef.current?.clientWidth ?? 300) - 248)), top: tooltip.y + 12 }}>
        <strong>共享枢纽 · L{tooltip.arc.layer}</strong><span>{tooltip.arc.name}</span><small>点击调阅卷宗</small></div>}
      {placeTooltip && !tooltip && <div className="geo-arc-tooltip" role="tooltip"
        style={{ left: Math.min(placeTooltip.x + 12, (hostRef.current?.clientWidth ?? 300) - 145), top: placeTooltip.y + 12 }}>
        {placeTooltip.label}{placeTooltip.count > 1 && ` · ${placeTooltip.count} 条`}</div>}
      {!ready && !error && <div className="stage-message" role="status">正在加载本地底图…</div>}
      {error && <div className="stage-message" role="alert">无法启动 3D 地图。请在支持 WebGL 的浏览器中打开。</div>}
      {ready && !error && (
        <>
          <ViewControls onReset={reset} onZoom={(direction) => {
            const map = mapRef.current;
            if (map) map.zoomTo(map.getZoom() + direction * 0.62, { duration: motionDuration(310) });
          }} onTilt={() => mapRef.current?.easeTo({ pitch: tilted ? 0 : 45, duration: motionDuration(390) })} tilted={tilted} />
          <button type="button" className="geo-list-toggle" aria-expanded={!!placeList}
            onClick={showVisiblePlaces}>此处条目</button>
          {placeList && <section className="geo-place-list" aria-label={placeList.title}>
            <header><h2>{placeList.title} <span>{placeNodes.length}</span></h2>
              <button type="button" aria-label="关闭地点列表" onClick={() => { setPlaceList(null); clusterRequest.current++; }}>×</button></header>
            {placeNodes.length ? <ul>{placeNodes.map((node) => <li key={node.id}>
              <button type="button" aria-current={node.id === selectedId ? 'true' : undefined}
                onClick={(event) => onSelect(node.id, event.shiftKey)}>
                <strong>{node.title}</strong>
                <small>{mapLabel(node)} · {node.reading && isModernReading(node)
                  ? readingLabel(node) : locationPrecision(node)}</small>
              </button>
            </li>)}</ul> : <p role="status">当前视野内没有条目。</p>}
          </section>}
          {selection.node && !anchor && (
            <div className="geo-context-note" role="status">
              {casePlaces.length ? `枢纽辐射分布 · ${casePlaces.length} 个实景锚点`
                : regionDistribution ? `母题共现 · ${context.length} 个研究地区`
                : context.length ? `关联地点 · ${context.length} 处` : '暂无登记地点'}
              {!context.length && !casePlaces.length && <button type="button" onClick={onOpenGraph}>在星图查看</button>}
            </div>
          )}
          <div className="scene-footer">
            <span>{places.size} 处标点</span>
            <span className="geo-legend">
              {routes.length > 0 && <span className="arc-legend"><b aria-hidden="true">◇</b> 点击弧线锚标看枢纽</span>}
              {!streetLevel && linkAnchor && context.length > 1 && <span><i />{regionDistribution ? '研究地区共现'
                : context.length > MAX_CONTEXT_ARCS + 1 ? '关联地点（部分）' : '关联地点'}</span>}
              <span className="geo-attribution">
                <a href="https://www.naturalearthdata.com/" target="_blank" rel="noopener noreferrer">Natural Earth</a>
                <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">© OpenStreetMap</a>
                <a href="https://www.openmaptiles.org/" target="_blank" rel="noopener noreferrer">© OpenMapTiles</a>
              </span>
            </span>
          </div>
        </>
      )}
    </>
  );
}
