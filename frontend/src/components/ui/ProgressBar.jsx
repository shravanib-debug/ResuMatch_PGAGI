/**
 * ProgressBar — Thin amber progress indicator.
 * Matches design PRD spec 3.5.
 */
export default function ProgressBar({ current, total, showLabel = true }) {
  const pct = total > 0 ? (current / total) * 100 : 0;

  return (
    <div className="w-full">
      {showLabel && (
        <div
          style={{
            fontFamily: 'var(--font-body)',
            fontSize: '12px',
            color: 'var(--text-secondary)',
            marginBottom: '8px',
          }}
        >
          Question {current} of {total}
        </div>
      )}
      <div
        style={{
          width: '100%',
          height: '3px',
          background: 'rgba(212, 130, 10, 0.1)',
          borderRadius: '999px',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: '100%',
            background: 'linear-gradient(90deg, #D4820A, #F0A832)',
            borderRadius: '999px',
            transition: 'width 0.6s ease-out',
          }}
        />
      </div>
    </div>
  );
}
