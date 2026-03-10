export interface DataType {
  category_id: string;
  name: string;
  sensitivity: 'critical' | 'high' | 'medium' | 'low';
  gdpr_special_category: boolean;
  gdpr_article: string;
  ccpa_category: string;
  color: string;
  icon: string;
  evidence: string[];
  shared: boolean;
  shared_with: string[];
  purposes: string[];
  risk_description: string;
}

export interface RetentionItem {
  context: string;
  period_text: string;
  period_days: number | null;
  period_type: 'specific' | 'event_based' | 'vague';
  rating: 'excellent' | 'good' | 'fair' | 'poor' | 'very_poor' | 'unknown';
  rating_label: string;
  is_vague: boolean;
}

export interface RetentionAnalysis {
  items: RetentionItem[];
  overall_rating: string;
  has_vague_retention: boolean;
  has_indefinite_retention: boolean;
  has_event_based_deletion: boolean;
  has_specific_periods: boolean;
  has_deletion_policy: boolean;
  deletion_on_request: boolean;
  shortest_days: number | null;
  longest_days: number | null;
  storage_limitation_mentioned: boolean;
}

export interface DarkPattern {
  pattern_type: string;
  name: string;
  severity: 'high' | 'medium' | 'low';
  description: string;
  evidence: string[];
  gdpr_reference: string;
  confidence: number;
}

export interface DarkPatternAnalysis {
  detected: DarkPattern[];
  count: number;
  high_severity_count: number;
  medium_severity_count: number;
  low_severity_count: number;
  overall_risk: 'critical' | 'high' | 'medium' | 'low' | 'none';
  consent_mechanism_quality: string;
}

export interface RightCoverage {
  right_id: string;
  name: string;
  article: string;
  description: string;
  covered: boolean;
  evidence: string | null;
}

export interface RightsAnalysis {
  gdpr: Record<string, RightCoverage>;
  gdpr_score: number;
  gdpr_grade: string;
  ccpa: Record<string, RightCoverage>;
  ccpa_score: number;
  ccpa_grade: string;
  frameworks_mentioned: string[];
  cookie_compliance: Record<string, boolean>;
  dnt_mentioned: boolean;
  dnt_honored: boolean;
  global_privacy_control: boolean;
  overall_rights_score: number;
}

export interface SentimentResult {
  vagueness_score: number;
  specificity_score: number;
  passive_voice_ratio: number;
  active_voice_count: number;
  passive_voice_count: number;
  named_third_parties: string[];
  named_third_party_count: number;
  vague_term_examples: string[];
  hedging_examples: string[];
  specific_purpose_count: number;
  accountability: Record<string, boolean>;
  accountability_score: number;
  overall_transparency: 'high' | 'medium' | 'low' | 'very_low';
  transparency_score: number;
  avg_sentence_length: number;
  readability_rating: string;
  flesch_kincaid_words: number;
}

export interface ThirdPartyEntry {
  name: string;
  category: string;
  trust_score: number;
  trust_label: string;
  data_types_shared: string[];
  purposes: string[];
  opt_out_url: string | null;
  privacy_url: string | null;
  gdpr_compliant: boolean | null;
  cross_border_transfer: boolean;
  is_data_broker: boolean;
  evidence: string[];
}

export interface ThirdPartyAnalysis {
  count: number;
  named_count: number;
  unnamed_count: number;
  parties: ThirdPartyEntry[];
  sharing_purposes: Record<string, boolean>;
  data_sold: boolean;
  cross_border_transfers: boolean;
  transfer_safeguards: string[];
  advertising_partners: number;
  analytics_partners: number;
  risk_level: string;
  sharing_score: number;
}

export interface DetectedTracker {
  domain: string;
  name: string;
  category: string;
  risk: 'low' | 'medium' | 'high' | 'critical';
  source_type: 'script' | 'pixel' | 'iframe' | 'inline';
  url: string;
  fingerprinting: boolean;
  session_recording: boolean;
  opt_out: string | null;
  description: string;
}

export interface CookieInfo {
  name: string;
  value_preview: string;
  httponly: boolean;
  secure: boolean;
  samesite: string | null;
  path: string;
  domain: string | null;
  max_age: number | null;
  category: string;
  duration_label: string;
}

export interface TrackerResult {
  trackers: DetectedTracker[];
  total_tracker_count: number;
  by_category: Record<string, number>;
  high_risk_count: number;
  fingerprinting_detected: boolean;
  fingerprinting_evidence: string[];
  session_recording_detected: boolean;
  session_recording_evidence: string[];
  cookies: CookieInfo[];
  cookie_security: Record<string, number>;
  cmp_detected: string | null;
  inline_tracker_signals: string[];
  unique_third_party_domains: string[];
  privacy_sandbox_detected: boolean;
}

export interface ScoreBreakdown {
  data_collection: number;
  sharing: number;
  transparency: number;
  rights: number;
  retention: number;
  dark_patterns: number;
  technical: number;
  weights: Record<string, number>;
}

export interface Penalty {
  dimension: string;
  reason: string;
  penalty: number;
}

export interface Bonus {
  dimension: string;
  reason: string;
  bonus: number;
}

export interface AnalysisResult {
  cached: boolean;
  domain: string;
  url: string;
  policy_found: boolean;
  policy_url: string | null;
  policy_word_count: number;
  policy_discovery_method: 'canonical_path' | 'link_scan' | 'sitemap' | 'ai_discovery' | null;
  overall_score: number;
  grade: 'A' | 'B' | 'C' | 'D' | 'F';
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  summary: string;
  score_breakdown: ScoreBreakdown;
  penalties: Penalty[];
  bonuses: Bonus[];
  data_types: DataType[];
  retention: RetentionAnalysis;
  sentiment: SentimentResult;
  dark_patterns: DarkPatternAnalysis;
  rights: RightsAnalysis;
  third_parties: ThirdPartyAnalysis;
  trackers: TrackerResult;
}

export interface HistoryEntry {
  id: number;
  analyzed_at: string;
  overall_score: number;
  grade: string;
  risk_level: string;
}

export interface PolicyChange {
  id: number;
  detected_at: string;
  summary: string;
  added_lines: number;
  removed_lines: number;
  similarity_ratio: number;
  diff_snippets: Array<{ type: string; old?: string; new?: string; text?: string }>;
}

export interface DomainHistory {
  domain: string;
  analyses: HistoryEntry[];
  policy_changes: PolicyChange[];
}

// ─── AI Types ─────────────────────────────────────────────────────────────

export interface AIRedFlag {
  issue: string;
  evidence: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  action: string;
}

export interface AIComplianceGap {
  regulation: string;
  gap: string;
  recommendation: string;
}

export interface PolicyAIAnalysis {
  plain_summary: string;
  tldr: string;
  headline_risks: string[];
  red_flags: AIRedFlag[];
  positive_findings: string[];
  compliance_gaps: AIComplianceGap[];
  user_rights_summary: string;
  recommended_actions: string[];
  risk_narrative: string;
  data_story: string;
  ai_score_commentary: string;
  ai_available: boolean;
}

export interface PageFetch {
  url: string;
  label: string;
  content: string;
  success: boolean;
  error?: string;
}

export interface ThirdPartyDossier {
  name: string;
  category: string;
  pages_fetched: PageFetch[];
  pages_found: Record<string, string>;
  ai_summary: string;
  data_collected: string[];
  data_shared_with: string[];
  certifications: string[];
  gdpr_role: string;
  data_location: string[];
  retention_claimed: string;
  opt_out_url: string | null;
  risk_flags: string[];
  positive_signals: string[];
  trust_score_ai: number;
  error?: string;
}

export interface EcosystemMap {
  domain: string;
  total_parties_researched: number;
  dossiers: ThirdPartyDossier[];
  executive_summary: string;
  highest_risk_party: string | null;
  data_flow_description: string;
  recommended_actions: string[];
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}
