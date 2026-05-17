/**
 * Card — Glass card with amber border glow.
 * Matches design PRD spec 3.4.
 */
export default function Card({ children, className = '', hover = false, active = false, onClick }) {
  return (
    <div
      className={`relative ${className}`}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      style={{
        background: 'rgba(17, 12, 2, 0.85)',
        border: `1px solid ${active ? 'rgba(212,130,10,0.6)' : 'rgba(212,130,10,0.12)'}`,
        borderRadius: 'var(--radius-card)',
        backdropFilter: 'blur(12px)',
        padding: '32px',
        boxShadow: active
          ? '0 0 0 1px rgba(212,130,10,0.3), 0 0 24px rgba(212,130,10,0.15), 0 8px 32px rgba(0,0,0,0.5)'
          : 'var(--shadow-card)',
        transition: 'all 0.2s ease',
        cursor: onClick ? 'pointer' : 'default',
        ...(hover && !active ? {} : {}),
      }}
      onMouseEnter={(e) => {
        if (hover && !active) {
          e.currentTarget.style.borderColor = 'rgba(212,130,10,0.3)';
          e.currentTarget.style.transform = 'translateY(-2px)';
        }
      }}
      onMouseLeave={(e) => {
        if (hover && !active) {
          e.currentTarget.style.borderColor = 'rgba(212,130,10,0.12)';
          e.currentTarget.style.transform = 'translateY(0)';
        }
      }}
    >
      {active && (
        <div
          className="absolute inset-0 -z-10 rounded-[var(--radius-card)]"
          style={{
            background: 'radial-gradient(ellipse at 50% 50%, rgba(212,130,10,0.08) 0%, transparent 70%)',
          }}
        />
      )}
      {children}
    </div>
  );
}
