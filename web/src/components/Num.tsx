export default function Num({ label, value, onChange, disabled, placeholder }: { label: string; value: string; onChange: (v: string) => void; disabled?: boolean; placeholder?: string }) {
  return (
    <label className="field">
      <span>{label}</span>
      <input type="text" inputMode="decimal" value={value} disabled={disabled} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}
