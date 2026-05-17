'use client';

import { useState, useEffect, use } from 'react';
import { useRouter } from 'next/navigation';
import { CheckCircle, AlertCircle, BookOpen, ArrowRight, Sparkles } from 'lucide-react';
import Grainient from '@/components/ui/Grainient';
import BlurText from '@/components/ui/BlurText';
import Card from '@/components/ui/Card';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Header from '@/components/layout/Header';
import { getSummary, getSession } from '@/lib/api';

export default function SummaryPage({ params }) {
  const { sessionId } = use(params);
  const router = useRouter();

  const [summary, setSummary] = useState(null);
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    async function load() {
      try {
        const [sum, sess] = await Promise.all([
          getSummary(sessionId),
          getSession(sessionId),
        ]);
        setSummary(sum);
        setSession(sess);
      } catch (err) {
        setError(err.message || 'Failed to load summary');
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [sessionId]);

  if (loading) {
    return (
      <>
        <Grainient />
        <Header subtitle="Interview Complete" />
        <main style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}>
          <Card style={{ textAlign: 'center', padding: '64px 48px', maxWidth: '480px' }}>
            <div style={{
              width: 48, height: 48,
              borderRadius: '50%',
              border: '3px solid rgba(212,130,10,0.2)',
              borderTopColor: 'var(--amber-primary)',
              animation: 'spin 0.8s linear infinite',
              margin: '0 auto 24px',
            }} />
            <h2 style={{ marginBottom: '16px' }}>Loading Your Report</h2>
            <p style={{ fontSize: '15px', color: 'var(--text-secondary)' }}>
              Analysing your responses...
            </p>
            <style jsx>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
          </Card>
        </main>
      </>
    );
  }

  if (error) {
    return (
      <>
        <Grainient />
        <Header />
        <main style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}>
          <Card style={{ textAlign: 'center', padding: '48px', maxWidth: '480px' }}>
            <p style={{ color: 'var(--error)', marginBottom: '16px' }}>{error}</p>
            <Button onClick={() => router.push('/')}>Return Home</Button>
          </Card>
        </main>
      </>
    );
  }

  const perQuestion = summary?.per_question || [];
  const strengths = summary?.strengths || [];
  const gaps = summary?.gaps || [];
  const recommendations = summary?.recommendations || [];
  const score = summary?.overall_score || 0;
  const parsedResume = session?.parsed_resume;

  return (
    <>
      <Grainient />
      <Header subtitle="Interview Complete" />

      <main style={{
        maxWidth: '800px',
        margin: '0 auto',
        padding: '96px 24px 64px',
      }}>
        {/* Hero */}
        <div className="animate-fade-in" style={{ marginBottom: '48px' }}>
          <span style={{
            fontFamily: 'var(--font-body)',
            fontSize: '11px',
            fontWeight: 500,
            textTransform: 'uppercase',
            letterSpacing: '0.15em',
            color: 'var(--amber-muted)',
            marginBottom: '16px',
            display: 'block',
          }}>
            Your Evaluation Report
          </span>

          <h1 style={{ marginBottom: '16px' }}>
            <BlurText text="Interview Summary" />
          </h1>

          <div style={{ display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
            <Badge>{session?.role === 'aiml' ? 'AI / ML Engineer' : 'Data Science'}</Badge>
            <Badge>{parsedResume?.experience_level || 'Mid'} Level</Badge>
            <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
              {perQuestion.length} Questions
            </span>
          </div>
        </div>

        {/* Score Overview Card */}
        <Card className="animate-fade-in-delay-1" style={{ marginBottom: '32px' }}>
          <div style={{ display: 'flex', gap: '32px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
            {/* Score Circle */}
            <div style={{ textAlign: 'center', flexShrink: 0 }}>
              <div style={{
                width: 96, height: 96,
                borderRadius: '50%',
                border: '3px solid var(--amber-primary)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: 'rgba(212,130,10,0.06)',
                boxShadow: '0 0 24px rgba(212,130,10,0.15)',
              }}>
                <span style={{
                  fontFamily: 'var(--font-display)',
                  fontStyle: 'italic',
                  fontSize: '36px',
                  color: 'var(--amber-light)',
                }}>
                  {score.toFixed(1)}
                </span>
              </div>
              <p style={{
                fontSize: '12px',
                color: 'var(--text-secondary)',
                marginTop: '8px',
              }}>
                out of 10
              </p>
            </div>

            {/* Score Label */}
            <div style={{ flex: 1, minWidth: '200px' }}>
              <h3 style={{ marginBottom: '8px' }}>Overall Score</h3>
              <p style={{
                fontSize: '15px',
                color: 'var(--text-secondary)',
                lineHeight: 1.6,
              }}>
                {score >= 8 ? 'Exceptional performance — demonstrates deep, nuanced understanding.' :
                 score >= 6 ? 'Strong performance — covers key concepts with good depth.' :
                 score >= 4 ? 'Adequate performance — basic understanding with room for growth.' :
                 'Needs improvement — significant gaps in understanding.'}
              </p>
            </div>
          </div>
        </Card>

        {/* Strengths */}
        {strengths.length > 0 && (
          <div className="animate-fade-in-delay-2" style={{ marginBottom: '32px' }}>
            <h2 style={{ marginBottom: '20px' }}>Strengths Observed</h2>
            <Card>
              <ul style={{ listStyle: 'none', padding: 0 }}>
                {strengths.map((s, i) => (
                  <li key={i} style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '12px',
                    marginBottom: i < strengths.length - 1 ? '12px' : 0,
                  }}>
                    <CheckCircle
                      size={18}
                      color="var(--amber-primary)"
                      style={{ flexShrink: 0, marginTop: '2px' }}
                    />
                    <span style={{ fontSize: '15px', lineHeight: 1.6 }}>{s}</span>
                  </li>
                ))}
              </ul>
            </Card>
          </div>
        )}

        {/* Gaps */}
        {gaps.length > 0 && (
          <div className="animate-fade-in-delay-3" style={{ marginBottom: '32px' }}>
            <h2 style={{ marginBottom: '20px' }}>Areas for Improvement</h2>
            <Card>
              <ul style={{ listStyle: 'none', padding: 0 }}>
                {gaps.map((g, i) => (
                  <li key={i} style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '12px',
                    marginBottom: i < gaps.length - 1 ? '12px' : 0,
                  }}>
                    <AlertCircle
                      size={18}
                      color="rgba(212,130,10,0.6)"
                      style={{ flexShrink: 0, marginTop: '2px' }}
                    />
                    <span style={{ fontSize: '15px', lineHeight: 1.6 }}>{g}</span>
                  </li>
                ))}
              </ul>
            </Card>
          </div>
        )}

        {/* Per-Question Breakdown */}
        {perQuestion.length > 0 && (
          <div style={{ marginBottom: '32px' }}>
            <h2 style={{ marginBottom: '20px' }}>Question-by-Question Breakdown</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {perQuestion.map((pq, i) => (
                <Card key={i}>
                  <div style={{ display: 'flex', gap: '24px', alignItems: 'flex-start' }}>
                    {/* Question Number */}
                    <span style={{
                      fontFamily: 'var(--font-display)',
                      fontStyle: 'italic',
                      fontSize: '48px',
                      color: 'var(--amber-muted)',
                      lineHeight: 1,
                      flexShrink: 0,
                      width: '48px',
                    }}>
                      {i + 1}
                    </span>

                    <div style={{ flex: 1, minWidth: 0 }}>
                      {/* Score + Assessment */}
                      <div style={{
                        display: 'flex',
                        gap: '12px',
                        alignItems: 'center',
                        marginBottom: '8px',
                      }}>
                        <Badge>
                          {typeof pq.score === 'number' ? `${pq.score}/10` : pq.assessment || 'N/A'}
                        </Badge>
                      </div>

                      {/* Question Preview */}
                      <p style={{
                        fontSize: '13px',
                        color: 'var(--text-secondary)',
                        fontStyle: 'italic',
                        marginBottom: '8px',
                        lineHeight: 1.5,
                      }}>
                        {pq.question_text?.substring(0, 120)}...
                      </p>

                      {/* Feedback */}
                      <p style={{
                        fontSize: '14px',
                        color: 'var(--text-primary)',
                        lineHeight: 1.6,
                      }}>
                        {pq.feedback}
                      </p>

                      {/* What Was Missed */}
                      {pq.what_was_missed && pq.what_was_missed !== 'N/A' && (
                        <p style={{
                          fontSize: '13px',
                          color: 'var(--text-secondary)',
                          marginTop: '8px',
                          lineHeight: 1.5,
                        }}>
                          <strong style={{ color: 'var(--amber-muted)' }}>Could improve: </strong>
                          {pq.what_was_missed}
                        </p>
                      )}
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          </div>
        )}

        {/* Recommendations */}
        {recommendations.length > 0 && (
          <div style={{ marginBottom: '48px' }}>
            <h2 style={{ marginBottom: '20px' }}>Recommended Study Areas</h2>
            <Card>
              <ul style={{ listStyle: 'none', padding: 0 }}>
                {recommendations.map((r, i) => (
                  <li key={i} style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '12px',
                    marginBottom: i < recommendations.length - 1 ? '12px' : 0,
                  }}>
                    <BookOpen
                      size={18}
                      color="var(--amber-primary)"
                      style={{ flexShrink: 0, marginTop: '2px' }}
                    />
                    <span style={{ fontSize: '15px', lineHeight: 1.6 }}>{r}</span>
                  </li>
                ))}
              </ul>
            </Card>
          </div>
        )}

        {/* Footer Actions */}
        <div style={{
          display: 'flex',
          justifyContent: 'center',
          gap: '16px',
          paddingTop: '32px',
          paddingBottom: '48px',
        }}>
          <Button onClick={() => router.push('/')}>
            Start a New Interview <ArrowRight size={16} />
          </Button>
        </div>
      </main>
    </>
  );
}
