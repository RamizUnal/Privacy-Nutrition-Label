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
    <div className="flex min-h-[650px] flex-col items-center justify-center gap-8 px-4 text-center">
      {/* Animated shield */}
      <div className="relative w-24 h-24">
        <div className="absolute inset-0 rounded-full border border-accent-green/20 animate-ping" />
        <div className="absolute inset-2 rounded-full border border-accent-green/30 animate-ping [animation-delay:300ms]" />
        <div className="absolute inset-4 rounded-full border border-accent-green/40 animate-ping [animation-delay:600ms]" />
        <div className="glass-panel flex h-24 w-24 items-center justify-center rounded-full">
          <svg className="w-10 h-10 text-accent-green" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
          </svg>
        </div>
      </div>

      {/* URL display */}
      <div className="glass-panel max-w-md truncate rounded-full px-5 py-2 font-mono text-sm text-white/55">
        target / <b className="font-medium text-white">{url}</b>
      </div>

      {/* Steps — these are an estimated timeline of phases the analyzer
          typically goes through; we DON'T have a real success signal from the
          backend yet, so we deliberately do NOT mark past steps with a green
          checkmark (which would imply that step actually succeeded). Past
          steps get a neutral dim dot, the current step pulses, future steps
          stay as outlined circles. The real ✓ / ✗ findings appear once the
          analysis completes and the result page renders. */}
      <div className="glass-panel w-full max-w-md space-y-2 rounded-2xl p-5 text-left">
        {STEPS.map((s, i) => (
          <div
            key={i}
            className={`flex items-center gap-3 font-mono text-xs transition-all duration-500 ${
              i <= step ? 'opacity-100' : 'opacity-25'
            }`}
          >
            {i < step ? (
              // Past step: neutral filled dot, NOT a checkmark — we can't
              // honestly claim it succeeded yet.
              <div className="w-4 h-4 flex-shrink-0 flex items-center justify-center">
                <div className="w-1.5 h-1.5 rounded-full bg-white/30" />
              </div>
            ) : i === step ? (
              // Currently-running step: pulsing accent dot.
              <div className="w-4 h-4 flex-shrink-0 flex items-center justify-center">
                <div className="w-2 h-2 rounded-full bg-accent-green animate-pulse" />
              </div>
            ) : (
              // Future step: empty outlined circle.
              <div className="w-4 h-4 flex-shrink-0 rounded-full border border-white/10" />
            )}
            <span className={
              i === step ? 'text-accent-green'
              : i < step ? 'text-white/40'
              : 'text-white/25'
            }>
              {s.label}
            </span>
          </div>
        ))}
      </div>

      <p className="max-w-xs text-center font-mono text-[10px] leading-relaxed text-white/35">
        These are typical phases — final findings (✓ / ✗) appear once analysis completes.
      </p>
    </div>
  );
}
