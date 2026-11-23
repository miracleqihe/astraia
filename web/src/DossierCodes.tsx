import { codeKey, type CodeFocus } from './graph';

export interface CodeInteractions {
  counts: ReadonlyMap<string, number>;
  pinned: CodeFocus | null;
  onFocus: (code: CodeFocus | null) => void;
  onPin: (code: CodeFocus) => void;
}

export function DossierCodes({ codes, interaction }: {
  codes: Array<CodeFocus & { label: string }>;
  interaction: CodeInteractions;
}) {
  const { counts, pinned, onFocus, onPin } = interaction;
  return <div className="code-plates" aria-label="按编码反查">
    {codes.map((code) => {
      const key = codeKey(code);
      const count = counts.get(key) ?? 0;
      return <button key={key} type="button" title={`反查 ${code.label} 的 ${count} 份卷宗`}
        aria-label={`反查 ${code.label}，${count} 项`} aria-pressed={pinned !== null && key === codeKey(pinned)}
        onMouseEnter={() => onFocus(code)} onMouseLeave={() => onFocus(null)}
        onFocus={() => onFocus(code)} onBlur={() => onFocus(null)} onClick={() => onPin(code)}>
        <span aria-hidden="true">⌖</span> {code.label} <span className="code-total">({count})</span>
      </button>;
    })}
  </div>;
}
