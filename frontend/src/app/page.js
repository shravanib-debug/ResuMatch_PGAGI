'use client';

import { useState, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Upload, FileText, Check } from 'lucide-react';
import Grainient from '@/components/ui/Grainient';
import BlurText from '@/components/ui/BlurText';
import Card from '@/components/ui/Card';
import Header from '@/components/layout/Header';
import { createSession, uploadResume } from '@/lib/api';

export default function HomePage() {
  const router = useRouter();
  const fileInputRef = useRef(null);

  const [file, setFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const handleFile = useCallback(async (selectedFile) => {
    setError('');

    if (!selectedFile.name.toLowerCase().endsWith('.pdf')) {
      setError('Only PDF files are accepted');
      return;
    }

    if (selectedFile.size > 5 * 1024 * 1024) {
      setError('File too large (max 5MB)');
      return;
    }

    setFile(selectedFile);
    setUploading(true);

    try {
      // Simulate progress for UX while creating session
      setProgress(20);
      const session = await createSession('aiml'); // role selected on next page
      localStorage.setItem('sessionId', session.id);

      setProgress(50);

      // Upload resume
      const result = await uploadResume(session.id, selectedFile);
      localStorage.setItem('parsedResume', JSON.stringify(result.parsed_resume));

      setProgress(100);
      setSuccess(true);

      // Navigate to role selection after brief success state
      setTimeout(() => {
        router.push('/role');
      }, 800);
    } catch (err) {
      setError(err.message || 'Upload failed. Please try again.');
      setUploading(false);
      setProgress(0);
    }
  }, [router]);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);
    const droppedFile = e.dataTransfer.files?.[0];
    if (droppedFile) handleFile(droppedFile);
  }, [handleFile]);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    setDragOver(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setDragOver(false);
  }, []);

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
          paddingBottom: '5vh',
        }}
      >
        {/* Label */}
        <span
          className="animate-fade-in"
          style={{
            fontFamily: 'var(--font-body)',
            fontSize: '11px',
            fontWeight: 500,
            textTransform: 'uppercase',
            letterSpacing: '0.15em',
            color: 'var(--amber-muted)',
            marginBottom: '16px',
          }}
        >
          AI-Powered Interview
        </span>

        {/* Title */}
        <h1 className="animate-fade-in-delay-1" style={{ textAlign: 'center', marginBottom: '16px' }}>
          <BlurText text="Upload Your Resume" />
        </h1>

        {/* Subtitle */}
        <p
          className="animate-fade-in-delay-2"
          style={{
            fontFamily: 'var(--font-body)',
            fontSize: '15px',
            color: 'var(--text-secondary)',
            textAlign: 'center',
            maxWidth: '480px',
            marginBottom: '48px',
            lineHeight: 1.6,
          }}
        >
          Our AI will analyse your background and generate a personalised
          technical interview tailored to you.
        </p>

        {/* Upload Card */}
        <Card className="animate-fade-in-delay-3" style={{ width: '100%', maxWidth: '560px' }}>
          {success ? (
            /* Success State */
            <div style={{ textAlign: 'center', padding: '32px 0' }}>
              <div
                style={{
                  width: 56, height: 56,
                  borderRadius: '50%',
                  background: 'rgba(39, 174, 96, 0.15)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  margin: '0 auto 16px',
                }}
              >
                <Check size={28} color="var(--success)" />
              </div>
              <p style={{ fontSize: '15px', color: 'var(--text-primary)' }}>
                Resume processed successfully
              </p>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '8px' }}>
                Redirecting to role selection...
              </p>
            </div>
          ) : uploading ? (
            /* Uploading State */
            <div style={{ textAlign: 'center', padding: '32px 0' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', justifyContent: 'center', marginBottom: '20px' }}>
                <FileText size={20} color="var(--amber-primary)" />
                <span style={{ fontSize: '14px', color: 'var(--text-primary)' }}>{file?.name}</span>
              </div>

              {/* Progress Bar */}
              <div style={{
                width: '100%', height: '3px',
                background: 'rgba(212,130,10,0.1)',
                borderRadius: '999px',
                overflow: 'hidden',
                marginBottom: '12px',
              }}>
                <div style={{
                  width: `${progress}%`,
                  height: '100%',
                  background: 'linear-gradient(90deg, #D4820A, #F0A832)',
                  borderRadius: '999px',
                  transition: 'width 0.6s ease-out',
                }} />
              </div>

              <p style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>
                Parsing your resume with AI...
              </p>
            </div>
          ) : (
            /* Drop Zone */
            <div
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onClick={() => fileInputRef.current?.click()}
              role="button"
              tabIndex={0}
              aria-label="Upload resume PDF"
              style={{
                border: `1.5px dashed ${dragOver ? 'rgba(212,130,10,0.6)' : 'rgba(212,130,10,0.3)'}`,
                borderRadius: '12px',
                padding: '48px 32px',
                textAlign: 'center',
                cursor: 'pointer',
                background: dragOver ? 'rgba(212,130,10,0.04)' : 'transparent',
                transition: 'all 0.15s ease',
              }}
            >
              <Upload
                size={32}
                color="var(--amber-primary)"
                style={{ margin: '0 auto 16px' }}
              />
              <p style={{ fontSize: '15px', color: 'var(--text-primary)', marginBottom: '8px' }}>
                Drag & drop your PDF here
              </p>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                or click to browse — PDF only, max 5MB
              </p>

              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf"
                style={{ display: 'none' }}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) handleFile(f);
                }}
              />
            </div>
          )}

          {/* Error */}
          {error && (
            <p style={{
              fontSize: '13px',
              color: 'var(--error)',
              marginTop: '16px',
              textAlign: 'center',
            }}>
              {error}
            </p>
          )}
        </Card>
      </main>
    </>
  );
}
