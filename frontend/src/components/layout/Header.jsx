/**
 * Header — Global header with logo.
 */
export default function Header({ subtitle }) {
  return (
    <header
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        zIndex: 50,
        padding: '20px 32px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}
    >
      <a
        href="/"
        style={{
          fontFamily: 'var(--font-display)',
          fontStyle: 'italic',
          fontSize: '28px',
          color: 'var(--amber-light)',
          textDecoration: 'none',
          letterSpacing: '-0.02em',
        }}
      >
        PGAGI
        {subtitle && (
          <span
            style={{
              fontSize: '13px',
              color: 'var(--text-secondary)',
              marginLeft: '12px',
              fontFamily: 'var(--font-body)',
              fontStyle: 'normal',
              fontWeight: 400,
              letterSpacing: '0',
            }}
          >
            {subtitle}
          </span>
        )}
      </a>
    </header>
  );
}
