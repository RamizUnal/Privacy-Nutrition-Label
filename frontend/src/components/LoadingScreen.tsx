import React, { useEffect, useState } from 'react';

const STEPS = [
  { label: 'Discovering privacy policy URL…', delay: 0 },
  { label: 'Crawling privacy policy document…', delay: 1200 },
  { label: 'Detecting GDPR special categories…', delay: 2400 },
  { label: 'Analyzing third-party sharing…', delay: 3200 },
  { label: 'Scanning for dark patterns…', delay: 4200 },
  { label: 'Checking GDPR/CCPA rights coverage…', delay: 5000 },
  { label: 'Detecting trackers & cookies…', delay: 6000 },
  { label: 'Running sentiment analysis…', delay: 7000 },
  { label: 'Calculating privacy score…', delay: 8200 },
];

export default function LoadingScreen({ url }: { url: string }) {
  const [step, setStep] = useState(0);

  useEffect(() => {
    const timers = STEPS.map((s, i) =>
      setTimeout(() => setStep(i), s.delay)
    );
    return () => timers.forEach(clearTimeout);
  }, []);

  return (
    <div className="flex flex-col items-center justify-center min-h-[80vh] gap-8">
      {/* Animated shield */}
      <div className="relative w-24 h-24">
        <div className="absolute inset-0 rounded-full border border-accent-green/20 animate-ping" />
        <div className="absolute inset-2 rounded-full border border-accent-green/30 animate-ping [animation-delay:300ms]" />
        <div className="absolute inset-4 rounded-full border border-accent-green/40 animate-ping [animation-delay:600ms]" />
        <div className="w-24 h-24 rounded-full border border-accent-green/60 flex items-center justify-center bg-panel">
          <svg className="w-10 h-10 text-accent-green" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
          </svg>
        </div>
      </div>

      {/* URL display */}
      <div className="font-mono text-sm text-white/40 border border-border rounded px-4 py-2 bg-panel max-w-md truncate">
        🔍 {url}
      </div>

      {/* Steps */}
      <div className="space-y-2 min-w-[320px]">
        {STEPS.map((s, i) => (
          <div
            key={i}
            className={`flex items-center gap-3 font-mono text-xs transition-all duration-500 ${
              i <= step ? 'opacity-100' : 'opacity-20'
            }`}
          >
            {i < step ? (
              <svg className="w-4 h-4 text-accent-green flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
              </svg>
            ) : i === step ? (
              <div className="w-4 h-4 flex-shrink-0 flex items-center justify-center">
                <div className="w-2 h-2 rounded-full bg-accent-green animate-pulse" />
              </div>
            ) : (
              <div className="w-4 h-4 flex-shrink-0 rounded-full border border-white/10" />
            )}
            <span className={i === step ? 'text-accent-green' : i < step ? 'text-white/60' : 'text-white/20'}>
              {s.label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
