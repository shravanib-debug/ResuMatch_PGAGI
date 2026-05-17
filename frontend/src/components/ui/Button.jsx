'use client';

/**
 * Button — Primary and secondary/ghost variants.
 * Matches design PRD spec 3.1 and 3.2.
 */
export default function Button({
  children,
  onClick,
  variant = 'primary',
  disabled = false,
  loading = false,
  className = '',
  type = 'button',
}) {
  const baseStyles = {
    fontFamily: 'var(--font-body)',
    fontSize: '14px',
    fontWeight: 500,
    borderRadius: 'var(--radius-button)',
    padding: '12px 28px',
    transition: 'all 0.2s ease',
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.5 : 1,
    display: 'inline-flex',
    alignItems: 'center',
    gap: '8px',
    position: 'relative',
    overflow: 'hidden',
  };

  const variants = {
    primary: {
      background: 'linear-gradient(135deg, #D4820A, #A86208)',
      color: '#080500',
      border: 'none',
      boxShadow: disabled ? 'none' : 'var(--glow-button)',
    },
    ghost: {
      background: 'transparent',
      color: 'var(--amber-light)',
      border: '1px solid rgba(212,130,10,0.4)',
      boxShadow: 'none',
    },
  };

  return (
    <button
      type={type}
      onClick={disabled || loading ? undefined : onClick}
      disabled={disabled}
      className={className}
      style={{ ...baseStyles, ...variants[variant] }}
      onMouseEnter={(e) => {
        if (disabled) return;
        if (variant === 'primary') {
          e.currentTarget.style.filter = 'brightness(1.1)';
          e.currentTarget.style.boxShadow = '0 0 24px rgba(212,130,10,0.5)';
        } else {
          e.currentTarget.style.borderColor = 'rgba(212,130,10,0.7)';
          e.currentTarget.style.background = 'rgba(212,130,10,0.06)';
        }
      }}
      onMouseLeave={(e) => {
        if (variant === 'primary') {
          e.currentTarget.style.filter = '';
          e.currentTarget.style.boxShadow = disabled ? 'none' : 'var(--glow-button)';
        } else {
          e.currentTarget.style.borderColor = 'rgba(212,130,10,0.4)';
          e.currentTarget.style.background = 'transparent';
        }
      }}
      onMouseDown={(e) => {
        if (!disabled) e.currentTarget.style.transform = 'scale(0.98)';
      }}
      onMouseUp={(e) => {
        e.currentTarget.style.transform = '';
      }}
    >
      {loading && (
        <span
          style={{
            width: 16, height: 16,
            border: '2px solid rgba(8,5,0,0.3)',
            borderTopColor: variant === 'primary' ? '#080500' : 'var(--amber-light)',
            borderRadius: '50%',
            animation: 'spin 0.6s linear infinite',
          }}
        />
      )}
      {children}
      <style jsx>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </button>
  );
}
