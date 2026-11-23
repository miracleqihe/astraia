import { MercatorCoordinate, type CustomRenderMethodInput } from 'maplibre-gl';
import type { Coordinates } from '../graph';

const EARTH_RADIUS = 6371008.8;
const RADIANS = Math.PI / 180;
const MERCATOR_LIMIT = 85.05112878;

export interface HubArc { from: Coordinates; to: Coordinates; hubId: string; name: string; layer: number; type: string }
type Vector = [number, number, number];
type ClipPoint = [x: number, y: number, w: number, horizon: number];
interface ArcSample { globe: Vector; flat: MercatorCoordinate; horizonLift: number }
export interface ArcRoute { arc: HubArc; samples: ArcSample[]; dashed: boolean }

function sphere([longitude, latitude]: Coordinates): Vector {
  const lon = longitude * RADIANS, lat = latitude * RADIANS;
  return [Math.sin(lon) * Math.cos(lat), Math.sin(lat), Math.cos(lon) * Math.cos(lat)];
}

function dot(a: Vector, b: Vector): number {
  return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}

export function makeArcRoute(arc: HubArc): ArcRoute | null {
  const from = sphere(arc.from), to = sphere(arc.to);
  const cosine = dot(from, to);
  let tangent = to.map((value, i) => value - from[i] * cosine) as Vector;
  let length = Math.hypot(...tangent);
  const angle = Math.atan2(length, cosine);
  if (angle < 1e-6) return null;
  if (length < 1e-10) {
    tangent = [Math.cos(arc.from[0] * RADIANS), 0, -Math.sin(arc.from[0] * RADIANS)];
    length = 1;
  }
  tangent = tangent.map((value) => value / length) as Vector;
  const lift = Math.min(.085, angle * .10);
  const cycles = Math.min(80, 2 * Math.ceil(angle * 24));
  const samples: ArcSample[] = [];
  let longitude = arc.from[0];
  for (let index = 0; index <= cycles * 2; index++) {
    // Each visible stroke and gap is located at a fixed fraction of the geographic route.
    const t = (Math.floor(index / 2) + (index % 2 ? .68 : 0)) / cycles;
    const cos = Math.cos(t * angle), sin = Math.sin(t * angle);
    const direction = t === 0 ? from : t === 1 ? to :
      from.map((value, i) => value * cos + tangent[i] * sin) as Vector;
    const [x, y, z] = direction;
    const lon = Math.atan2(x, z) / RADIANS;
    longitude = lon + Math.round((longitude - lon) / 360) * 360;
    const latitude = Math.atan2(y, Math.hypot(x, z)) / RADIANS;
    const height = t === 1 ? 0 : lift * Math.sin(Math.PI * t);
    const radius = 1 + height;
    samples.push({
      globe: [x * radius, y * radius, z * radius],
      flat: MercatorCoordinate.fromLngLat([longitude, Math.max(-MERCATOR_LIMIT, Math.min(MERCATOR_LIMIT, latitude))],
        height * EARTH_RADIUS),
      horizonLift: Math.sqrt(radius * radius - 1),
    });
  }
  return { arc, samples, dashed: arc.layer !== 4 && arc.type !== 'EXPLAINED_BY' };
}

function transform(matrix: CustomRenderMethodInput['modelViewProjectionMatrix'], x: number, y: number, z: number): Vector {
  return [
    matrix[0] * x + matrix[4] * y + matrix[8] * z + matrix[12],
    matrix[1] * x + matrix[5] * y + matrix[9] * z + matrix[13],
    matrix[3] * x + matrix[7] * y + matrix[11] * z + matrix[15],
  ];
}

function clipDistances([x, y, w, horizon]: ClipPoint): number[] {
  const edge = w * 1.025;
  return [horizon, w - 1e-6, edge + x, edge - x, edge + y, edge - y];
}

function clipRange(from: number[], to: number[]): [number, number] | null {
  let start = 0, end = 1;
  for (let i = 0; i < from.length; i++) {
    const left = from[i], right = to[i];
    if (left < 0 && right < 0) return null;
    if (left < 0) start = Math.max(start, left / (left - right));
    if (right < 0) end = Math.min(end, left / (left - right));
  }
  return start < end ? [start, end] : null;
}

export function arcProjector(input: CustomRenderMethodInput, width: number, height: number,
  centerLongitude: number, worldCopies: boolean) {
  const { defaultProjectionData, modelViewProjectionMatrix } = input;
  const { clippingPlane: [nx, ny, nz, offset], projectionTransition: globeness, fallbackMatrix } = defaultProjectionData;
  const horizonRange = Math.sqrt(Math.max(0, 1 - offset * offset));
  const depthMix = Math.max(0, (globeness - .2) / .8);
  const centerX = (centerLongitude + 180) / 360;
  const pixel = (x: number, y: number, w: number): [number, number] => [
    Math.round((1 + x / w) * width * 5) / 10, Math.round((1 - y / w) * height * 5) / 10,
  ];

  function project(sample: ArcSample, wrap: number): ClipPoint {
    const [gx, gy, gz] = sample.globe;
    // A point above the surface can still be seen past the surface's tangent plane.
    const horizon = nx * gx + ny * gy + nz * gz + offset + horizonRange * sample.horizonLift;
    if (globeness === 1) return [...transform(modelViewProjectionMatrix, gx, gy, gz), horizon];
    const { x, y, z } = sample.flat;
    const flat = transform(fallbackMatrix, x + wrap, y, z);
    if (globeness === 0) return [...flat, 1];
    const globe = transform(modelViewProjectionMatrix, gx, gy, gz);
    const [px, py, w] = globe.map((value, i) => flat[i] + (value - flat[i]) * globeness);
    return [px, py, w, w - (1 - horizon) * globe[2] * depthMix];
  }

  function pixelBetween(from: ClipPoint, to: ClipPoint, t: number): string {
    return pixel(from[0] + (to[0] - from[0]) * t, from[1] + (to[1] - from[1]) * t,
      from[2] + (to[2] - from[2]) * t).join(' ');
  }

  return ({ samples, dashed }: ArcRoute) => {
    const middle = (samples.length - 1) / 2;
    const wrap = worldCopies || globeness > 0 ? Math.round(centerX - samples[middle].flat.x) : 0;
    let previous = project(samples[0], wrap);
    let clip = clipDistances(previous);
    let continues = false, path = '', strokes = '';
    let anchor: [number, number] | null = null;
    for (let i = 1; i < samples.length; i++) {
      const point = project(samples[i], wrap);
      const nextClip = clipDistances(point);
      const range = clipRange(clip, nextClip);
      if (range) {
        const [start, end] = range;
        const startsPath = !continues || start > 0;
        const drawsDash = dashed && i % 2 === 1;
        const head = startsPath || drawsDash ? pixelBetween(previous, point, start) : '';
        const tail = pixelBetween(previous, point, end);
        path += (startsPath ? `M${head}` : '') + `L${tail}`;
        if (drawsDash) strokes += `M${head}L${tail}`;
      }
      if (i === middle && nextClip.every((value) => value >= 0)) anchor = pixel(point[0], point[1], point[2]);
      continues = range?.[1] === 1;
      previous = point;
      clip = nextClip;
    }
    return { path, strokes: dashed ? strokes : path, anchor };
  };
}
