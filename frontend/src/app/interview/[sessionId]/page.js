'use client';

import { useState, useEffect, use, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowRight, Sparkles, CheckCircle } from 'lucide-react';
import Grainient from '@/components/ui/Grainient';
import Card from '@/components/ui/Card';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import ProgressBar from '@/components/ui/ProgressBar';
import Header from '@/components/layout/Header';
import { startInterview, submitAnswer, generateSummary, getSession, getProgress } from '@/lib/api';

export default function InterviewPage({ params }) {
  const { sessionId } = use(params);
  const router = useRouter();

  const [session, setSession] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answer, setAnswer] = useState('');
  const [answeredTopics, setAnsweredTopics] = useState([]);

  const [loadingQuestions, setLoadingQuestions] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [complete, setComplete] = useState(false);
  const [generatingSummary, setGeneratingSummary] = useState(false);
  const [error, setError] = useState('');
  const [questionVisible, setQuestionVisible] = useState(false);

  const hasStarted = useRef(false);

  // Load session, questions, AND progress on mount
  useEffect(() => {
    if (hasStarted.current) return;
    hasStarted.current = true;

    async function init() {
      try {
        const sess = await getSession(sessionId);
        setSession(sess);

        const result = await startInterview(sessionId);
        setQuestions(result.questions);

        // Check progress — resume from first unanswered question
        const progress = await getProgress(sessionId);

        if (progress.is_complete) {
          // All questions already answered — go to summary
          setComplete(true);
          router.push(`/summary/${sessionId}`);
          return;
        }

        // Find the first unanswered question
        const answeredIds = new Set(progress.answered_question_ids);
        const answeredQs = result.questions.filter(q => answeredIds.has(q.id));
        const firstUnanswered = result.questions.findIndex(q => !answeredIds.has(q.id));

        // Restore answered topics for left panel
        setAnsweredTopics(answeredQs.map(q => q.topic));
        setCurrentIndex(firstUnanswered >= 0 ? firstUnanswered : 0);
        setLoadingQuestions(false);

        // Animate question in
        setTimeout(() => setQuestionVisible(true), 100);
      } catch (err) {
        setError(err.message || 'Failed to load interview');
        setLoadingQuestions(false);
      }
    }
    init();
  }, [sessionId]);

  const currentQuestion = questions[currentIndex];
  const totalQuestions = questions.length;
  const wordCount = answer.trim().split(/\s+/).filter(Boolean).length;

  const handleSubmit = async () => {
    if (answer.trim().length < 10) return;

    setSubmitting(true);
    setError('');

    try {
      const result = await submitAnswer(sessionId, currentQuestion.id, answer.trim());

      // Track answered topic
      setAnsweredTopics(prev => [...prev, currentQuestion.topic]);

      if (result.is_complete) {
        // All questions answered
        setComplete(true);
        setGeneratingSummary(true);

        try {
          await generateSummary(sessionId);
        } catch {
          // Summary generation might fail but we still redirect
        }

        setTimeout(() => {
          router.push(`/summary/${sessionId}`);
        }, 2000);
      } else {
        // Next question
        setQuestionVisible(false);
        setAnswer('');
        setSubmitting(false);

        setTimeout(() => {
          setCurrentIndex(result.next_question_index);
          setTimeout(() => setQuestionVisible(true), 100);
        }, 300);
      }
    } catch (err) {
      setError(err.message || 'Failed to submit answer');
      setSubmitting(false);
    }
  };

  // ── Complete State ───────────────────────────────────────────────────────
  if (complete) {
    return (
      <>
        <Grainient opacity={0.6} />
        <Header />
        <main style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '0 24px',
        }}>
          <Card className="animate-fade-in" style={{ textAlign: 'center', maxWidth: '480px', padding: '64px 48px' }}>
            <Sparkles size={40} color="var(--amber-primary)" style={{ margin: '0 auto 24px' }} />
            <h2 style={{ marginBottom: '16px' }}>Interview Complete</h2>
            <p style={{ fontSize: '15px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              Generating your personalised report...
            </p>
            <div style={{
              marginTop: '24px',
              display: 'flex',
              gap: '8px',
              justifyContent: 'center',
            }}>
              {[0, 1, 2].map(i => (
                <div
                  key={i}
                  style={{
                    width: 8, height: 8,
                    borderRadius: '50%',
                    background: 'var(--amber-primary)',
                    animation: `pulse-glow 1.4s ease-in-out ${i * 0.2}s infinite`,
                  }}
                />
              ))}
            </div>
          </Card>
        </main>
      </>
    );
  }

  // ── Loading State ────────────────────────────────────────────────────────
  if (loadingQuestions) {
    return (
      <>
        <Grainient opacity={0.6} />
        <Header />
        <main style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '0 24px',
        }}>
          <Card className="animate-fade-in" style={{ textAlign: 'center', maxWidth: '480px', padding: '64px 48px' }}>
            <div style={{
              width: 48, height: 48,
              borderRadius: '50%',
              border: '3px solid rgba(212,130,10,0.2)',
              borderTopColor: 'var(--amber-primary)',
              animation: 'spin 0.8s linear infinite',
              margin: '0 auto 24px',
            }} />
            <h2 style={{ marginBottom: '16px' }}>Preparing Your Interview</h2>
            <p style={{ fontSize: '15px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              Our AI is analysing your resume and generating personalised questions...
            </p>
            <style jsx>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
          </Card>
        </main>
      </>
    );
  }

  // ── Main Interview UI ────────────────────────────────────────────────────
  const parsedResume = session?.parsed_resume;

  return (
    <>
      <Grainient opacity={0.6} />
      <Header subtitle="Interview in Progress" />

      {/* Global Progress Bar */}
      <div style={{
        position: 'fixed',
        top: '64px',
        left: 0,
        right: 0,
        zIndex: 40,
        padding: '0 32px',
      }}>
        <ProgressBar current={currentIndex + 1} total={totalQuestions} />
      </div>

      <main style={{
        minHeight: '100vh',
        display: 'flex',
        paddingTop: '100px',
        gap: '32px',
        maxWidth: '1200px',
        margin: '0 auto',
        padding: '100px 32px 48px',
      }}>
        {/* Left Panel — Session Context */}
        <aside style={{
          width: '280px',
          flexShrink: 0,
          position: 'sticky',
          top: '100px',
          alignSelf: 'flex-start',
          display: 'none', // hidden on mobile
        }} className="lg-panel">
          <Card>
            {/* Candidate Info */}
            {parsedResume && (
              <>
                <p style={{
                  fontSize: '11px',
                  fontWeight: 500,
                  textTransform: 'uppercase',
                  letterSpacing: '0.1em',
                  color: 'var(--text-secondary)',
                  marginBottom: '12px',
                }}>
                  Candidate
                </p>
                <Badge>{parsedResume.experience_level || 'Mid'} Level</Badge>
                <div style={{ marginTop: '12px', display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {(parsedResume.skills || []).slice(0, 6).map((skill, i) => (
                    <Badge key={i}>{skill}</Badge>
                  ))}
                </div>
              </>
            )}

            {/* Divider */}
            <div style={{
              borderTop: '1px solid rgba(212,130,10,0.08)',
              margin: '20px 0',
            }} />

            {/* Topics Covered */}
            <p style={{
              fontSize: '11px',
              fontWeight: 500,
              textTransform: 'uppercase',
              letterSpacing: '0.1em',
              color: 'var(--text-secondary)',
              marginBottom: '12px',
            }}>
              Topics Covered
            </p>
            {answeredTopics.length === 0 ? (
              <p style={{ fontSize: '13px', color: 'var(--text-disabled)' }}>None yet</p>
            ) : (
              <ul style={{ listStyle: 'none', padding: 0 }}>
                {answeredTopics.map((topic, i) => (
                  <li key={i} style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    fontSize: '13px',
                    color: 'var(--text-secondary)',
                    marginBottom: '6px',
                  }}>
                    <CheckCircle size={14} color="var(--amber-primary)" />
                    {topic}
                  </li>
                ))}
              </ul>
            )}

            {/* Divider */}
            <div style={{
              borderTop: '1px solid rgba(212,130,10,0.08)',
              margin: '20px 0',
            }} />

            {/* Question Counter */}
            <h2 style={{ fontSize: '36px' }}>
              {currentIndex + 1}
              <span style={{ fontSize: '18px', color: 'var(--text-secondary)' }}> / {totalQuestions}</span>
            </h2>
          </Card>
        </aside>

        {/* Right Panel — Question + Answer */}
        <div style={{ flex: 1, maxWidth: '720px' }}>
          {currentQuestion && (
            <div
              style={{
                opacity: questionVisible ? 1 : 0,
                transform: questionVisible ? 'translateY(0)' : 'translateY(12px)',
                transition: 'all 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
              }}
            >
              {/* Question Label */}
              <span style={{
                fontFamily: 'var(--font-body)',
                fontSize: '11px',
                fontWeight: 500,
                textTransform: 'uppercase',
                letterSpacing: '0.1em',
                color: 'var(--amber-muted)',
                marginBottom: '16px',
                display: 'block',
              }}>
                Question {currentIndex + 1}
              </span>

              {/* Question Text */}
              <p style={{
                fontFamily: 'var(--font-body)',
                fontSize: '18px',
                color: 'var(--text-primary)',
                lineHeight: 1.6,
                fontWeight: 400,
                marginBottom: '8px',
              }}>
                {currentQuestion.question_text}
              </p>

              {/* Topic Badge */}
              <div style={{ marginBottom: '32px' }}>
                <Badge>{currentQuestion.topic}</Badge>
              </div>

              {/* Answer Textarea */}
              <div style={{ position: 'relative' }}>
                <textarea
                  value={answer}
                  onChange={(e) => setAnswer(e.target.value)}
                  placeholder="Type your answer here — be as detailed as you can..."
                  aria-label="Your answer"
                  disabled={submitting}
                  style={{
                    width: '100%',
                    minHeight: '180px',
                    background: 'rgba(255,255,255,0.03)',
                    border: '1px solid rgba(212,130,10,0.15)',
                    borderRadius: 'var(--radius-input)',
                    padding: '16px',
                    fontFamily: 'var(--font-body)',
                    fontSize: '15px',
                    color: 'var(--text-primary)',
                    resize: 'vertical',
                    outline: 'none',
                    transition: 'border-color 0.2s, box-shadow 0.2s',
                    lineHeight: 1.6,
                  }}
                  onFocus={(e) => {
                    e.target.style.borderColor = 'rgba(212,130,10,0.5)';
                    e.target.style.boxShadow = '0 0 0 3px rgba(212,130,10,0.12)';
                  }}
                  onBlur={(e) => {
                    e.target.style.borderColor = 'rgba(212,130,10,0.15)';
                    e.target.style.boxShadow = 'none';
                  }}
                />

                {/* Word Count */}
                <span style={{
                  position: 'absolute',
                  bottom: '12px',
                  right: '16px',
                  fontSize: '12px',
                  color: 'var(--text-secondary)',
                  pointerEvents: 'none',
                }}>
                  {wordCount} words
                </span>
              </div>

              {/* Action Row */}
              <div style={{
                display: 'flex',
                justifyContent: 'flex-end',
                alignItems: 'center',
                marginTop: '20px',
                gap: '16px',
              }}>
                <Button
                  onClick={handleSubmit}
                  disabled={answer.trim().length < 10 || submitting}
                  loading={submitting}
                >
                  Submit Answer <ArrowRight size={16} />
                </Button>
              </div>

              {/* Helper Text */}
              <p style={{
                fontSize: '12px',
                color: 'var(--text-secondary)',
                marginTop: '12px',
                textAlign: 'right',
              }}>
                Your answer will be saved and used in your final evaluation.
              </p>

              {/* Error */}
              {error && (
                <p style={{ fontSize: '13px', color: 'var(--error)', marginTop: '12px' }}>
                  {error}
                </p>
              )}
            </div>
          )}
        </div>
      </main>

      {/* CSS for responsive left panel */}
      <style jsx global>{`
        @media (min-width: 1024px) {
          .lg-panel { display: block !important; }
        }
      `}</style>
    </>
  );
}
