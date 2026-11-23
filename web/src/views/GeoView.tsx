import { greatCircle } from '@turf/great-circle';
import { LngLat, Map as GlobeMap, Marker, ScaleControl, type GeoJSONSource, type MapMouseEvent } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useEffect, useMemo, useRef, useState } from 'react';
import type { FeatureCollection, LineString, MultiLineString, Point } from 'geojson';
import { coordinatesOf, isFiction, isModernReading, locationPrecision, mapLabel, READING_LABELS,
  type Coordinates, type GraphIndex, type GraphNode, type ViewSelection } from '../graph';
import { addStreetDetail, loadOverviewMapFonts, mapStyle } from './geoStyle';
import { motionDuration, ViewControls } from './ViewControls';

const DEFAULT_CENTER: Coordinates = [105, 30];
const EAST_ASIA_CENTER: Coordinates = [111, 34];
const MAX_CONTEXT_ARCS = 14;

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

interface HubArc { from: Coordinates; to: Coordinates; hubId: string; name: string; layer: number; type: string }
interface ArcPath extends HubArc { d: string }

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

export default function GeoView({ graph, selection, codeIds, focus, onSelect, onOpenGraph }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<GlobeMap | null>(null);
  const clusterRequest = useRef(0);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState(false);
  const [arcPaths, setArcPaths] = useState<ArcPath[]>([]);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; arc: HubArc } | null>(null);
  const [placeTooltip, setPlaceTooltip] = useState<{ x: number; y: number; label: string; count: number } | null>(null);
  const [placeList, setPlaceList] = useState<PlaceList | null>(null);
  const [tilted, setTilted] = useState(false);
  const [streetLevel, setStreetLevel] = useState(false);
  const selectedId = selection.node?.id ?? null;
  const points = useMemo(() => mappedNodes(graph), [graph]);
  const regionIds = useMemo(() => new Set((graph.adjacency.get(selectedId ?? '') ?? [])
    .filter((link) => link.type === 'ATTESTS_MOTIF' && link.target === selectedId).map((link) => link.source)),
  [graph.adjacency, selectedId]);
  const regionDistribution = regionIds.size > 0;
  const visiblePoints = useMemo(() => regionDistribution ? points.filter(({ node }) => regionIds.has(node.id)) : points,
    [points, regionDistribution, regionIds]);
  const places = useMemo(() => groupPlaces(visiblePoints), [visiblePoints]);
  const context = useMemo(() => visiblePoints.filter(({ node }) => selection.neighbors.has(node.id)), [visiblePoints, selection]);
  const hubArcs = useMemo(() => relatedArcs(graph, selection), [graph, selection]);
  const anchor = useMemo(() => selection.node ? coordinatesOf(selection.node) : null, [selection.node]);
  const viewCenter = useMemo<Coordinates>(() => {
    const [longitude, latitude] = anchor ?? centerOf(context);
    return [longitude, regionDistribution ? Math.max(-36, Math.min(36, latitude)) : latitude];
  }, [anchor, context, regionDistribution]);
  const [regionalOverview] = useState(() => !focus && !!selection.node && isModernReading(selection.node));
  const [initialCenter] = useState(() => regionalOverview ? EAST_ASIA_CENTER : viewCenter);
  const lastFocusedId = useRef(selectedId);
  const lastFocus = useRef<Props['focus']>(null);
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
    map.getSource<GeoJSONSource>('records')?.setData(pointFeatures(places, codeIds));
    return () => { clusterRequest.current++; };
  }, [ready, places, codeIds]);

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
      if (map.isMoving()) return;
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
    if (focus && lastFocus.current !== focus && target && targetCoordinates) {
      lastFocus.current = focus;
      lastFocusedId.current = selectedId;
      clusterRequest.current++;
      setPlaceList(null);
      map.easeTo({ center: targetCoordinates, zoom: zoomForPoint(target), pitch: 0, bearing: 0, duration: motionDuration(740) });
    }
    const source = map.getSource<GeoJSONSource>('context');
    source?.setData(connectPoints(linkAnchor, context, regionDistribution ? context.length : MAX_CONTEXT_ARCS));
    if (lastFocusedId.current !== selectedId) {
      lastFocusedId.current = selectedId;
      if (anchor || context.length) {
        const center = anchor ?? viewCenter;
        const host = hostRef.current;
        const zoom = !anchor && host ? zoomFor(host) : map.getZoom();
        map.easeTo({ center, zoom, pitch: anchor ? map.getPitch() : 0, duration: motionDuration(680) });
      }
    }
  }, [anchor, context, focus, graph.byId, linkAnchor, ready, regionDistribution, selectedId, viewCenter]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    if (!hubArcs.length) {
      setArcPaths([]);
      return;
    }
    let frame = 0;
    const update = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        if (map.getZoom() >= 10) {
          setArcPaths((previous) => previous.length ? [] : previous);
          setTooltip(null);
          return;
        }
        const center = map.getCenter(), radians = Math.PI / 180;
        const visible = ([lon, lat]: Coordinates) => Math.sin(lat * radians) * Math.sin(center.lat * radians)
          + Math.cos(lat * radians) * Math.cos(center.lat * radians) * Math.cos((lon - center.lng) * radians) > 0;
        setArcPaths(hubArcs.flatMap((arc) => {
          if (!visible(arc.from) || !visible(arc.to)) return [];
          const from = map.project(arc.from), to = map.project(arc.to);
          const lift = Math.min(130, Math.hypot(to.x - from.x, to.y - from.y) * .28 + 16);
          return [{ ...arc, d: `M ${from.x} ${from.y} Q ${(from.x + to.x) / 2} ${(from.y + to.y) / 2 - lift} ${to.x} ${to.y}` }];
        }));
      });
    };
    map.on('move', update); map.on('resize', update); update();
    return () => { cancelAnimationFrame(frame); map.off('move', update); map.off('resize', update); };
  }, [ready, hubArcs]);

  function reset() {
    const host = hostRef.current;
    setPlaceList(null);
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
        data-point-count={visiblePoints.length} data-location-count={places.size} />
      {ready && arcPaths.length > 0 && <svg className="geo-arcs" aria-label="共同母题或机制连接">
        {arcPaths.map((arc, index) => <g key={`${arc.hubId}-${index}`}>
          <path className="arc-visible" d={arc.d} data-layer={arc.layer} data-type={arc.type} />
          <path className="arc-hit" d={arc.d} role="button" tabIndex={0} aria-label={`查看共享 L${arc.layer} ${arc.name}`}
            onMouseMove={(event) => { const rect = event.currentTarget.ownerSVGElement?.getBoundingClientRect();
              if (rect) setTooltip({ x: event.clientX - rect.left, y: event.clientY - rect.top, arc }); }}
            onMouseLeave={() => setTooltip(null)} onClick={() => { setTooltip(null); onSelect(arc.hubId); }}
            onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelect(arc.hubId); } }} />
        </g>)}
      </svg>}
      {tooltip && <div className="geo-arc-tooltip" style={{ left: tooltip.x + 12, top: tooltip.y + 12 }}>
        共享 L{tooltip.arc.layer} · {tooltip.arc.name}</div>}
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
                  ? READING_LABELS[node.reading.kind] : locationPrecision(node)}</small>
              </button>
            </li>)}</ul> : <p role="status">当前视野内没有条目。</p>}
          </section>}
          {selection.node && !anchor && (
            <div className="geo-context-note" role="status">
              {regionDistribution ? `母题共现 · ${context.length} 个研究地区`
                : context.length ? `所选节点无坐标 · 显示 ${context.length} 个关联地点` : '所选节点暂无可显示的地点'}
              {!context.length && <button type="button" onClick={onOpenGraph}>在星图查看</button>}
            </div>
          )}
          <div className="scene-footer">
            <span>{places.size} 处标点</span>
            <span className="geo-legend">
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
