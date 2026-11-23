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

export function Check({ size = 14 }: { size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M3 8.5l3.2 3.2L13 4.8" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}

export function Cross({ size = 14 }: { size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M4 4l8 8M12 4l-8 8" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" /></svg>;
}
