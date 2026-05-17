/**
 * Badge — Small tag/label component.
 * Matches design PRD spec 3.6.
 */
export default function Badge({ children, className = '' }) {
  return (
    <span
      className={className}
      style={{
        display: 'inline-block',
        background: 'rgba(212, 130, 10, 0.1)',
        border: '1px solid rgba(212, 130, 10, 0.25)',
        color: 'var(--amber-light)',
        fontFamily: 'var(--font-body)',
        fontSize: '11px',
        fontWeight: 500,
        textTransform: 'uppercase',
        letterSpacing: '0.05em',
        padding: '4px 10px',
        borderRadius: '6px',
      }}
    >
      {children}
    </span>
  );
}
