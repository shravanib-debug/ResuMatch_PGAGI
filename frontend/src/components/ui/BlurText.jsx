'use client';

import { useEffect, useState } from 'react';

/**
 * BlurText — Page title entrance animation.
 * Words fade in from blur, staggered.
 */
export default function BlurText({ text, className = '', delay = 0 }) {
  const [visible, setVisible] = useState(false);
  const words = text.split(' ');

  useEffect(() => {
    const timer = setTimeout(() => setVisible(true), delay);
    return () => clearTimeout(timer);
  }, [delay]);

  return (
    <span className={className} aria-label={text}>
      {words.map((word, i) => (
        <span
          key={i}
          style={{
            display: 'inline-block',
            filter: visible ? 'blur(0)' : 'blur(8px)',
            opacity: visible ? 1 : 0,
            transform: visible ? 'translateY(0)' : 'translateY(8px)',
            transition: `all 0.4s cubic-bezier(0.16, 1, 0.3, 1) ${i * 0.06 + 0.1}s`,
            marginRight: '0.3em',
          }}
        >
          {word}
        </span>
      ))}
    </span>
  );
}
