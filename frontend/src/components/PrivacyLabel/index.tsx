import React, { useState } from 'react';
import type { AnalysisResult } from '../../types';
import { getAIInsights, getEcosystemResearch } from '../../api';
import ScoreHeader from './ScoreHeader';
import NutritionFacts from './NutritionFacts';
import DataTypes from './DataTypes';
import ThirdParties from './ThirdParties';
import Trackers from './Trackers';
import Retention from './Retention';
import DarkPatterns from './DarkPatterns';
import Rights from './Rights';
import Sentiment from './Sentiment';
import Cookies from './Cookies';
import DynamicScan from './DynamicScan';
import MismatchPanel from './MismatchPanel';
import PolicyHistory from './PolicyHistory';
import AIInsights from './AIInsights';
import EcosystemResearch from './EcosystemResearch';
import PrivacyAssistant from './PrivacyAssistant';

interface Props {
  result: AnalysisResult;
  onReanalyze?: () => void;
}

const TABS = [
  { id: 'overview',      label: 'Overview',         group: 'core' },
  { id: 'dynamic',       label: 'Dynamic Scan',     group: 'core' },
  { id: 'mismatch',      label: 'Mismatch',         group: 'core' },
  { id: 'data',          label: 'Data Collected',   group: 'core' },
  { id: 'sharing',       label: 'Third Parties',    group: 'core' },
  { id: 'trackers',      label: 'Trackers',         group: 'core' },
  { id: 'cookies',       label: 'Cookies',          group: 'core' },
  { id: 'retention',     label: 'Retention',        group: 'core' },
  { id: 'dark_patterns', label: 'Dark Patterns',    group: 'core' },
  { id: 'rights',        label: 'Rights',           group: 'core' },
  { id: 'transparency',  label: 'Transparency',     group: 'core' },
  { id: 'history',       label: 'Policy History',   group: 'core' },
  { id: 'ai_insights',   label: 'AI Insights',      group: 'ai'   },
  { id: 'ecosystem',     label: 'Ecosystem',        group: 'ai'   },
  { id: 'assistant',     label: 'Assistant',        group: 'ai'   },
];

export default function PrivacyLabel({ result, onReanalyze }: Props) {
  const [activeTab, setActiveTab] = useState('overview');

  const hasMismatches = (result.mismatch_analysis?.total_count ?? 0) > 0;

  return (
    <div className="space-y-4">
      {/* Score header */}
      <ScoreHeader result={result} onReanalyze={onReanalyze} />

      {/* Tabs */}
      <div className="sticky top-3 z-30 rounded-full border border-white/80 bg-white/75 p-1 shadow-[var(--shadow-sm)] backdrop-blur-xl">
        <div className="flex gap-1 overflow-x-auto scrollbar-hide">
          {TABS.map((tab, idx) => {
            const hasAlert = (
              (tab.id === 'dark_patterns' && result.dark_patterns?.count > 0) ||
              (tab.id === 'trackers'      && result.trackers?.fingerprinting_detected) ||
              (tab.id === 'mismatch'      && hasMismatches)
            );
            const isAI = tab.group === 'ai';
            const showSeparator = isAI && TABS[idx - 1]?.group === 'core';

            return (
              <React.Fragment key={tab.id}>
                {showSeparator && (
                  <div className="w-px bg-border/60 my-2 mx-1 shrink-0" />
                )}
                <button
                  onClick={() => setActiveTab(tab.id)}
                  className={`relative whitespace-nowrap rounded-full px-4 py-2.5 text-[11px] font-mono font-medium uppercase tracking-[0.08em] transition-all ${
                    activeTab === tab.id
                      ? isAI
                        ? 'bg-[#0E0E0D] text-[#FBFAF7]'
                        : tab.id === 'mismatch'
                          ? 'bg-[#0E0E0D] text-[#FBFAF7]'
                          : 'bg-[#0E0E0D] text-[#FBFAF7]'
                      : isAI
                        ? 'text-violet-400/70 hover:bg-black/5'
                        : tab.id === 'mismatch'
                          ? 'text-orange-400/70 hover:bg-black/5'
                          : 'text-white/50 hover:bg-black/5 hover:text-white/80'
                  }`}
                >
                  {tab.label}
                  {hasAlert && (
                    <span className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-red-500" />
                  )}
                </button>
              </React.Fragment>
            );
          })}
        </div>
      </div>

      {/* Tab content */}
      <div className="pb-8">
        {activeTab === 'overview'      && <NutritionFacts result={result} onTabChange={setActiveTab} />}
        {activeTab === 'dynamic'       && <DynamicScan dynamic={result.dynamic_crawling} />}
        {activeTab === 'mismatch'      && <MismatchPanel mismatch={result.mismatch_analysis} />}
        {activeTab === 'data'          && <DataTypes dataTypes={result.data_types || []} result={result} />}
        {activeTab === 'sharing'       && <ThirdParties analysis={result.third_parties} result={result} />}
        {activeTab === 'trackers'      && <Trackers trackers={result.trackers} runtime={result.runtime_observations} />}
        {activeTab === 'cookies'       && <Cookies trackers={result.trackers} runtime={result.runtime_observations} />}
        {activeTab === 'retention'     && <Retention retention={result.retention} result={result} />}
        {activeTab === 'dark_patterns' && <DarkPatterns analysis={result.dark_patterns} result={result} />}
        {activeTab === 'rights'        && <Rights rights={result.rights} result={result} />}
        {activeTab === 'transparency'  && <Sentiment sentiment={result.sentiment} result={result} />}
        {activeTab === 'history'       && <PolicyHistory domain={result.domain} />}

        {activeTab === 'ai_insights' && (
          <AIInsights
            domain={result.domain}
            result={result}
            onLoad={() => getAIInsights(result.domain)}
          />
        )}

        {activeTab === 'ecosystem' && (
          <EcosystemResearch
            domain={result.domain}
            result={result}
            onLoad={(maxParties) => getEcosystemResearch(result.domain, maxParties)}
          />
        )}

        {activeTab === 'assistant' && (
          <PrivacyAssistant domain={result.domain} result={result} />
        )}
      </div>
    </div>
  );
}
