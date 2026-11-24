export interface LifeDrawing {
  update: (selected: string | null, subject: string | null, highlights: readonly string[]) => void;
  reset: () => void;
  dispose: () => void;
}

export interface LifeHover {
  title: string;
  x: number;
  y: number;
}
