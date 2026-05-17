'use client';

/**
 * Grainient — Animated grain + gradient background.
 * Implemented natively (no external dependency) to match the design PRD:
 * deep dark brown-black with slow-moving amber warmth.
 */
export default function Grainient({ opacity = 1 }) {
  return (
    <div className="fixed inset-0 -z-10 overflow-hidden" style={{ opacity }}>
      {/* Base gradient */}
      <div
        className="absolute inset-0"
        style={{
          background: `
            radial-gradient(ellipse at 50% 80%, rgba(212,130,10,0.08) 0%, transparent 70%),
            radial-gradient(ellipse at 20% 20%, rgba(212,130,10,0.04) 0%, transparent 50%),
            var(--bg-base)
          `,
        }}
      />

      {/* Animated warm pulse */}
      <div
        className="absolute inset-0"
        style={{
          background: 'radial-gradient(ellipse at 50% 100%, rgba(212,130,10,0.06) 0%, transparent 60%)',
          animation: 'pulse-glow 8s ease-in-out infinite',
        }}
      />

      {/* Grain overlay */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.3'/%3E%3C/svg%3E")`,
          backgroundRepeat: 'repeat',
          backgroundSize: '128px 128px',
          opacity: 0.35,
          animation: 'grain 4s steps(8) infinite',
          mixBlendMode: 'overlay',
        }}
      />
    </div>
  );
}
