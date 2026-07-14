'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { fetchAPI } from '@/lib/api';
import { Badge } from '@/components/ui/badge';

interface DashboardData {
  needs_onboarding?: boolean;
  creator: any;
  stats: any;
  products: any[];
  active_deals: any[];
  pending_approvals: any[];
  recent_activities: any[];
  patterns: any[];
  recent_thinking?: any[];
  documents?: any[];
}

interface LLMProvider {
  name: string;
  models: string[];
  needs_key: boolean;
  enabled: boolean;
  is_rate_limited: boolean;
  rate_limit_expires_in: number;
  total_calls: number;
  total_errors: number;
  last_error: string;
}

const PROVIDER_INFO: Record<string, { label: string; signupUrl: string; description: string; free: boolean }> = {
  groq: { label: 'Groq', signupUrl: 'https://console.groq.com/keys', description: 'Fast LPU inference, 30 RPM free', free: true },
  gemini: { label: 'Google Gemini', signupUrl: 'https://aistudio.google.com/apikey', description: 'Gemini 2.5 Flash, 15 RPM free', free: true },
  openrouter: { label: 'OpenRouter', signupUrl: 'https://openrouter.ai/keys', description: '28+ free models, great fallback', free: true },
  cerebras: { label: 'Cerebras', signupUrl: 'https://cloud.cerebras.ai/', description: 'Ultra-fast inference, 30 RPM free', free: true },
  mistral: { label: 'Mistral AI', signupUrl: 'https://console.mistral.ai/', description: 'Mistral models, free tier', free: true },
  'llm7-free': { label: 'LLM7 (Free)', signupUrl: '', description: 'No key needed — always available', free: true },
};

const AGENT_ICONS: Record<string, string> = {
  deal_agent: '🤝',
  content_agent: '✍️',
  finance_agent: '💰',
  memory_agent: '🧠',
  system: '⚙️',
};

const STATUS_COLORS: Record<string, string> = {
  completed: '#4ade80',
  started: '#fbbf24',
  awaiting_approval: '#fbbf24',
  approved: '#4ade80',
  declined: '#f87171',
};

const PHASE_ICONS: Record<string, string> = {
  data_gathering: '📥',
  context_loading: '🧠',
  ai_analysis: '🤖',
  ai_writing: '🤖',
  ai_generating: '🤖',
  ai_calling: '⏳',
  strategy: '🎨',
  pattern_mining: '🔍',
  result: '✅',
  planning: '🧠',
  plan_ready: '📋',
  tool_call: '🔧',
  tool_result: '📊',
  analyzing: '🔬',
  task_received: '📨',
  error: '❌',
  max_iterations: '⏰',
};

const INDUSTRIES = [
  'tech', 'music', 'fitness', 'beauty', 'food', 'fashion', 'gaming',
  'travel', 'education', 'business', 'lifestyle', 'health',
];

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'overview' | 'deals' | 'content' | 'storefront' | 'memory' | 'agents' | 'documents' | 'providers'>('overview');
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  const [activeProvider, setActiveProvider] = useState('');
  const [keyProvider, setKeyProvider] = useState('groq');
  const [keyValue, setKeyValue] = useState('');
  const [keyMsg, setKeyMsg] = useState('');
  const [thinking, setThinking] = useState<any[]>([]);
  const [runningAgent, setRunningAgent] = useState<string | null>(null);

  const loadProviders = useCallback(async () => {
    try {
      const d = await fetchAPI('/llm/providers');
      setProviders(d.providers || []);
      setActiveProvider(d.active_provider || '');
    } catch (e) {
      console.error(e);
    }
  }, []);

  const load = useCallback(async () => {
    try {
      const d = await fetchAPI('/dashboard');
      setData(d);
      if (d.recent_thinking) setThinking(d.recent_thinking);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    loadProviders();
    const interval = setInterval(load, 3000);
    return () => clearInterval(interval);
  }, [load, loadProviders]);

  const handleApprove = async (id: number) => {
    await fetchAPI(`/approvals/${id}/resolve?decision=approved`, { method: 'POST' });
    load();
  };

  const handleDecline = async (id: number) => {
    await fetchAPI(`/approvals/${id}/resolve?decision=declined`, { method: 'POST' });
    load();
  };

  const analyzeAllDeals = async () => {
    if (!data?.active_deals) return;
    for (const deal of data.active_deals.filter(d => d.status === 'pending_analysis')) {
      setRunningAgent(`Analyzing ${deal.brand_name}...`);
      await fetchAPI(`/agents/deal/analyze/${deal.id}`, { method: 'POST' });
      await load();
    }
    setRunningAgent(null);
  };

  const learnMemory = async () => {
    setRunningAgent('Memory Agent learning patterns...');
    await fetchAPI('/agents/memory/learn', { method: 'POST' });
    await load();
    setRunningAgent(null);
  };

  const addProviderKey = async () => {
    if (!keyValue.trim()) { setKeyMsg('Please enter an API key'); return; }
    try {
      setKeyMsg('Adding key...');
      await fetchAPI('/llm/providers/key', {
        method: 'POST',
        body: JSON.stringify({ provider: keyProvider, api_key: keyValue.trim() }),
      });
      setKeyValue('');
      setKeyMsg(`✅ ${PROVIDER_INFO[keyProvider]?.label || keyProvider} key added! System will use it automatically.`);
      loadProviders();
    } catch (e: any) {
      setKeyMsg(`❌ Error: ${e.message}`);
    }
  };

  const removeProviderKey = async (provider: string) => {
    try {
      await fetchAPI(`/llm/providers/${provider}`, { method: 'DELETE' });
      setKeyMsg(`✅ Removed ${PROVIDER_INFO[provider]?.label || provider} key`);
      loadProviders();
    } catch (e: any) {
      setKeyMsg(`❌ Error: ${e.message}`);
    }
  };

  const resetWorkspace = async () => {
    if (!confirm('Reset everything? This will delete all data and take you back to onboarding.')) return;
    await fetchAPI('/reset', { method: 'POST' });
    window.location.reload();
  };

  // ─── ONBOARDING SCREEN ───
  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <div style={{ textAlign: 'center' }}>
          <div className="gradient-text" style={{ fontSize: '2rem', fontFamily: 'var(--font-display)', fontWeight: 700 }}>
            CreatorForge OS
          </div>
          <div style={{ color: 'var(--color-text-muted)', marginTop: '8px' }}>Loading...</div>
        </div>
      </div>
    );
  }

  if (data?.needs_onboarding) {
    return <OnboardingScreen onOnboarded={() => load()} />;
  }

  const { creator, stats, products, active_deals, pending_approvals, recent_activities, patterns } = data!;

  return (
    <div style={{ minHeight: '100vh', background: 'var(--color-bg)' }}>
      {/* Header */}
      <header style={{
        borderBottom: '1px solid var(--color-border)',
        padding: '16px 32px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        position: 'sticky',
        top: 0,
        zIndex: 100,
        background: 'rgba(10,10,10,0.95)',
        backdropFilter: 'blur(8px)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '1.5rem' }}>🦊</span>
          <div>
            <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '1.1rem', letterSpacing: '-0.02em' }}>
              CreatorForge <span className="gradient-text">OS</span>
            </div>
            <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)' }}>The Agentic Operating System for Creators</div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          {runningAgent && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: '8px',
              padding: '6px 12px', background: 'rgba(251,191,36,0.1)',
              borderRadius: 20, border: '1px solid rgba(251,191,36,0.3)',
            }}>
              <span className="pulse-dot" style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--color-warning)', color: 'var(--color-warning)' }} />
              <span style={{ fontSize: '0.75rem', color: 'var(--color-warning)' }}>{runningAgent}</span>
            </div>
          )}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span className="pulse-dot" style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--color-success)', color: 'var(--color-success)' }} />
            <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>4 agents active</span>
          </div>
          {stats.llm_enabled && (
            <Badge style={{ background: 'rgba(74,222,128,0.1)', color: 'var(--color-success)', border: '1px solid rgba(74,222,128,0.3)' }}>
              🤖 {activeProvider || 'AI'} Active
            </Badge>
          )}
          <button
            onClick={resetWorkspace}
            style={{
              padding: '6px 12px', borderRadius: 8, background: 'transparent',
              border: '1px solid var(--color-border)', color: 'var(--color-text-muted)',
              cursor: 'pointer', fontSize: '0.72rem', fontWeight: 500,
            }}
          >
            ↻ Reset
          </button>
        </div>
      </header>

      {/* Tabs */}
      <nav style={{ display: 'flex', gap: '2px', padding: '0 32px', borderBottom: '1px solid var(--color-border)' }}>
        {([
          ['overview', 'Overview'],
          ['deals', 'Deals'],
          ['content', 'Content'],
          ['storefront', 'Storefront'],
          ['memory', 'Memory'],
          ['agents', 'Agents'],
          ['documents', 'Documents'],
          ['providers', 'AI Providers'],
        ] as const).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            style={{
              padding: '12px 16px',
              background: 'none',
              border: 'none',
              borderBottom: tab === key ? '2px solid var(--color-accent)' : '2px solid transparent',
              color: tab === key ? 'var(--color-text)' : 'var(--color-text-muted)',
              cursor: 'pointer',
              fontFamily: 'var(--font-body)',
              fontSize: '0.85rem',
              fontWeight: 500,
              transition: 'color 0.2s',
            }}
          >
            {label}
          </button>
        ))}
      </nav>

      <main style={{ maxWidth: 1200, margin: '0 auto', padding: '32px' }}>
        {tab === 'overview' && (
          <OverviewTab
            creator={creator}
            stats={stats}
            pending_approvals={pending_approvals}
            recent_activities={recent_activities}
            thinking={thinking}
            onApprove={handleApprove}
            onDecline={handleDecline}
          />
        )}
        {tab === 'deals' && (
          <DealsTab
            deals={active_deals}
            onAnalyzeAll={analyzeAllDeals}
            onAnalyze={async (id: number) => {
              setRunningAgent('Deal Agent analyzing...');
              await fetchAPI(`/agents/deal/analyze/${id}`, { method: 'POST' });
              await load();
              setRunningAgent(null);
            }}
            onReload={load}
          />
        )}
        {tab === 'content' && <ContentTab onReload={load} />}
        {tab === 'storefront' && <StorefrontTab products={products} stats={stats} onReload={load} />}
        {tab === 'memory' && <MemoryTab patterns={patterns} onLearn={learnMemory} />}
        {tab === 'agents' && <AgentsTab activities={recent_activities} thinking={thinking} />}
        {tab === 'documents' && (
          <DocumentsTab documents={data?.documents || []} onReload={load} />
        )}
        {tab === 'providers' && (
          <ProvidersTab
            providers={providers}
            activeProvider={activeProvider}
            keyProvider={keyProvider}
            setKeyProvider={setKeyProvider}
            keyValue={keyValue}
            setKeyValue={setKeyValue}
            onAddKey={addProviderKey}
            onRemoveKey={removeProviderKey}
            keyMsg={keyMsg}
          />
        )}
      </main>
    </div>
  );
}

// ═══════════════════════════════════════
// ONBOARDING SCREEN
// ═══════════════════════════════════════

function OnboardingScreen({ onOnboarded }: { onOnboarded: () => void }) {
  const [name, setName] = useState('');
  const [handle, setHandle] = useState('');
  const [industry, setIndustry] = useState('tech');
  const [bio, setBio] = useState('');
  const [followers, setFollowers] = useState('');
  const [revenue, setRevenue] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async () => {
    if (!name.trim() || !handle.trim()) {
      setError('Please enter your company name and handle');
      return;
    }
    setSubmitting(true);
    setError('');
    try {
      await fetchAPI('/onboard', {
        method: 'POST',
        body: JSON.stringify({
          company_name: name.trim(),
          handle: handle.trim().replace('@', ''),
          industry,
          bio: bio.trim() || `${name.trim()} — ${industry} content creator`,
          followers: parseInt(followers) || 0,
          monthly_revenue: parseFloat(revenue) || 0,
        }),
      });
      onOnboarded();
    } catch (e: any) {
      setError(`Error: ${e.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ minHeight: '100vh', background: 'var(--color-bg)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
      <div style={{ maxWidth: 560, width: '100%' }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <div style={{ fontSize: '3rem' }}>🦊</div>
          <div className="gradient-text" style={{ fontSize: '2rem', fontFamily: 'var(--font-display)', fontWeight: 700, marginTop: '8px' }}>
            CreatorForge OS
          </div>
          <div style={{ color: 'var(--color-text-muted)', fontSize: '0.9rem', marginTop: '4px' }}>
            The Agentic Operating System for Creators
          </div>
        </div>

        {/* What is this */}
        <div style={{
          background: 'var(--color-surface)', border: '1px solid var(--color-border)',
          borderRadius: 12, padding: '20px', marginBottom: '24px',
        }}>
          <h3 style={{ fontSize: '0.95rem', fontWeight: 600, marginBottom: '12px' }}>What is CreatorForge OS?</h3>
          <p style={{ fontSize: '0.82rem', color: 'var(--color-text-muted)', lineHeight: 1.7, marginBottom: '12px' }}>
            An AI-powered operating system that runs your creator business autonomously. Four AI agents work together:
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '0.78rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><span>🤝</span><span style={{ color: 'var(--color-text-muted)' }}><strong style={{ color: 'var(--color-text)' }}>Deal Agent</strong> — analyzes brand offers, negotiates terms</span></div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><span>✍️</span><span style={{ color: 'var(--color-text-muted)' }}><strong style={{ color: 'var(--color-text)' }}>Content Agent</strong> — drafts posts, videos, reels</span></div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><span>💰</span><span style={{ color: 'var(--color-text-muted)' }}><strong style={{ color: 'var(--color-text)' }}>Finance Agent</strong> — generates invoices, tracks payments</span></div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}><span>🧠</span><span style={{ color: 'var(--color-text-muted)' }}><strong style={{ color: 'var(--color-text)' }}>Memory Agent</strong> — learns patterns, improves decisions</span></div>
          </div>
          <div style={{
            marginTop: '14px', paddingTop: '14px', borderTop: '1px solid var(--color-border)',
            fontSize: '0.78rem', color: 'var(--color-text-muted)',
          }}>
            <strong style={{ color: 'var(--color-text)' }}>How to use:</strong> Add your brand deals and content briefs. The agents will analyze, negotiate, draft, and invoice — all with AI. You approve everything before it goes out.
          </div>
        </div>

        {/* Onboarding Form */}
        <div style={{
          background: 'var(--color-surface)', border: '1px solid var(--color-border)',
          borderRadius: 12, padding: '24px',
        }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '16px' }}>Set up your workspace</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Company / Creator Name *</label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. TechFlow Studios"
                style={inputStyle}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Handle *</label>
              <input
                value={handle}
                onChange={(e) => setHandle(e.target.value)}
                placeholder="e.g. techflow"
                style={inputStyle}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Industry / Niche</label>
              <select value={industry} onChange={(e) => setIndustry(e.target.value)} style={inputStyle}>
                {INDUSTRIES.map(i => <option key={i} value={i}>{i.charAt(0).toUpperCase() + i.slice(1)}</option>)}
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Bio / Description</label>
              <textarea
                value={bio}
                onChange={(e) => setBio(e.target.value)}
                placeholder="What do you create? What's your audience about?"
                rows={2}
                style={{ ...inputStyle, resize: 'vertical' }}
              />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Followers</label>
                <input
                  type="number"
                  value={followers}
                  onChange={(e) => setFollowers(e.target.value)}
                  placeholder="45000"
                  style={inputStyle}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Monthly Revenue ($)</label>
                <input
                  type="number"
                  value={revenue}
                  onChange={(e) => setRevenue(e.target.value)}
                  placeholder="8000"
                  style={inputStyle}
                />
              </div>
            </div>
            {error && (
              <div style={{ fontSize: '0.82rem', color: 'var(--color-danger)' }}>{error}</div>
            )}
            <button
              onClick={handleSubmit}
              disabled={submitting}
              style={{
                padding: '14px', borderRadius: 10,
                background: submitting ? 'var(--color-surface-2)' : 'var(--color-accent)',
                color: submitting ? 'var(--color-text-muted)' : '#000',
                border: 'none', cursor: submitting ? 'wait' : 'pointer',
                fontWeight: 700, fontSize: '0.9rem', marginTop: '4px',
              }}
            >
              {submitting ? 'Setting up your workspace...' : '🚀 Start →'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '10px 12px',
  background: 'var(--color-bg)',
  border: '1px solid var(--color-border)',
  borderRadius: 8,
  color: 'var(--color-text)',
  fontSize: '0.85rem',
  fontFamily: 'var(--font-body)',
  outline: 'none',
};

// ═══════════════════════════════════════
// OVERVIEW TAB
// ═══════════════════════════════════════

function OverviewTab({ creator, stats, pending_approvals, recent_activities, thinking, onApprove, onDecline }: any) {
  const [showThinking, setShowThinking] = useState(true);

  return (
    <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Creator Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div style={{
          width: 56, height: 56, borderRadius: 12,
          background: 'var(--color-surface)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '1.8rem', border: '1px solid var(--color-border)',
        }}>
          {creator.avatar || '🎵'}
        </div>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0 }}>{creator.name}</h1>
          <div style={{ color: 'var(--color-text-muted)', fontSize: '0.85rem' }}>
            @{creator.handle} · {creator.bio}
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '16px' }}>
        <StatCard label="Followers" value={stats.followers.toLocaleString()} icon="👥" />
        <StatCard label="This Month" value={`$${stats.monthly_revenue.toLocaleString()}`} icon="📈" accent />
        <StatCard label="Cleared" value={`$${stats.cleared_revenue.toLocaleString()}`} icon="✅" />
        <StatCard label="Active Deals" value={stats.active_deals} icon="🤝" />
        <StatCard label="Content" value={`${stats.published_content}/${stats.content_count}`} icon="✍️" />
        <StatCard label="Patterns" value={stats.patterns_count} icon="🧠" />
        <StatCard label="Pending" value={stats.pending_approvals} icon="⏳" highlight={stats.pending_approvals > 0} />
        <StatCard label="Total Deals" value={`$${stats.total_deal_revenue.toLocaleString()}`} icon="💰" />
      </div>

      {/* Live Agent Thinking */}
      {thinking && thinking.length > 0 && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <h2 style={{ fontSize: '1.1rem' }}>🧠 Agent Thinking Process</h2>
            <button
              onClick={() => setShowThinking(!showThinking)}
              style={{
                padding: '4px 10px', borderRadius: 6, background: 'var(--color-surface)',
                border: '1px solid var(--color-border)', color: 'var(--color-text-muted)',
                cursor: 'pointer', fontSize: '0.72rem',
              }}
            >
              {showThinking ? 'Hide' : 'Show'}
            </button>
          </div>
          {showThinking && (
            <div style={{
              background: 'var(--color-surface)', border: '1px solid var(--color-border)',
              borderRadius: 12, padding: '16px', maxHeight: '300px', overflow: 'auto',
            }}>
              {thinking.slice(0, 20).map((t: any, i: number) => (
                <div key={t.id || i} className="slide-in" style={{
                  display: 'flex', alignItems: 'start', gap: '10px',
                  padding: '8px 0', borderBottom: i < thinking.length - 1 ? '1px solid var(--color-border)' : 'none',
                }}>
                  <span style={{ fontSize: '1rem', flexShrink: 0 }}>
                    {PHASE_ICONS[t.phase] || '💭'}
                  </span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)', marginBottom: '2px' }}>
                      {AGENT_ICONS[t.agent_name] || '🤖'} {t.agent_name.replace(/_/g, ' ')} · step {t.step_number}
                    </div>
                    <div style={{ fontSize: '0.82rem', color: 'var(--color-text)' }}>{t.thought}</div>
                  </div>
                  <span className="mono" style={{ fontSize: '0.68rem', color: 'var(--color-text-muted)', flexShrink: 0 }}>
                    {new Date(t.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Pending Approvals */}
      {pending_approvals.length > 0 && (
        <div>
          <h2 style={{ fontSize: '1.1rem', marginBottom: '12px' }}>⚠️ Approval Queue</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {pending_approvals.map((a: any) => (
              <div key={a.id} className="slide-in" style={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: 12,
                padding: '16px',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600, marginBottom: '4px' }}>
                      {AGENT_ICONS[a.agent_name] || '⚙️'} {a.title}
                    </div>
                    <div style={{ color: 'var(--color-text-muted)', fontSize: '0.8rem', whiteSpace: 'pre-wrap' }}>
                      {a.summary}
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '8px', marginLeft: '16px' }}>
                    <button
                      onClick={() => onApprove(a.id)}
                      style={{
                        padding: '6px 16px', borderRadius: 8, border: 'none',
                        background: 'var(--color-success)', color: '#000',
                        cursor: 'pointer', fontWeight: 600, fontSize: '0.8rem',
                      }}
                    >Approve</button>
                    <button
                      onClick={() => onDecline(a.id)}
                      style={{
                        padding: '6px 16px', borderRadius: 8,
                        background: 'transparent', color: 'var(--color-danger)',
                        border: '1px solid var(--color-danger)', cursor: 'pointer', fontWeight: 600, fontSize: '0.8rem',
                      }}
                    >Decline</button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Agent Activity Feed */}
      <div>
        <h2 style={{ fontSize: '1.1rem', marginBottom: '12px' }}>🔄 Agent Activity Feed</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {recent_activities.length === 0 ? (
            <div style={{
              padding: '24px', textAlign: 'center', color: 'var(--color-text-muted)',
              background: 'var(--color-surface)', borderRadius: 12, fontSize: '0.85rem',
            }}>
              No agent activity yet. Go to <strong>Deals</strong> or <strong>Content</strong> tab to add something for the agents to work on.
            </div>
          ) : (
            recent_activities.map((a: any, i: number) => (
              <div key={a.id || i} className="slide-in" style={{
                display: 'flex', alignItems: 'center', gap: '10px',
                padding: '10px 12px',
                background: 'var(--color-surface)',
                borderRadius: 8,
                fontSize: '0.82rem',
              }}>
                <span style={{ fontSize: '1.1rem' }}>{AGENT_ICONS[a.agent_name] || '⚙️'}</span>
                <span style={{
                  width: 8, height: 8, borderRadius: '50%',
                  background: STATUS_COLORS[a.status] || '#666',
                  flexShrink: 0,
                }} />
                <span style={{ flex: 1 }}>{a.summary}</span>
                <span className="mono" style={{ color: 'var(--color-text-muted)', fontSize: '0.7rem' }}>
                  {new Date(a.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, icon, accent, highlight }: any) {
  return (
    <div style={{
      background: 'var(--color-surface)',
      border: highlight ? '1px solid var(--color-warning)' : '1px solid var(--color-border)',
      borderRadius: 12,
      padding: '16px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
        <span style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</span>
        <span style={{ fontSize: '1rem', opacity: 0.6 }}>{icon}</span>
      </div>
      <div style={{
        fontSize: '1.3rem', fontWeight: 700, fontFamily: 'var(--font-display)',
        color: accent ? 'var(--color-accent)' : 'var(--color-text)',
      }}>
        {value}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════
// DEALS TAB
// ═══════════════════════════════════════

function DealsTab({ deals, onAnalyzeAll, onAnalyze, onReload }: any) {
  const [showAddForm, setShowAddForm] = useState(false);
  const [newDeal, setNewDeal] = useState({
    brand_name: '', brand_type: '', deal_type: 'sponsorship', offer_amount: '', description: '',
  });
  const [adding, setAdding] = useState(false);

  const addDeal = async () => {
    if (!newDeal.brand_name.trim()) return;
    setAdding(true);
    try {
      await fetchAPI('/deals', {
        method: 'POST',
        body: JSON.stringify({
          ...newDeal,
          offer_amount: parseFloat(newDeal.offer_amount) || 0,
        }),
      });
      setNewDeal({ brand_name: '', brand_type: '', deal_type: 'sponsorship', offer_amount: '', description: '' });
      setShowAddForm(false);
      onReload();
    } catch (e) {
      console.error(e);
    } finally {
      setAdding(false);
    }
  };

  const deleteDeal = async (id: number) => {
    await fetchAPI(`/deals/${id}`, { method: 'DELETE' });
    onReload();
  };

  const pending = deals?.filter((d: any) => d.status === 'pending_analysis') || [];
  const analyzed = deals?.filter((d: any) => d.status !== 'pending_analysis') || [];

  return (
    <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ fontSize: '1.3rem' }}>Brand Deals</h2>
        <div style={{ display: 'flex', gap: '8px' }}>
          {pending.length > 0 && (
            <button onClick={onAnalyzeAll} style={{
              padding: '8px 20px', borderRadius: 8,
              background: 'var(--color-accent)', color: '#000',
              border: 'none', cursor: 'pointer', fontWeight: 600, fontSize: '0.85rem',
            }}>
              🤝 Analyze {pending.length} Pending
            </button>
          )}
          <button onClick={() => setShowAddForm(!showAddForm)} style={{
            padding: '8px 20px', borderRadius: 8,
            background: showAddForm ? 'var(--color-surface-2)' : 'var(--color-surface)',
            color: showAddForm ? 'var(--color-text-muted)' : 'var(--color-accent)',
            border: showAddForm ? '1px solid var(--color-border)' : '1px solid var(--color-accent)',
            cursor: 'pointer', fontWeight: 600, fontSize: '0.85rem',
          }}>
            {showAddForm ? '✕ Cancel' : '+ Add Deal'}
          </button>
        </div>
      </div>

      {/* Add Deal Form */}
      {showAddForm && (
        <div className="slide-in" style={{
          background: 'var(--color-surface)', border: '1px solid var(--color-accent)',
          borderRadius: 12, padding: '20px',
        }}>
          <h3 style={{ fontSize: '0.95rem', fontWeight: 600, marginBottom: '14px' }}>Add a Brand Deal</h3>
          <p style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', marginBottom: '14px' }}>
            Enter the details of an inbound brand offer. The Deal Agent will analyze it for brand fit, benchmark the price, and negotiate a counter-offer.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Brand Name *</label>
              <input value={newDeal.brand_name} onChange={(e) => setNewDeal({...newDeal, brand_name: e.target.value})} placeholder="e.g. Notion" style={inputStyle} />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Brand Type</label>
              <input value={newDeal.brand_type} onChange={(e) => setNewDeal({...newDeal, brand_type: e.target.value})} placeholder="e.g. software, hardware, food" style={inputStyle} />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Deal Type</label>
              <select value={newDeal.deal_type} onChange={(e) => setNewDeal({...newDeal, deal_type: e.target.value})} style={inputStyle}>
                <option value="sponsorship">Sponsorship</option>
                <option value="collab">Collaboration</option>
                <option value="affiliate">Affiliate</option>
                <option value="ambassador">Ambassador</option>
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Offer Amount ($)</label>
              <input type="number" value={newDeal.offer_amount} onChange={(e) => setNewDeal({...newDeal, offer_amount: e.target.value})} placeholder="5000" style={inputStyle} />
            </div>
          </div>
          <div style={{ marginBottom: '14px' }}>
            <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Description / Brief</label>
            <textarea
              value={newDeal.description}
              onChange={(e) => setNewDeal({...newDeal, description: e.target.value})}
              placeholder="What does the brand want? What content? What deliverables?"
              rows={3}
              style={{ ...inputStyle, resize: 'vertical' }}
            />
          </div>
          <button onClick={addDeal} disabled={adding || !newDeal.brand_name.trim()} style={{
            padding: '10px 24px', borderRadius: 8,
            background: adding ? 'var(--color-surface-2)' : 'var(--color-accent)',
            color: adding ? 'var(--color-text-muted)' : '#000',
            border: 'none', cursor: adding ? 'wait' : 'pointer', fontWeight: 600, fontSize: '0.85rem',
          }}>
            {adding ? 'Adding...' : 'Add Deal →'}
          </button>
        </div>
      )}

      {/* Empty State */}
      {pending.length === 0 && analyzed.length === 0 && !showAddForm && (
        <div style={{
          padding: '40px', textAlign: 'center', background: 'var(--color-surface)',
          borderRadius: 12, border: '1px solid var(--color-border)',
        }}>
          <div style={{ fontSize: '2.5rem', marginBottom: '12px' }}>🤝</div>
          <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '8px' }}>No deals yet</h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)', marginBottom: '16px' }}>
            Add a brand deal and the Deal Agent will analyze it — checking brand fit, benchmarking the price, and proposing a counter-offer.
          </p>
          <button onClick={() => setShowAddForm(true)} style={{
            padding: '10px 24px', borderRadius: 8,
            background: 'var(--color-accent)', color: '#000',
            border: 'none', cursor: 'pointer', fontWeight: 600, fontSize: '0.85rem',
          }}>
            + Add Your First Deal
          </button>
        </div>
      )}

      {pending.length > 0 && (
        <div>
          <h3 style={{ fontSize: '0.9rem', color: 'var(--color-text-muted)', marginBottom: '12px' }}>PENDING ANALYSIS</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '16px' }}>
            {pending.map((d: any) => (
              <div key={d.id} style={{
                background: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: 12, padding: '16px',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                  <div style={{ fontWeight: 600, marginBottom: '4px' }}>{d.brand_name}</div>
                  <button onClick={() => deleteDeal(d.id)} style={{
                    background: 'none', border: 'none', color: 'var(--color-text-muted)',
                    cursor: 'pointer', fontSize: '0.85rem', padding: '0 4px',
                  }}>✕</button>
                </div>
                <div style={{ color: 'var(--color-text-muted)', fontSize: '0.8rem', marginBottom: '8px' }}>
                  {d.brand_type} · {d.deal_type} · ${d.offer_amount?.toLocaleString()}
                </div>
                <div style={{ fontSize: '0.8rem', marginBottom: '12px', color: 'var(--color-text-muted)' }}>
                  {d.description}
                </div>
                <button onClick={() => onAnalyze(d.id)} style={{
                  padding: '6px 14px', borderRadius: 6,
                  background: 'var(--color-surface-2)', color: 'var(--color-accent)',
                  border: '1px solid var(--color-accent)', cursor: 'pointer',
                  fontSize: '0.75rem', fontWeight: 600,
                }}>
                  Run Deal Agent →
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {analyzed.length > 0 && (
        <div>
          <h3 style={{ fontSize: '0.9rem', color: 'var(--color-text-muted)', marginBottom: '12px' }}>ANALYZED BY AGENT</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '16px' }}>
            {analyzed.map((d: any) => (
              <div key={d.id} style={{
                background: 'var(--color-surface)',
                border: `1px solid ${d.status === 'declined' ? 'rgba(248,113,113,0.2)' : d.status === 'approved' ? 'rgba(74,222,128,0.2)' : 'var(--color-border)'}`,
                borderRadius: 12, padding: '16px',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '8px' }}>
                  <div style={{ fontWeight: 600 }}>{d.brand_name}</div>
                  <Badge style={{
                    background: d.status === 'declined' ? 'rgba(248,113,113,0.1)' : d.status === 'approved' ? 'rgba(74,222,128,0.1)' : 'rgba(251,191,36,0.1)',
                    color: d.status === 'declined' ? 'var(--color-danger)' : d.status === 'approved' ? 'var(--color-success)' : 'var(--color-warning)',
                    border: 'none',
                  }}>{d.status}</Badge>
                </div>
                {d.fit_score !== null && d.fit_score !== undefined && (
                  <div style={{ marginBottom: '8px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>
                      <span>Brand Fit</span><span>{(d.fit_score * 100).toFixed(0)}%</span>
                    </div>
                    <div style={{ height: 4, background: 'var(--color-bg)', borderRadius: 2, overflow: 'hidden' }}>
                      <div style={{
                        width: `${d.fit_score * 100}%`, height: '100%',
                        background: d.fit_score > 0.7 ? 'var(--color-success)' : d.fit_score > 0.45 ? 'var(--color-warning)' : 'var(--color-danger)',
                      }} />
                    </div>
                  </div>
                )}
                {d.fit_reasoning && (
                  <div style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', marginBottom: '8px' }}>
                    {d.fit_reasoning}
                  </div>
                )}
                {d.negotiated_amount && (
                  <div style={{ fontSize: '0.8rem', marginTop: '8px', paddingTop: '8px', borderTop: '1px solid var(--color-border)' }}>
                    <span style={{ color: 'var(--color-text-muted)' }}>Negotiated: </span>
                    <span style={{ fontWeight: 600, color: 'var(--color-accent)' }}>${d.negotiated_amount.toLocaleString()}</span>
                    {d.offer_amount && (
                      <span style={{ color: 'var(--color-text-muted)', fontSize: '0.72rem', marginLeft: '8px' }}>
                        (was ${d.offer_amount.toLocaleString()})
                      </span>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════
// CONTENT TAB
// ═══════════════════════════════════════

function ContentTab({ onReload }: { onReload: () => void }) {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newContent, setNewContent] = useState({
    title: '', content_type: 'post', brief: '', platform: 'instagram',
  });
  const [adding, setAdding] = useState(false);

  const loadContent = useCallback(async () => {
    try {
      const d = await fetchAPI('/content');
      setItems(d);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadContent(); }, [loadContent]);

  const draftContent = async (id: number) => {
    await fetchAPI(`/agents/content/draft/${id}`, { method: 'POST' });
    loadContent();
    onReload();
  };

  const addContent = async () => {
    if (!newContent.title.trim()) return;
    setAdding(true);
    try {
      await fetchAPI('/content', {
        method: 'POST',
        body: JSON.stringify(newContent),
      });
      setNewContent({ title: '', content_type: 'post', brief: '', platform: 'instagram' });
      setShowAddForm(false);
      loadContent();
      onReload();
    } catch (e) { console.error(e); }
    finally { setAdding(false); }
  };

  const deleteContent = async (id: number) => {
    await fetchAPI(`/content/${id}`, { method: 'DELETE' });
    loadContent();
    onReload();
  };

  if (loading) return <div style={{ color: 'var(--color-text-muted)' }}>Loading content...</div>;

  return (
    <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ fontSize: '1.3rem' }}>Content Pipeline</h2>
        <button onClick={() => setShowAddForm(!showAddForm)} style={{
          padding: '8px 20px', borderRadius: 8,
          background: showAddForm ? 'var(--color-surface-2)' : 'var(--color-surface)',
          color: showAddForm ? 'var(--color-text-muted)' : 'var(--color-accent)',
          border: showAddForm ? '1px solid var(--color-border)' : '1px solid var(--color-accent)',
          cursor: 'pointer', fontWeight: 600, fontSize: '0.85rem',
        }}>
          {showAddForm ? '✕ Cancel' : '+ Add Content'}
        </button>
      </div>

      {/* Add Content Form */}
      {showAddForm && (
        <div className="slide-in" style={{
          background: 'var(--color-surface)', border: '1px solid var(--color-accent)',
          borderRadius: 12, padding: '20px',
        }}>
          <h3 style={{ fontSize: '0.95rem', fontWeight: 600, marginBottom: '14px' }}>Add Content Brief</h3>
          <p style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', marginBottom: '14px' }}>
            Enter a brief or idea. The Content Agent will draft the full content — optimized for the platform, with hashtags, captions, and notes.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Title *</label>
              <input value={newContent.title} onChange={(e) => setNewContent({...newContent, title: e.target.value})} placeholder="e.g. Behind the scenes of our latest product launch" style={inputStyle} />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Content Type</label>
              <select value={newContent.content_type} onChange={(e) => setNewContent({...newContent, content_type: e.target.value})} style={inputStyle}>
                <option value="post">Post</option>
                <option value="video">Video</option>
                <option value="reel">Reel</option>
                <option value="story">Story</option>
                <option value="carousel">Carousel</option>
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Platform</label>
              <select value={newContent.platform} onChange={(e) => setNewContent({...newContent, platform: e.target.value})} style={inputStyle}>
                <option value="instagram">Instagram</option>
                <option value="youtube">YouTube</option>
                <option value="tiktok">TikTok</option>
                <option value="twitter">Twitter/X</option>
                <option value="linkedin">LinkedIn</option>
                <option value="blog">Blog</option>
              </select>
            </div>
          </div>
          <div style={{ marginBottom: '14px' }}>
            <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Brief / Description</label>
            <textarea
              value={newContent.brief}
              onChange={(e) => setNewContent({...newContent, brief: e.target.value})}
              placeholder="What should the content be about? Key points, call-to-action, tone, any specific requirements..."
              rows={4}
              style={{ ...inputStyle, resize: 'vertical' }}
            />
          </div>
          <button onClick={addContent} disabled={adding || !newContent.title.trim()} style={{
            padding: '10px 24px', borderRadius: 8,
            background: adding ? 'var(--color-surface-2)' : 'var(--color-accent)',
            color: adding ? 'var(--color-text-muted)' : '#000',
            border: 'none', cursor: adding ? 'wait' : 'pointer', fontWeight: 600, fontSize: '0.85rem',
          }}>
            {adding ? 'Adding...' : 'Add Content →'}
          </button>
        </div>
      )}

      {/* Empty State */}
      {items.length === 0 && !showAddForm && (
        <div style={{
          padding: '40px', textAlign: 'center', background: 'var(--color-surface)',
          borderRadius: 12, border: '1px solid var(--color-border)',
        }}>
          <div style={{ fontSize: '2.5rem', marginBottom: '12px' }}>✍️</div>
          <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '8px' }}>No content yet</h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)', marginBottom: '16px' }}>
            Add a content brief and the Content Agent will draft the full post — optimized for the platform with hashtags, captions, and creator notes.
          </p>
          <button onClick={() => setShowAddForm(true)} style={{
            padding: '10px 24px', borderRadius: 8,
            background: 'var(--color-accent)', color: '#000',
            border: 'none', cursor: 'pointer', fontWeight: 600, fontSize: '0.85rem',
          }}>
            + Add Your First Content
          </button>
        </div>
      )}

      {/* Content Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(350px, 1fr))', gap: '16px' }}>
        {items.map((c: any) => (
          <div key={c.id} style={{
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            borderRadius: 12, padding: '16px',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '8px' }}>
              <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{c.title}</div>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <Badge style={{
                  background: c.status === 'published' ? 'rgba(74,222,128,0.1)' : c.status === 'draft_ready' ? 'rgba(251,191,36,0.1)' : 'rgba(138,134,128,0.1)',
                  color: c.status === 'published' ? 'var(--color-success)' : c.status === 'draft_ready' ? 'var(--color-warning)' : 'var(--color-text-muted)',
                  border: 'none',
                }}>{c.status.replace('_', ' ')}</Badge>
                <button onClick={() => deleteContent(c.id)} style={{
                  background: 'none', border: 'none', color: 'var(--color-text-muted)',
                  cursor: 'pointer', fontSize: '0.85rem', padding: '0 4px',
                }}>✕</button>
              </div>
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginBottom: '8px' }}>
              {c.platform} · {c.content_type}
            </div>
            {c.brief && (
              <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', marginBottom: '8px' }}>
                <strong>Brief:</strong> {c.brief.slice(0, 120)}{c.brief.length > 120 ? '...' : ''}
              </div>
            )}
            {c.draft && (
              <div style={{
                background: 'var(--color-bg)', borderRadius: 8, padding: '12px',
                fontSize: '0.8rem', marginBottom: '8px', whiteSpace: 'pre-wrap',
                maxHeight: 200, overflow: 'auto',
                border: '1px solid var(--color-border)',
              }}>
                {c.draft}
              </div>
            )}
            {c.status === 'brief' && (
              <button onClick={() => draftContent(c.id)} style={{
                padding: '6px 14px', borderRadius: 6,
                background: 'var(--color-surface-2)', color: 'var(--color-accent)',
                border: '1px solid var(--color-accent)', cursor: 'pointer',
                fontSize: '0.75rem', fontWeight: 600,
              }}>
                ✍️ Run Content Agent →
              </button>
            )}
            {c.agent_reasoning && (
              <div style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)', marginTop: '8px', fontStyle: 'italic' }}>
                {c.agent_reasoning}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════
// STOREFRONT TAB
// ═══════════════════════════════════════

function StorefrontTab({ products, stats, onReload }: any) {
  const [showAddForm, setShowAddForm] = useState(false);
  const [newProduct, setNewProduct] = useState({ title: '', description: '', price: '', category: '', image_emoji: '📦' });
  const [adding, setAdding] = useState(false);

  const addProduct = async () => {
    if (!newProduct.title.trim()) return;
    setAdding(true);
    try {
      await fetchAPI('/products', {
        method: 'POST',
        body: JSON.stringify({
          ...newProduct,
          price: parseFloat(newProduct.price) || 0,
          sales_count: 0,
        }),
      });
      setNewProduct({ title: '', description: '', price: '', category: '', image_emoji: '📦' });
      setShowAddForm(false);
      onReload();
    } catch (e) { console.error(e); }
    finally { setAdding(false); }
  };

  const deleteProduct = async (id: number) => {
    await fetchAPI(`/products/${id}`, { method: 'DELETE' });
    onReload();
  };

  return (
    <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: '1.3rem' }}>Storefront</h2>
          <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>Your products and digital goods</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Total Revenue</div>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-accent)', fontFamily: 'var(--font-display)' }}>
              ${stats.total_product_revenue.toLocaleString()}
            </div>
          </div>
          <button onClick={() => setShowAddForm(!showAddForm)} style={{
            padding: '8px 20px', borderRadius: 8,
            background: showAddForm ? 'var(--color-surface-2)' : 'var(--color-surface)',
            color: showAddForm ? 'var(--color-text-muted)' : 'var(--color-accent)',
            border: showAddForm ? '1px solid var(--color-border)' : '1px solid var(--color-accent)',
            cursor: 'pointer', fontWeight: 600, fontSize: '0.85rem',
          }}>
            {showAddForm ? '✕ Cancel' : '+ Add Product'}
          </button>
        </div>
      </div>

      {/* Add Product Form */}
      {showAddForm && (
        <div className="slide-in" style={{
          background: 'var(--color-surface)', border: '1px solid var(--color-accent)',
          borderRadius: 12, padding: '20px',
        }}>
          <h3 style={{ fontSize: '0.95rem', fontWeight: 600, marginBottom: '14px' }}>Add a Product</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Title *</label>
              <input value={newProduct.title} onChange={(e) => setNewProduct({...newProduct, title: e.target.value})} placeholder="e.g. Ultimate Guide to X" style={inputStyle} />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Price ($)</label>
              <input type="number" value={newProduct.price} onChange={(e) => setNewProduct({...newProduct, price: e.target.value})} placeholder="49" style={inputStyle} />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Category</label>
              <input value={newProduct.category} onChange={(e) => setNewProduct({...newProduct, category: e.target.value})} placeholder="e.g. course, ebook, template" style={inputStyle} />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Emoji Icon</label>
              <input value={newProduct.image_emoji} onChange={(e) => setNewProduct({...newProduct, image_emoji: e.target.value})} placeholder="📦" style={{ ...inputStyle, maxWidth: 60 }} />
            </div>
          </div>
          <div style={{ marginBottom: '14px' }}>
            <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--color-text-muted)', marginBottom: '4px' }}>Description</label>
            <textarea value={newProduct.description} onChange={(e) => setNewProduct({...newProduct, description: e.target.value})} placeholder="What is this product about?" rows={2} style={{ ...inputStyle, resize: 'vertical' }} />
          </div>
          <button onClick={addProduct} disabled={adding || !newProduct.title.trim()} style={{
            padding: '10px 24px', borderRadius: 8,
            background: adding ? 'var(--color-surface-2)' : 'var(--color-accent)',
            color: adding ? 'var(--color-text-muted)' : '#000',
            border: 'none', cursor: adding ? 'wait' : 'pointer', fontWeight: 600, fontSize: '0.85rem',
          }}>
            {adding ? 'Adding...' : 'Add Product →'}
          </button>
        </div>
      )}

      {/* Products Grid */}
      {products.length === 0 && !showAddForm ? (
        <div style={{
          padding: '40px', textAlign: 'center', background: 'var(--color-surface)',
          borderRadius: 12, border: '1px solid var(--color-border)',
        }}>
          <div style={{ fontSize: '2.5rem', marginBottom: '12px' }}>📦</div>
          <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '8px' }}>No products yet</h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)', marginBottom: '16px' }}>
            Add your digital products, courses, or services to track sales and revenue.
          </p>
          <button onClick={() => setShowAddForm(true)} style={{
            padding: '10px 24px', borderRadius: 8,
            background: 'var(--color-accent)', color: '#000',
            border: 'none', cursor: 'pointer', fontWeight: 600, fontSize: '0.85rem',
          }}>
            + Add Your First Product
          </button>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '16px' }}>
          {products.map((p: any) => (
            <div key={p.id} style={{
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: 12, overflow: 'hidden',
            }}>
              <div style={{
                height: 100, background: 'var(--color-surface-2)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '2.5rem', position: 'relative',
              }}>
                {p.image_emoji}
                <button onClick={() => deleteProduct(p.id)} style={{
                  position: 'absolute', top: 8, right: 8,
                  background: 'rgba(0,0,0,0.5)', border: 'none', borderRadius: 6,
                  color: 'var(--color-text-muted)', cursor: 'pointer', fontSize: '0.8rem',
                  padding: '2px 8px',
                }}>✕</button>
              </div>
              <div style={{ padding: '16px' }}>
                <div style={{ fontWeight: 600, fontSize: '0.9rem', marginBottom: '4px' }}>{p.title}</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginBottom: '12px' }}>
                  {p.description?.slice(0, 80)}{p.description?.length > 80 ? '...' : ''}
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ fontWeight: 700, fontSize: '1.1rem', color: 'var(--color-accent)' }}>
                    ${p.price}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                    {p.sales_count.toLocaleString()} sold
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════
// MEMORY TAB
// ═══════════════════════════════════════

function MemoryTab({ patterns, onLearn }: any) {
  return (
    <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: '1.3rem' }}>Performance Memory</h2>
          <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
            Patterns learned from your deal history and content performance
          </div>
        </div>
        <button onClick={onLearn} style={{
          padding: '8px 20px', borderRadius: 8,
          background: 'var(--color-accent)', color: '#000',
          border: 'none', cursor: 'pointer', fontWeight: 600, fontSize: '0.85rem',
        }}>
          🧠 Run Memory Agent
        </button>
      </div>

      {patterns.length === 0 ? (
        <div style={{
          padding: '40px', textAlign: 'center', background: 'var(--color-surface)',
          borderRadius: 12, border: '1px solid var(--color-border)',
        }}>
          <div style={{ fontSize: '2.5rem', marginBottom: '12px' }}>🧠</div>
          <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '8px' }}>No patterns learned yet</h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)', marginBottom: '16px' }}>
            The Memory Agent analyzes your deals and content to extract patterns — what brands fit best, what price ranges work, what content performs.
            <br/><br/>
            Add some deals and content first, then run the Memory Agent to learn from them.
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {patterns.map((p: any) => (
            <div key={p.id} style={{
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: 12, padding: '16px',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '8px' }}>
                <div>
                  <Badge style={{
                    background: 'rgba(255,87,34,0.1)', color: 'var(--color-accent)', border: 'none',
                  }}>{p.pattern_type.replace('_', ' ')}</Badge>
                  <span style={{ marginLeft: '8px', fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
                    {p.pattern_key}
                  </span>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontWeight: 700, fontSize: '0.9rem' }}>{p.pattern_value}</div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)' }}>
                    {p.sample_count} samples · {(p.confidence * 100).toFixed(0)}% confidence
                  </div>
                </div>
              </div>
              <div style={{ fontSize: '0.82rem', color: 'var(--color-text)' }}>{p.insight}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════
// AGENTS TAB
// ═══════════════════════════════════════

function AgentsTab({ activities, thinking }: any) {
  const agentInfo = [
    { name: 'deal_agent', display: 'Deal Agent', icon: '🤝', desc: 'Researches brands on the web, analyzes market rates, scores brand fit, negotiates counter-offers, generates proposal documents, creates invoices' },
    { name: 'content_agent', display: 'Content Agent', icon: '✍️', desc: 'Researches trending topics, searches YouTube for popular content, writes full platform-optimized drafts, generates content calendars' },
    { name: 'finance_agent', display: 'Finance Agent', icon: '💰', desc: 'Auto-generates invoices from approved deals, researches tax rates, generates financial reports, tracks payments' },
    { name: 'memory_agent', display: 'Memory Agent', icon: '🧠', desc: 'Analyzes all deals and content, researches industry trends, extracts patterns, stores insights for future agent decisions' },
  ];

  return (
    <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <h2 style={{ fontSize: '1.3rem' }}>Agent Orchestra</h2>

      {/* What is this */}
      <div style={{
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 12, padding: '20px',
      }}>
        <h3 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '10px' }}>How It Works</h3>
        <div style={{ fontSize: '0.82rem', color: 'var(--color-text-muted)', lineHeight: 1.7 }}>
          Four AI agents work together autonomously. Each agent uses a <strong>ReAct (Reason + Act) loop</strong> — it plans which tools to use, executes them (web search, market research, document generation), analyzes the results with AI, and takes real actions.
          When a deal is approved, the Finance Agent auto-generates an invoice and the Content Agent auto-schedules content. Nothing goes out without your sign-off.
        </div>
        <div style={{ marginTop: '12px', display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
          {['🌐 web_search', '📺 youtube_search', '📊 market_rate_research', '🔍 competitor_analysis', '📄 generate_document', '💳 create_invoice', '📅 create_content_calendar', '🧠 store_memory'].map(t => (
            <code key={t} style={{ fontSize: '0.68rem', padding: '3px 8px', background: 'var(--color-bg)', borderRadius: 4, color: 'var(--color-text-muted)' }}>{t}</code>
          ))}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '16px' }}>
        {agentInfo.map(a => {
          const agentActivities = activities.filter((act: any) => act.agent_name === a.name);
          return (
            <div key={a.name} style={{
              background: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: 12, padding: '16px',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                <span style={{ fontSize: '1.5rem' }}>{a.icon}</span>
                <div>
                  <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{a.display}</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <span className="pulse-dot" style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--color-success)' }} />
                    <span style={{ fontSize: '0.7rem', color: 'var(--color-success)' }}>active</span>
                  </div>
                </div>
              </div>
              <div style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', marginBottom: '12px' }}>
                {a.desc}
              </div>
              <div style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)' }}>
                {agentActivities.length} actions logged
              </div>
            </div>
          );
        })}
      </div>

      {/* Agent Thinking Process */}
      {thinking && thinking.length > 0 && (
        <div>
          <h3 style={{ fontSize: '1rem', marginBottom: '12px' }}>🧠 Live Agent Thinking</h3>
          <div style={{
            background: 'var(--color-surface)', border: '1px solid var(--color-border)',
            borderRadius: 12, padding: '16px', maxHeight: '400px', overflow: 'auto',
          }}>
            {thinking.map((t: any, i: number) => (
              <div key={t.id || i} className="slide-in" style={{
                display: 'flex', alignItems: 'start', gap: '10px',
                padding: '10px 0', borderBottom: i < thinking.length - 1 ? '1px solid var(--color-border)' : 'none',
              }}>
                <span style={{ fontSize: '1.1rem', flexShrink: 0 }}>
                  {PHASE_ICONS[t.phase] || '💭'}
                </span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)', marginBottom: '2px' }}>
                    {AGENT_ICONS[t.agent_name] || '🤖'} {t.agent_name.replace(/_/g, ' ')} · {t.phase.replace(/_/g, ' ')} · step {t.step_number}
                  </div>
                  <div style={{ fontSize: '0.82rem', color: 'var(--color-text)' }}>{t.thought}</div>
                </div>
                <span className="mono" style={{ fontSize: '0.68rem', color: 'var(--color-text-muted)', flexShrink: 0 }}>
                  {new Date(t.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Activity Feed */}
      <div>
        <h3 style={{ fontSize: '1rem', marginBottom: '12px' }}>Live Activity Feed</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {activities.length === 0 ? (
            <div style={{
              padding: '24px', textAlign: 'center', color: 'var(--color-text-muted)',
              background: 'var(--color-surface)', borderRadius: 12, fontSize: '0.85rem',
            }}>
              No agent activity yet. Add deals or content to see the agents in action.
            </div>
          ) : (
            activities.map((a: any, i: number) => (
              <div key={a.id || i} className="slide-in" style={{
                display: 'flex', alignItems: 'center', gap: '10px',
                padding: '10px 12px',
                background: 'var(--color-surface)', borderRadius: 8, fontSize: '0.82rem',
              }}>
                <span style={{ fontSize: '1.1rem' }}>{AGENT_ICONS[a.agent_name] || '⚙️'}</span>
                <span style={{
                  width: 8, height: 8, borderRadius: '50%',
                  background: STATUS_COLORS[a.status] || '#666', flexShrink: 0,
                }} />
                <span style={{ flex: 1 }}>{a.summary}</span>
                <span className="mono" style={{ color: 'var(--color-text-muted)', fontSize: '0.7rem' }}>
                  {new Date(a.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════
// DOCUMENTS TAB
// ═══════════════════════════════════════

function DocumentsTab({ documents, onReload }: any) {
  const [selectedDoc, setSelectedDoc] = useState<any>(null);

  return (
    <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div>
        <h2 style={{ fontSize: '1.3rem' }}>Generated Documents</h2>
        <div style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', marginTop: '4px' }}>
          Documents automatically generated by agents — contracts, proposals, invoices, reports
        </div>
      </div>

      {documents.length === 0 ? (
        <div style={{
          padding: '40px', textAlign: 'center', background: 'var(--color-surface)',
          borderRadius: 12, border: '1px solid var(--color-border)',
        }}>
          <div style={{ fontSize: '2.5rem', marginBottom: '12px' }}>📄</div>
          <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '8px' }}>No documents yet</h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)' }}>
            When agents process deals and content, they automatically generate documents like
            counter-offer proposals, contracts, invoices, and content strategy reports.
            <br/><br/>
            Add a deal and run the Deal Agent to see documents appear here.
          </p>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '16px' }}>
          {/* Document List */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {documents.map((d: any) => (
              <div
                key={d.id}
                onClick={() => setSelectedDoc(d)}
                style={{
                  background: selectedDoc?.id === d.id ? 'var(--color-surface-2)' : 'var(--color-surface)',
                  border: selectedDoc?.id === d.id ? '1px solid var(--color-accent)' : '1px solid var(--color-border)',
                  borderRadius: 12, padding: '14px', cursor: 'pointer',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                  <span style={{ fontSize: '1.1rem' }}>
                    {d.doc_type === 'contract' ? '📋' : d.doc_type === 'proposal' ? '📝' :
                     d.doc_type === 'invoice' ? '💰' : d.doc_type === 'report' ? '📊' :
                     d.doc_type === 'email' ? '📧' : '📄'}
                  </span>
                  <Badge style={{
                    background: 'rgba(255,87,34,0.1)', color: 'var(--color-accent)', border: 'none',
                    fontSize: '0.65rem', textTransform: 'uppercase',
                  }}>{d.doc_type}</Badge>
                </div>
                <div style={{ fontWeight: 600, fontSize: '0.82rem', marginBottom: '4px' }}>{d.title}</div>
                <div style={{ fontSize: '0.68rem', color: 'var(--color-text-muted)' }}>
                  {new Date(d.created_at).toLocaleDateString()} · {new Date(d.created_at).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})}
                </div>
              </div>
            ))}
          </div>

          {/* Document Preview */}
          <div style={{
            background: 'var(--color-surface)', border: '1px solid var(--color-border)',
            borderRadius: 12, padding: '24px', minHeight: '400px',
          }}>
            {selectedDoc ? (
              <div>
                <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '8px' }}>{selectedDoc.title}</h3>
                <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
                  <Badge style={{ background: 'rgba(255,87,34,0.1)', color: 'var(--color-accent)', border: 'none' }}>
                    {selectedDoc.doc_type}
                  </Badge>
                  <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                    Generated: {new Date(selectedDoc.created_at).toLocaleString()}
                  </span>
                </div>
                <div style={{
                  background: 'var(--color-bg)', borderRadius: 8, padding: '20px',
                  fontSize: '0.85rem', lineHeight: 1.7, whiteSpace: 'pre-wrap',
                  maxHeight: '500px', overflow: 'auto', border: '1px solid var(--color-border)',
                }}>
                  {selectedDoc.content}
                </div>
              </div>
            ) : (
              <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                height: '400px', color: 'var(--color-text-muted)', fontSize: '0.85rem',
              }}>
                Select a document to preview
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════
// AI PROVIDERS TAB
// ═══════════════════════════════════════

function ProvidersTab({
  providers, activeProvider, keyProvider, setKeyProvider,
  keyValue, setKeyValue, onAddKey, onRemoveKey, keyMsg
}: any) {
  return (
    <div style={{ maxWidth: 800, margin: '0 auto' }}>
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: '1.3rem', fontWeight: 700, marginBottom: 8 }}>🤖 AI Provider Configuration</h2>
        <p style={{ fontSize: '0.85rem', color: 'var(--color-text-muted)', lineHeight: 1.6 }}>
          CreatorForge uses multiple AI providers with automatic failover. When one provider hits a rate limit or error,
          the system automatically switches to the next. All providers below are <strong>free</strong> — no credit card required.
          The <code>llm7-free</code> provider works without any key, so the system always has AI available.
        </p>
      </div>

      {/* Add Key Form */}
      <div style={{
        background: 'var(--color-surface)', border: '1px solid var(--color-border)',
        borderRadius: 12, padding: 20, marginBottom: 24,
      }}>
        <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 12 }}>Add Provider API Key (Optional)</h3>
        <p style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', marginBottom: '12px' }}>
          The system works out of the box with the free LLM7 provider. Adding a key (e.g. Groq) makes the AI faster and more capable.
        </p>
        <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
          <select
            value={keyProvider}
            onChange={(e) => setKeyProvider(e.target.value)}
            style={{
              padding: '10px 12px', background: 'var(--color-bg)', border: '1px solid var(--color-border)',
              borderRadius: 8, color: 'var(--color-text)', fontSize: '0.85rem', minWidth: 160,
            }}
          >
            {Object.entries(PROVIDER_INFO).filter(([k]) => k !== 'llm7-free').map(([key, info]) => (
              <option key={key} value={key}>{info.label}</option>
            ))}
          </select>
          <input
            type="password"
            placeholder="Paste your API key here..."
            value={keyValue}
            onChange={(e) => setKeyValue(e.target.value)}
            style={{
              flex: 1, padding: '10px 12px', background: 'var(--color-bg)', border: '1px solid var(--color-border)',
              borderRadius: 8, color: 'var(--color-text)', fontSize: '0.85rem',
            }}
          />
          <button
            onClick={onAddKey}
            style={{
              padding: '10px 20px', background: 'var(--color-accent)', color: '#000',
              border: 'none', borderRadius: 8, fontWeight: 600, fontSize: '0.85rem', cursor: 'pointer',
            }}
          >
            Add Key
          </button>
        </div>
        {keyMsg && (
          <div style={{ fontSize: '0.82rem', color: keyMsg.startsWith('❌') ? 'var(--color-danger)' : 'var(--color-success)', marginTop: 8 }}>
            {keyMsg}
          </div>
        )}
        {keyProvider && PROVIDER_INFO[keyProvider] && PROVIDER_INFO[keyProvider].signupUrl && (
          <div style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', marginTop: 8 }}>
            Get a free key: <a href={PROVIDER_INFO[keyProvider].signupUrl} target="_blank" rel="noopener" style={{ color: 'var(--color-accent)' }}>{PROVIDER_INFO[keyProvider].signupUrl}</a>
            {' '}— {PROVIDER_INFO[keyProvider].description}
          </div>
        )}
      </div>

      {/* Provider List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {providers.map((p: LLMProvider) => {
          const info = PROVIDER_INFO[p.name] || { label: p.name, description: '', signupUrl: '', free: false };
          const isActive = activeProvider === p.name;
          const hasKey = !p.needs_key || p.total_calls > 0 || !p.last_error.includes('Auth');
          return (
            <div key={p.name} style={{
              background: 'var(--color-surface)', border: `1px solid ${isActive ? 'var(--color-accent)' : 'var(--color-border)'}`,
              borderRadius: 12, padding: 16, opacity: p.is_rate_limited ? 0.6 : 1,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>{info.label}</span>
                  {isActive && (
                    <Badge style={{ background: 'rgba(255,87,34,0.15)', color: 'var(--color-accent)', border: '1px solid rgba(255,87,34,0.3)', fontSize: '0.68rem' }}>
                      ● ACTIVE
                    </Badge>
                  )}
                  {p.is_rate_limited && (
                    <Badge style={{ background: 'rgba(251,191,36,0.15)', color: '#fbbf24', border: '1px solid rgba(251,191,36,0.3)', fontSize: '0.68rem' }}>
                      ⏳ RATE LIMITED ({p.rate_limit_expires_in}s)
                    </Badge>
                  )}
                  {!p.needs_key && (
                    <Badge style={{ background: 'rgba(74,222,128,0.15)', color: 'var(--color-success)', border: '1px solid rgba(74,222,128,0.3)', fontSize: '0.68rem' }}>
                      NO KEY NEEDED
                    </Badge>
                  )}
                </div>
                {p.needs_key && hasKey && (
                  <button
                    onClick={() => onRemoveKey(p.name)}
                    style={{
                      padding: '4px 10px', background: 'transparent', border: '1px solid var(--color-border)',
                      borderRadius: 6, color: 'var(--color-text-muted)', fontSize: '0.72rem', cursor: 'pointer',
                    }}
                  >
                    Remove Key
                  </button>
                )}
              </div>
              <div style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', marginBottom: 8 }}>
                {info.description}
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 8 }}>
                {p.models.map((m: string) => (
                  <code key={m} style={{ fontSize: '0.7rem', padding: '2px 6px', background: 'var(--color-bg)', borderRadius: 4, color: 'var(--color-text-muted)' }}>
                    {m}
                  </code>
                ))}
              </div>
              <div style={{ display: 'flex', gap: 16, fontSize: '0.72rem', color: 'var(--color-text-muted)' }}>
                <span>📊 {p.total_calls} calls</span>
                {p.total_errors > 0 && <span style={{ color: 'var(--color-danger)' }}>⚠️ {p.total_errors} errors</span>}
                {info.signupUrl && (
                  <a href={info.signupUrl} target="_blank" rel="noopener" style={{ color: 'var(--color-accent)' }}>
                    Get free key →
                  </a>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Info Box */}
      <div style={{
        marginTop: 24, padding: 16, background: 'rgba(255,87,34,0.05)',
        border: '1px solid rgba(255,87,34,0.2)', borderRadius: 12,
      }}>
        <h4 style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: 8 }}>💡 How Multi-Provider Failover Works</h4>
        <ul style={{ fontSize: '0.78rem', color: 'var(--color-text-muted)', lineHeight: 1.8, paddingLeft: 20, margin: 0 }}>
          <li>When you add a key (e.g., Groq), it becomes the <strong>first choice</strong> — faster and more powerful</li>
          <li>If that provider hits a rate limit (429), the system waits 60s and tries the <strong>next provider</strong></li>
          <li><code>llm7-free</code> is always last in the chain — no key needed, always available</li>
          <li>If all LLM providers fail, agents fall back to <strong>rule-based reasoning</strong> (never breaks)</li>
          <li>Add multiple keys for maximum reliability — the system handles everything automatically</li>
        </ul>
      </div>
    </div>
  );
}
