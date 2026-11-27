/** Phones in portrait or landscape; larger tablets keep their existing layout. */
export function isCompactViewport(): boolean {
  return window.matchMedia('(max-width: 760px), (max-width: 1100px) and (max-height: 500px) and (pointer: coarse)').matches;
}
