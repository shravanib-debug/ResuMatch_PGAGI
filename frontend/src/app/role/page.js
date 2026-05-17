'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Brain, Server, CheckCircle, ArrowRight } from 'lucide-react';
import Grainient from '@/components/ui/Grainient';
import BlurText from '@/components/ui/BlurText';
import Card from '@/components/ui/Card';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Header from '@/components/layout/Header';
import { createSession, uploadResume } from '@/lib/api';

const ROLES = [
  {
    id: 'aiml',
    icon: Brain,
    badge: 'AI / ML Engineer',
    title: 'AI & Machine Learning',
    description: 'Deep learning, neural networks, NLP, computer vision, and modern ML frameworks.',
    topics: ['Supervised Learning', 'Neural Networks', 'RAG Systems', 'Transformers'],
  },
  {
    id: 'datascience',
    icon: Server,
    badge: 'Data Science',
    title: 'Data Science & Analytics',
    description: 'Statistical modelling, data pipelines, feature engineering, and ML deployment.',
    topics: ['Statistical Methods', 'Data Pipelines', 'Model Evaluation', 'Feature Engineering'],
  },
];

export default function RolePage() {
  const router = useRouter();
  const [selectedRole, setSelectedRole] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleContinue = async () => {
    if (!selectedRole) return;
    setLoading(true);

    try {
      const sessionId = localStorage.getItem('sessionId');

      if (sessionId) {
        // Session already exists from upload page — just proceed
        router.push(`/interview/${sessionId}`);
      } else {
        // Fallback: create session (shouldn't normally reach here)
        const session = await createSession(selectedRole);
        localStorage.setItem('sessionId', session.id);
        router.push(`/interview/${session.id}`);
      }
    } catch (err) {
      console.error('Failed to start:', err);
      setLoading(false);
    }
  };

  return (
    <>
      <Grainient />
      <Header />

      <main
        className="animate-fade-in"
        style={{
          minHeight: '100vh',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '0 24px',
        }}
      >
        {/* Label */}
        <span style={{
          fontFamily: 'var(--font-body)',
          fontSize: '11px',
          fontWeight: 500,
          textTransform: 'uppercase',
          letterSpacing: '0.15em',
          color: 'var(--amber-muted)',
          marginBottom: '16px',
        }}>
          Step 2 of 3
        </span>

        {/* Title */}
        <h1 style={{ textAlign: 'center', marginBottom: '16px' }}>
          <BlurText text="Select Your Role" />
        </h1>

        {/* Subtitle */}
        <p style={{
          fontFamily: 'var(--font-body)',
          fontSize: '15px',
          color: 'var(--text-secondary)',
          textAlign: 'center',
          maxWidth: '480px',
          marginBottom: '48px',
          lineHeight: 1.6,
        }}>
          Choose the role you&apos;re applying for. Your interview will be
          tailored to that domain.
        </p>

        {/* Role Cards */}
        <div style={{
          display: 'flex',
          gap: '24px',
          flexWrap: 'wrap',
          justifyContent: 'center',
          marginBottom: '40px',
        }}>
          {ROLES.map((role, idx) => {
            const isSelected = selectedRole === role.id;
            const Icon = role.icon;

            return (
              <Card
                key={role.id}
                hover
                active={isSelected}
                onClick={() => setSelectedRole(role.id)}
                className={`animate-fade-in-delay-${idx + 1}`}
                style={{ width: '340px', position: 'relative' }}
              >
                {/* Checkmark */}
                {isSelected && (
                  <div style={{
                    position: 'absolute',
                    top: '16px',
                    right: '16px',
                    animation: 'fadeInUp 0.2s ease both',
                  }}>
                    <CheckCircle size={20} color="var(--amber-primary)" />
                  </div>
                )}

                {/* Icon */}
                <Icon
                  size={32}
                  color="var(--amber-primary)"
                  style={{ marginBottom: '16px' }}
                />

                {/* Badge */}
                <Badge>{role.badge}</Badge>

                {/* Title */}
                <h3 style={{ marginTop: '16px', marginBottom: '8px' }}>
                  {role.title}
                </h3>

                {/* Description */}
                <p style={{
                  fontSize: '14px',
                  color: 'var(--text-secondary)',
                  lineHeight: 1.6,
                  marginBottom: '16px',
                }}>
                  {role.description}
                </p>

                {/* Topics */}
                <p style={{
                  fontSize: '12px',
                  color: 'var(--text-secondary)',
                }}>
                  {role.topics.join(' · ')}
                </p>
              </Card>
            );
          })}
        </div>

        {/* Continue Button */}
        <div
          className="animate-fade-in-delay-3"
          style={{
            opacity: selectedRole ? 1 : 0,
            transform: selectedRole ? 'translateY(0)' : 'translateY(8px)',
            transition: 'all 0.3s ease',
            pointerEvents: selectedRole ? 'auto' : 'none',
          }}
        >
          <Button
            onClick={handleContinue}
            loading={loading}
            disabled={!selectedRole}
          >
            Begin Interview <ArrowRight size={16} />
          </Button>
        </div>
      </main>
    </>
  );
}
