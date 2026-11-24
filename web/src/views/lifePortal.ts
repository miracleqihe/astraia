import type { LifeEntry } from '../life';
import type { lifeGalaxyLayout } from './lifeGalaxyLayout';

/** A portal is offered only for a cross-subject reference present in the book. */
export function createLifePortal(host: HTMLElement, entries: LifeEntry[], layout: ReturnType<typeof lifeGalaxyLayout>, onSelect: (id: string) => void) {
  const byId = new Map(entries.map((entry) => [entry.id, entry]));
  const incoming = new Map<string, string[]>();
  for (const entry of entries) for (const id of entry.links) {
    const list = incoming.get(id); if (list) list.push(entry.id); else incoming.set(id, [entry.id]);
  }
  const button = document.createElement('button'); button.className = 'life-portal'; button.type = 'button'; button.hidden = true;
  let target: LifeEntry | undefined, selected: LifeEntry | undefined;
  button.addEventListener('click', () => { if (target) onSelect(target.id); });
  host.append(button);
  return {
    select(id: string | null) {
      selected = id ? byId.get(id) : undefined;
      target = selected ? [...selected.links, ...(incoming.get(selected.id) ?? [])]
        .map((linked) => byId.get(linked)).find((entry) => entry && entry.subject !== selected!.subject) : undefined;
      button.hidden = !target;
      if (target) { button.textContent = `↯ 跨域跃迁 · ${target.title}`; button.setAttribute('aria-label', `跨域跃迁至 ${target.title}`); }
    },
    position(x: number, y: number, visible = true) {
      button.hidden = !target || !visible;
      if (target && visible) { button.style.left = `${x}px`; button.style.top = `${y}px`; }
    },
    point() { return selected ? layout.locations.get(selected.id) : undefined; },
    dispose() { button.remove(); },
  };
}
