/** The Hindsight mark: a forecast fan opening from a saffron "today" point. */
export function Mark({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <rect width="32" height="32" rx="8" fill="#0F1B45" />
      <path d="M16 15 L28 9 L28 22 Z" fill="#8EA2FF" opacity="0.35" />
      <path d="M4 21c4 0 5-6 9-6h3" fill="none" stroke="#F4B23E" strokeWidth="2.4" strokeLinecap="round" />
      <path d="M16 15c4 0 7 1 12 5" fill="none" stroke="#8EA2FF" strokeWidth="2.2" strokeLinecap="round" />
      <circle cx="16" cy="15" r="2.8" fill="#F4B23E" />
    </svg>
  );
}

/** A still of the replay stage for the start page: real sales to a "today" line, a forecast fan opening behind the curtain. Decorative. */
export function HeroStage() {
  const wave = (i: number) => 150 - 34 * Math.sin((i / 7) * 2 * Math.PI + 0.6) - i * 0.25 - 6 * Math.sin(i * 1.7);
  const real = Array.from({ length: 41 }, (_, i) => `${i === 0 ? "M" : "L"}${20 + i * 7.2} ${wave(i).toFixed(1)}`).join("");
  const fan = Array.from({ length: 21 }, (_, k) => ({ x: 20 + (40 + k) * 7.2, y: wave(40 + k) + 2 }));
  const spread = (k: number) => 6 + k * 1.5;
  const band = `M${fan.map((p, k) => `${p.x.toFixed(1)} ${(p.y - spread(k)).toFixed(1)}`).join("L")}L${[...fan].reverse().map((p, k) => `${p.x.toFixed(1)} ${(p.y + spread(20 - k)).toFixed(1)}`).join("L")}Z`;
  const line = fan.map((p, k) => `${k === 0 ? "M" : "L"}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join("");
  const todayX = 20 + 40 * 7.2;
  return (
    <svg className="hero-stage" viewBox="0 0 480 270" aria-hidden="true" focusable="false">
      <rect width="480" height="270" rx="18" fill="#0f1b45" />
      {[70, 120, 170].map((y) => <line key={y} x1="20" x2="460" y1={y} y2={y} stroke="rgba(180,196,255,0.14)" />)}
      <rect x={todayX} y="46" width={460 - todayX} height="150" fill="#0b1438" />
      {Array.from({ length: 12 }, (_, i) => <rect key={i} x={todayX + i * 12} y="46" width="5" height="150" fill="#fff" opacity="0.045" />)}
      <path d={band} fill="rgba(142,162,255,0.28)" stroke="rgba(142,162,255,0.5)" />
      <path d={line} fill="none" stroke="#8ea2ff" strokeWidth="2.4" strokeLinecap="round" />
      <path d={real} fill="none" stroke="#f4b23e" strokeWidth="2.6" strokeLinejoin="round" strokeLinecap="round" />
      <line x1={todayX} x2={todayX} y1="38" y2="196" stroke="#fff" strokeOpacity="0.7" strokeDasharray="3 4" />
      <circle cx={todayX} cy={wave(40)} r="4.6" fill="#f4b23e" stroke="#0f1b45" strokeWidth="2" />
      {Array.from({ length: 41 }, (_, i) => (i % 9 === 4 ? <path key={i} d={`M${20 + i * 7.2 - 2.3} 226l4.6 4.6M${20 + i * 7.2 + 2.3} 226l-4.6 4.6`} stroke="#e0553f" strokeWidth="1.8" strokeLinecap="round" fill="none" /> : <circle key={i} cx={20 + i * 7.2} cy="222" r="2.1" fill="#1e9e86" />))}
    </svg>
  );
}

export function Check({ size = 14 }: { size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M3 8.5l3.2 3.2L13 4.8" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}

export function Cross({ size = 14 }: { size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M4 4l8 8M12 4l-8 8" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" /></svg>;
}
