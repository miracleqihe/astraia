import { LIFE_DIMENSIONS, type LifeDimension } from './lifeDimensions';

interface Props { value: LifeDimension; onChange: (value: LifeDimension) => void; }
export default function LifeResonance({ value, onChange }: Props) {
  return <section className="life-resonance" aria-label="格物认知谐振器">
    <div className="life-resonance-label"><span>✦</span><small>RESONANCE</small><strong>观测棱镜</strong></div>
    <div className="life-resonance-options">{LIFE_DIMENSIONS.map((item) => <button key={item.id} type="button"
      aria-pressed={value === item.id} onClick={() => onChange(item.id)}>{item.title}</button>)}</div>
  </section>;
}
