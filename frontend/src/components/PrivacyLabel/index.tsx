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
  { id: 'ai_insights',   label: '✦ AI Insights',    group: 'ai'   },
  { id: 'ecosystem',     label: 'Ecosystem',        group: 'ai'   },
  { id: 'assistant',     label: '💬 Assistant',     group: 'ai'   },
];

export default function PrivacyLabel({ result, onReanalyze }: Props) {
  const [activeTab, setActiveTab] = useState('overview');

  const hasMismatches = (result.mismatch_analysis?.total_count ?? 0) > 0;

  return (
    <div className="space-y-6">
      {/* Score header */}
      <ScoreHeader result={result} onReanalyze={onReanalyze} />

      {/* Tabs */}
      <div className="border-b border-border sticky top-[57px] bg-bg/95 backdrop-blur-sm z-30">
        <div className="flex overflow-x-auto gap-0 scrollbar-hide">
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
                  className={`relative px-4 py-3 text-xs font-mono font-medium whitespace-nowrap transition-colors border-b-2 -mb-px ${
                    activeTab === tab.id
                      ? isAI
                        ? 'border-violet-400 text-violet-300'
                        : tab.id === 'mismatch'
                          ? 'border-orange-400 text-orange-300'
                          : 'border-accent-green text-accent-green'
                      : isAI
                        ? 'border-transparent text-violet-400/50 hover:text-violet-300/80'
                        : tab.id === 'mismatch'
                          ? 'border-transparent text-orange-400/50 hover:text-orange-300/80'
                          : 'border-transparent text-white/40 hover:text-white/70'
                  }`}
                >
                  {tab.label}
                  {hasAlert && (
                    <span className="absolute top-2 right-2 w-1.5 h-1.5 rounded-full bg-red-500" />
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
        {activeTab === 'trackers'      && <Trackers trackers={result.trackers} />}
        {activeTab === 'cookies'       && <Cookies trackers={result.trackers} />}
        {activeTab === 'retention'     && <Retention retention={result.retention} />}
        {activeTab === 'dark_patterns' && <DarkPatterns analysis={result.dark_patterns} />}
        {activeTab === 'rights'        && <Rights rights={result.rights} />}
        {activeTab === 'transparency'  && <Sentiment sentiment={result.sentiment} />}
        {activeTab === 'history'       && <PolicyHistory domain={result.domain} />}

        {activeTab === 'ai_insights' && (
          <AIInsights
            domain={result.domain}
            onLoad={() => getAIInsights(result.domain)}
          />
        )}

        {activeTab === 'ecosystem' && (
          <EcosystemResearch
            domain={result.domain}
            onLoad={() => getEcosystemResearch(result.domain)}
          />
        )}

        {activeTab === 'assistant' && (
          <PrivacyAssistant domain={result.domain} />
        )}
      </div>
    </div>
  );
}
