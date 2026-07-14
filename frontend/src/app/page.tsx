'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { fetchAPI } from '@/lib/api';

// ═══════════════════════════════════════
// TYPES & CONSTANTS
// ═══════════════════════════════════════

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

const PHASE_ICONS: Record<string, string> = {
  data_gathering: '📥', context_loading: '🧠', ai_analysis: '🤖',
  ai_writing: '🤖', ai_generating: '🤖', ai_calling: '⌛',
  strategy: '🎨', pattern_mining: '🔍', result: '\u2705',
  planning: '🧠', plan_ready: '📋', tool_call: '🔧',
  tool_result: '📊', analyzing: '🔬', task_received: '📨',
  error: '\u274C', max_iterations: '\u23F0',
};

const INDUSTRIES = ['tech', 'music', 'fitness', 'beauty', 'food', 'fashion', 'gaming', 'travel', 'education', 'business', 'lifestyle', 'health'];

const STATUS_COLORS: Record<string, string> = {
  completed: '#16a34a', started: '#f59e0b', awaiting_approval: '#f59e0b',
  approved: '#16a34a', declined: '#dc2626', pending_analysis: '#2337f1',
  pending: '#f59e0b', active: '#16a34a',
};

// Fox-spark SVG component
function FoxSpark({ size = 16, color = '#ee4d1f' }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill={color} style={{ display: 'inline-block', verticalAlign: 'middle' }}>
      <path d="M12 1.5c.41 4.7 1.8 6.09 6.5 6.5-4.7.41-6.09 1.8-6.5 6.5-.41-4.7-1.8-6.09-6.5-6.5 4.7-.41 6.09-1.8 6.5-6.5z"/>
    </svg>
  );
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '10px 14px', background: 'var(--bg-sunken)',
  border: '1px solid var(--border)', borderRadius: 'var(--r-sm)',
  color: 'var(--fg)', fontSize: '0.85rem', fontFamily: 'var(--font-sans)',
  outline: 'none', transition: 'border-color 0.2s',
};
const inputFocusStyle = 'input:focus, select:focus, textarea:focus { border-color: var(--kit-fox); }';

const cardStyle: React.CSSProperties = {
  background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 'var(--r-md)', padding: 'var(--sp-6)',
};
const darkCardStyle: React.CSSProperties = {
  background: 'var(--dark-bg-elev)', border: '1px solid var(--dark-border)', borderRadius: 'var(--r-md)',
  color: 'var(--dark-fg)', padding: 'var(--sp-6)',
};

// ═══════════════════════════════════════
// MAIN DASHBOARD
// ═══════════════════════════════════════

export default function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'overview' | 'deals' | 'content' | 'storefront' | 'memory' | 'agents' | 'documents' | 'platforms' | 'providers'>('overview');
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  const [activeProvider, setActiveProvider] = useState('');
  const [keyProvider, setKeyProvider] = useState('groq');
  const [keyValue, setKeyValue] = useState('');
  const [keyMsg, setKeyMsg] = useState('');
  const [thinking, setThinking] = useState<any[]>([]);
  const [runningAgent, setRunningAgent] = useState<string | null>(null);
  const [scrolled, setScrolled] = useState(false);

  const loadProviders = useCallback(async () => {
    try {
      const d = await fetchAPI('/llm/providers');
      setProviders(d.providers || []);
      setActiveProvider(d.active_provider || '');
    } catch (e) { console.error(e); }
  }, []);

  const load = useCallback(async () => {
    try {
      const d = await fetchAPI('/dashboard');
      setData(d);
      if (d.recent_thinking) setThinking(d.recent_thinking);
    } catch (e) { console.error(e); } finally { setLoading(false); }
  }, []);

  useEffect(() => {
    load(); loadProviders();
    const interval = setInterval(load, 3000);
    return () => clearInterval(interval);
  }, [load, loadProviders]);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', onScroll);
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const handleApprove = async (id: number) => { await fetchAPI(`/approvals/${id}/resolve?decision=approved`, { method: 'POST' }); load(); };
  const handleDecline = async (id: number) => { await fetchAPI(`/approvals/${id}/resolve?decision=declined`, { method: 'POST' }); load(); };

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
    await load(); setRunningAgent(null);
  };

  const addProviderKey = async () => {
    if (!keyValue.trim()) { setKeyMsg('Please enter an API key'); return; }
    try {
      setKeyMsg('Adding key...');
      await fetchAPI('/llm/providers/key', { method: 'POST', body: JSON.stringify({ provider: keyProvider, api_key: keyValue.trim() }) });
      setKeyValue('');
      setKeyMsg(`Key added for ${PROVIDER_INFO[keyProvider]?.label || keyProvider}. System will use it automatically.`);
      loadProviders();
    } catch (e: any) { setKeyMsg(`Error: ${e.message}`); }
  };

  const removeProviderKey = async (provider: string) => {
    try {
      await fetchAPI(`/llm/providers/${provider}`, { method: 'DELETE' });
      setKeyMsg(`Removed ${PROVIDER_INFO[provider]?.label || provider} key`);
      loadProviders();
    } catch (e: any) { setKeyMsg(`Error: ${e.message}`); }
  };

  const resetWorkspace = async () => {
    if (!confirm('Reset everything? This will delete all data.')) return;
    await fetchAPI('/reset', { method: 'POST' });
    window.location.reload();
  };

  // ─── LOADING ───
  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', background: 'var(--bg)' }}>
        <div style={{ textAlign: 'center' }}>
          <FoxSpark size={40} color="#ee4d1f" />
          <div style={{ fontFamily: 'var(--font-display)', fontSize: '2rem', marginTop: '16px' }}>
            Creator<span className="kit-grad-text">Forge</span>
          </div>
          <div className="eyebrow" style={{ marginTop: '8px' }}>Loading workspace<span className="cursor-blink">_</span></div>
        </div>
      </div>
    );
  }

  // ─── ONBOARDING ───
  if (data?.needs_onboarding) {
    return <OnboardingScreen onOnboarded={() => load()} />;
  }

  const { creator, stats, products, active_deals, pending_approvals, recent_activities, patterns } = data!;

  const TABS = [
    ['overview', 'Overview'], ['deals', 'Deals'], ['content', 'Content'],
    ['storefront', 'Storefront'], ['memory', 'Memory'], ['agents', 'Agents'],
    ['documents', 'Documents'], ['platforms', 'Platforms'], ['providers', 'AI'],
  ] as const;

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)' }}>
      <style>{inputFocusStyle}</style>

      {/* ─── HEADER (Fixed, Kitsune nav) ─── */}
      <header style={{
        position: 'sticky', top: 0, zIndex: 100,
        background: scrolled ? 'rgba(255,255,255,0.92)' : 'rgba(255,255,255,1)',
        backdropFilter: scrolled ? 'blur(10px)' : 'none',
        borderBottom: scrolled ? '1px solid var(--border)' : '1px solid transparent',
        padding: scrolled ? '10px 32px' : '16px 32px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        transition: 'all 200ms var(--ease-out)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <FoxSpark size={22} color="#ee4d1f" />
          <div>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: '1.15rem', letterSpacing: '-0.02em' }}>
              Creator<span className="kit-grad-text">Forge</span>
            </div>
            <div className="eyebrow" style={{ fontSize: '9px' }}>The Agentic OS for Creators</div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          {runningAgent && (
            <div className="status-chip execute">
              <span className="dot" />
              {runningAgent}
            </div>
          )}
          <div className="status-chip live" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span className="dot" />
            <span style={{ fontSize: '11px' }}>12 agents live</span>
          </div>
          {stats?.llm_enabled && (
            <span className="status-chip approved">
              <span className="dot" />
              {activeProvider || 'AI'} active
            </span>
          )}
          <button onClick={resetWorkspace} className="btn-outline" style={{ fontSize: '11px', padding: '6px 14px' }}>
            Reset
          </button>
        </div>
      </header>

      {/* ─── TABS ─── */}
      <nav style={{
        display: 'flex', gap: '0', padding: '0 32px',
        borderBottom: '1px solid var(--border)', overflowX: 'auto',
        background: 'var(--bg)',
      }}>
        {TABS.map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            style={{
              padding: '12px 18px', background: 'none', border: 'none',
              borderBottom: tab === key ? '2px solid var(--kit-fox)' : '2px solid transparent',
              color: tab === key ? 'var(--fg)' : 'var(--fg-3)',
              cursor: 'pointer', fontFamily: 'var(--font-sans)',
              fontSize: '0.85rem', fontWeight: tab === key ? 600 : 400,
              transition: 'color 0.2s, border-color 0.2s',
              whiteSpace: 'nowrap',
            }}
          >
            {label}
          </button>
        ))}
      </nav>

      {/* ─── MAIN ─── */}
      <main style={{ maxWidth: 1248, margin: '0 auto', padding: 'clamp(32px, 5vw, 64px) 32px' }}>
        {tab === 'overview' && (
          <OverviewTab creator={creator} stats={stats} pending_approvals={pending_approvals} recent_activities={recent_activities} thinking={thinking} onApprove={handleApprove} onDecline={handleDecline} />
        )}
        {tab === 'deals' && (
          <DealsTab deals={active_deals} onAnalyzeAll={analyzeAllDeals} onAnalyze={async (id: number) => { setRunningAgent('Deal Agent analyzing...'); await fetchAPI(`/agents/deal/analyze/${id}`, { method: 'POST' }); await load(); setRunningAgent(null); }} onReload={load} />
        )}
        {tab === 'content' && <ContentTab onReload={load} />}
        {tab === 'storefront' && <StorefrontTab products={products} stats={stats} onReload={load} />}
        {tab === 'memory' && <MemoryTab patterns={patterns} onLearn={learnMemory} />}
        {tab === 'agents' && <AgentsTab activities={recent_activities} thinking={thinking} />}
        {tab === 'documents' && <DocumentsTab documents={data?.documents || []} onReload={load} />}
        {tab === 'platforms' && <PlatformsTab />}
        {tab === 'providers' && (
          <ProvidersTab providers={providers} activeProvider={activeProvider} keyProvider={keyProvider} setKeyProvider={setKeyProvider} keyValue={keyValue} setKeyValue={setKeyValue} onAddKey={addProviderKey} onRemoveKey={removeProviderKey} keyMsg={keyMsg} />
        )}
      </main>
    </div>
  );
}

// ═══════════════════════════════════════
// ONBOARDING SCREEN (Kitsune intake terminal)
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
    if (!name.trim() || !handle.trim()) { setError('Please enter your creator name and handle'); return; }
    setSubmitting(true); setError('');
    try {
      await fetchAPI('/onboard', { method: 'POST', body: JSON.stringify({
        company_name: name.trim(), handle: handle.trim().replace('@', ''),
        industry, bio: bio.trim() || `${name.trim()} — ${industry} content creator`,
        followers: parseInt(followers) || 0, monthly_revenue: parseFloat(revenue) || 0,
      })});
      onOnboarded();
    } catch (e: any) { setError(`Error: ${e.message}`); } finally { setSubmitting(false); }
  };

  return (
    <div style={{ minHeight: '100vh', background: 'var(--kit-page-gradient)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
      <div style={{ maxWidth: 560, width: '100%' }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <FoxSpark size={48} color="#ee4d1f" />
          <div style={{ fontFamily: 'var(--font-display)', fontSize: 'clamp(2rem, 4vw, 2.5rem)', marginTop: '12px' }}>
            Creator<span className="kit-grad-text">Forge OS</span>
          </div>
          <div className="eyebrow" style={{ marginTop: '8px' }}>The Agentic Operating System for Creators</div>
        </div>

        {/* What is this */}
        <div style={cardStyle}>
          <h3 style={{ fontSize: '0.95rem', fontWeight: 600, marginBottom: '12px' }}>What is CreatorForge OS?</h3>
          <p style={{ fontSize: '0.82rem', color: 'var(--fg-3)', lineHeight: 1.7, marginBottom: '16px' }}>
            An AI-powered operating system that runs your creator business autonomously. <strong style={{ color: 'var(--fg)' }}>12 AI agents</strong> work together — researching brands, writing content, sending emails, creating invoices, and posting to your platforms.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '0.78rem' }}>
            {[
              ['🤖', '6 Expert Agents', 'Deal, Content, Finance, Memory, Strategy, Outreach'],
              ['⚙️', '6 Worker Agents', 'Publisher, Email, Contract, Analytics, Scheduler, Notify'],
              ['🌐', '28 Real Tools', 'Web search, market research, document generation'],
              ['📸', '8 Platforms', 'Instagram, YouTube, Stripe, Email, Twitter, Slack, GitHub, Telegram'],
            ].map(([icon, title, desc]) => (
              <div key={title} style={{ display: 'flex', gap: '8px', alignItems: 'start' }}>
                <span style={{ fontSize: '1.1rem' }}>{icon}</span>
                <div>
                  <strong style={{ color: 'var(--fg)', fontSize: '0.78rem' }}>{title}</strong>
                  <div style={{ color: 'var(--fg-3)', fontSize: '0.7rem', marginTop: '2px' }}>{desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Intake form */}
        <div style={{ ...cardStyle, marginTop: '16px' }}>
          <div className="eyebrow" style={{ marginBottom: '16px' }}>Work with us</div>
          <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '1.4rem', marginBottom: '20px' }}>Bring us bottlenecks<span className="cursor-blink">_</span></h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div>
              <label className="eyebrow" style={{ display: 'block', marginBottom: '6px' }}>Creator Name *</label>
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Layla Makes" style={inputStyle} />
            </div>
            <div>
              <label className="eyebrow" style={{ display: 'block', marginBottom: '6px' }}>Handle *</label>
              <input value={handle} onChange={(e) => setHandle(e.target.value)} placeholder="e.g. layla.makes" style={inputStyle} />
            </div>
            <div>
              <label className="eyebrow" style={{ display: 'block', marginBottom: '6px' }}>Industry</label>
              <select value={industry} onChange={(e) => setIndustry(e.target.value)} style={inputStyle}>
                {INDUSTRIES.map(i => <option key={i} value={i}>{i.charAt(0).toUpperCase() + i.slice(1)}</option>)}
              </select>
            </div>
            <div>
              <label className="eyebrow" style={{ display: 'block', marginBottom: '6px' }}>Bio</label>
              <textarea value={bio} onChange={(e) => setBio(e.target.value)} placeholder="What do you create?" rows={2} style={{ ...inputStyle, resize: 'vertical' }} />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div>
                <label className="eyebrow" style={{ display: 'block', marginBottom: '6px' }}>Followers</label>
                <input type="number" value={followers} onChange={(e) => setFollowers(e.target.value)} placeholder="184000" style={inputStyle} />
              </div>
              <div>
                <label className="eyebrow" style={{ display: 'block', marginBottom: '6px' }}>Monthly Revenue ($)</label>
                <input type="number" value={revenue} onChange={(e) => setRevenue(e.target.value)} placeholder="12400" style={inputStyle} />
              </div>
            </div>
            {error && <div style={{ fontSize: '0.82rem', color: 'var(--color-danger)' }}>{error}</div>}
            <button onClick={handleSubmit} disabled={submitting} className="btn-terminal" style={{ width: '100%', justifyContent: 'center', padding: '14px', marginTop: '4px' }}>
              {submitting ? 'Setting up workspace...' : 'Start \u2192'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════
// OVERVIEW TAB
// ═══════════════════════════════════════

function OverviewTab({ creator, stats, pending_approvals, recent_activities, thinking, onApprove, onDecline }: any) {
  if (!creator) return null;

  return (
    <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 'clamp(24px, 4vw, 48px)' }}>
      {/* Hero header */}
      <div>
        <div className="eyebrow" style={{ marginBottom: '12px' }}>
          {creator.industry} / {creator.handle}
        </div>
        <h1 style={{ fontSize: 'clamp(36px, 5vw, 64px)', fontFamily: 'var(--font-display)', lineHeight: 0.98 }}>
          {creator.company_name}
        </h1>
        <p style={{ fontSize: 'var(--fs-body-lg)', color: 'var(--fg-3)', maxWidth: '52ch', marginTop: '12px', lineHeight: 1.5 }}>
          {creator.bio || 'No bio set.'}
        </p>
      </div>

      {/* Stats grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '12px' }}>
        <StatCard label="Followers" value={stats?.followers?.toLocaleString() || '0'} icon="👥" accent="fox" />
        <StatCard label="Monthly Revenue" value={`$${(stats?.monthly_revenue || 0).toLocaleString()}`} icon="💰" accent="electric" />
        <StatCard label="Active Deals" value={stats?.active_deals || 0} icon="🤝" accent="indigo" />
        <StatCard label="Pending Approvals" value={pending_approvals?.length || 0} icon="⏳" accent="fox" highlight={pending_approvals?.length > 0} />
        <StatCard label="Total Revenue" value={`$${(stats?.total_revenue || 0).toLocaleString()}`} icon="💸" accent="electric" />
        <StatCard label="AI Agents" value="12" icon="🤖" accent="indigo" />
      </div>

      {/* Pending approvals */}
      {pending_approvals && pending_approvals.length > 0 && (
        <div>
          <div className="eyebrow" style={{ marginBottom: '12px' }}>Awaiting your judgment</div>
          <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 'clamp(24px, 3vw, 36px)', marginBottom: '16px' }}>Approvals</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {pending_approvals.map((a: any) => (
              <div key={a.id} style={{ ...cardStyle, display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 20px' }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{a.summary}</div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--fg-3)', marginTop: '4px' }}>{a.details}</div>
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button onClick={() => onApprove(a.id)} className="btn-terminal" style={{ padding: '8px 16px', fontSize: '11px' }}>Approve</button>
                  <button onClick={() => onDecline(a.id)} className="btn-outline" style={{ padding: '8px 16px', fontSize: '11px' }}>Decline</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Activity + Thinking */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', '@media (max-width: 760px)': { gridTemplateColumns: '1fr' } } as any}>
        {/* Recent Activity */}
        <div>
          <div className="eyebrow" style={{ marginBottom: '12px' }}>Live activity</div>
          <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 'clamp(20px, 2.5vw, 28px)', marginBottom: '16px' }}>Agent Feed</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {(recent_activities || []).slice(0, 12).map((a: any, i: number) => (
              <div key={i} className="slide-in" style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '10px 14px', background: 'var(--bg-sunken)', borderRadius: 'var(--r-sm)', fontSize: '0.8rem' }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: STATUS_COLORS[a.status] || '#9aa1b1', flexShrink: 0 }} />
                <span className="mono" style={{ fontSize: '0.68rem', color: 'var(--fg-3)', textTransform: 'uppercase' }}>{a.agent_name}</span>
                <span style={{ flex: 1, color: 'var(--fg-2)' }}>{a.summary}</span>
                <span className="mono" style={{ color: 'var(--fg-mute)', fontSize: '0.65rem' }}>{new Date(a.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
              </div>
            ))}
            {(!recent_activities || recent_activities.length === 0) && (
              <div style={{ padding: '24px', textAlign: 'center', color: 'var(--fg-mute)', background: 'var(--bg-sunken)', borderRadius: 'var(--r-md)', fontSize: '0.85rem' }}>
                No activity yet. Add deals or content to see agents in action.
              </div>
            )}
          </div>
        </div>

        {/* Agent Thinking */}
        <div>
          <div className="eyebrow" style={{ marginBottom: '12px' }}>ReAct loop</div>
          <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 'clamp(20px, 2.5vw, 28px)', marginBottom: '16px' }}>Agent Thinking</h2>
          <div style={{ background: 'var(--dark-bg)', borderRadius: 'var(--r-md)', padding: '16px', maxHeight: '400px', overflow: 'auto', border: '1px solid var(--dark-border)' }}>
            {(thinking || []).slice(0, 20).map((t: any, i: number) => (
              <div key={i} className="slide-in" style={{ display: 'flex', gap: '10px', padding: '8px 0', borderBottom: i < thinking.length - 1 ? '1px solid var(--dark-border)' : 'none', fontSize: '0.78rem' }}>
                <span style={{ flexShrink: 0, fontSize: '0.9rem' }}>{PHASE_ICONS[t.phase] || '🔹'}</span>
                <div style={{ flex: 1 }}>
                  <div className="mono" style={{ fontSize: '0.62rem', color: 'var(--dark-fg-3)', marginBottom: '2px', textTransform: 'uppercase' }}>
                    {t.agent_name} \u00b7 {t.phase.replace(/_/g, ' ')}
                  </div>
                  <div style={{ color: 'var(--dark-fg-2)' }}>{t.thought}</div>
                </div>
              </div>
            ))}
            {(!thinking || thinking.length === 0) && (
              <div style={{ padding: '24px', textAlign: 'center', color: 'var(--dark-fg-3)', fontSize: '0.85rem' }}>
                Agent thoughts will appear here when agents run.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, icon, accent, highlight }: any) {
  const accentColors: Record<string, string> = { fox: '#ee4d1f', electric: '#2337f1', indigo: '#4b35c8' };
  const color = accentColors[accent] || '#6b7180';
  return (
    <div style={{
      ...cardStyle, padding: '20px',
      borderColor: highlight ? color : 'var(--border)',
      boxShadow: highlight ? `0 4px 20px -8px ${color}40` : 'none',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
        <span className="eyebrow">{label}</span>
        <span style={{ fontSize: '1rem' }}>{icon}</span>
      </div>
      <div style={{ fontFamily: 'var(--font-display)', fontSize: '2rem', lineHeight: 1, color: highlight ? color : 'var(--fg)' }}>
        {value}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════
// DEALS TAB
// ═══════════════════════════════════════

function DealsTab({ deals, onAnalyzeAll, onAnalyze, onReload }: any) {
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ brand_name: '', brand_type: 'tech', deal_type: 'sponsorship', offer_amount: '', description: '' });

  const handleAdd = async () => {
    if (!form.brand_name.trim()) return;
    await fetchAPI('/deals', { method: 'POST', body: JSON.stringify({
      brand_name: form.brand_name.trim(), brand_type: form.brand_type,
      deal_type: form.deal_type, offer_amount: parseFloat(form.offer_amount) || 0,
      description: form.description.trim(),
    })});
    setForm({ brand_name: '', brand_type: 'tech', deal_type: 'sponsorship', offer_amount: '', description: '' });
    setShowForm(false); onReload();
  };

  const dealStatusColor: Record<string, string> = {
    pending_analysis: '#2337f1', analyzed: '#f59e0b', approved: '#16a34a',
    declined: '#dc2626', countered: '#ee4d1f', completed: '#16a34a',
  };

  return (
    <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div className="eyebrow" style={{ marginBottom: '8px' }}>Deal pipeline</div>
          <h1 style={{ fontFamily: 'var(--font-display)', fontSize: 'clamp(32px, 4vw, 48px)' }}>Deals</h1>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          {deals && deals.some((d: any) => d.status === 'pending_analysis') && (
            <button onClick={onAnalyzeAll} className="btn-terminal" style={{ fontSize: '11px', padding: '10px 18px' }}>
              Analyze All \u2192
            </button>
          )}
          <button onClick={() => setShowForm(!showForm)} className="btn-outline" style={{ fontSize: '11px', padding: '10px 18px' }}>
            {showForm ? 'Cancel' : '+ Add Deal'}
          </button>
        </div>
      </div>

      {/* Add form */}
      {showForm && (
        <div style={cardStyle}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px' }}>
              <input value={form.brand_name} onChange={(e) => setForm({ ...form, brand_name: e.target.value })} placeholder="Brand name" style={inputStyle} />
              <select value={form.brand_type} onChange={(e) => setForm({ ...form, brand_type: e.target.value })} style={inputStyle}>
                {['tech', 'fashion', 'food', 'beauty', 'fitness', 'gaming', 'music', 'lifestyle', 'other'].map(t => <option key={t} value={t}>{t}</option>)}
              </select>
              <select value={form.deal_type} onChange={(e) => setForm({ ...form, deal_type: e.target.value })} style={inputStyle}>
                {['sponsorship', 'affiliate', 'product', 'ambassador', 'licensing'].map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: '12px' }}>
              <input type="number" value={form.offer_amount} onChange={(e) => setForm({ ...form, offer_amount: e.target.value })} placeholder="Amount ($)" style={inputStyle} />
              <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Deal description" style={inputStyle} />
            </div>
            <button onClick={handleAdd} className="btn-terminal" style={{ alignSelf: 'flex-start' }}>Add to pipeline</button>
          </div>
        </div>
      )}

      {/* Deal cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '16px' }}>
        {(deals || []).map((deal: any) => (
          <div key={deal.id} style={{ ...cardStyle, borderTop: `3px solid ${dealStatusColor[deal.status] || '#9aa1b1'}` }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '12px' }}>
              <div>
                <div style={{ fontWeight: 700, fontSize: '1rem' }}>{deal.brand_name}</div>
                <div className="eyebrow" style={{ marginTop: '4px' }}>{deal.brand_type} \u00b7 {deal.deal_type}</div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontFamily: 'var(--font-display)', fontSize: '1.4rem' }}>${deal.offer_amount?.toLocaleString()}</div>
                <span className="status-chip" style={{ background: `${dealStatusColor[deal.status]}15`, color: dealStatusColor[deal.status], border: 'none' }}>
                  {deal.status.replace(/_/g, ' ')}
                </span>
              </div>
            </div>
            {deal.description && <div style={{ fontSize: '0.8rem', color: 'var(--fg-3)', marginBottom: '12px', lineHeight: 1.5 }}>{deal.description}</div>}
            {deal.analysis && (
              <div style={{ marginTop: '8px', padding: '12px', background: 'var(--bg-sunken)', borderRadius: 'var(--r-sm)' }}>
                <div style={{ display: 'flex', gap: '16px', marginBottom: '8px' }}>
                  <div><span className="eyebrow">Fit</span> <strong style={{ color: deal.analysis.fit_score > 0.7 ? '#16a34a' : '#f59e0b' }}>{Math.round((deal.analysis.fit_score || 0) * 100)}%</strong></div>
                  {deal.analysis.negotiated_amount && <div><span className="eyebrow">Counter</span> <strong style={{ color: 'var(--kit-fox)' }}>${deal.analysis.negotiated_amount?.toLocaleString()}</strong></div>}
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--fg-3)' }}>{deal.analysis.fit_reasoning?.slice(0, 150)}</div>
                <div className="eyebrow" style={{ marginTop: '8px', color: 'var(--kit-fox)' }}>{deal.analysis.recommendation}</div>
              </div>
            )}
            <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
              {deal.status === 'pending_analysis' && <button onClick={() => onAnalyze(deal.id)} className="btn-terminal" style={{ fontSize: '11px', padding: '6px 14px' }}>Analyze \u2192</button>}
              {deal.status === 'analyzed' && <>
                <button onClick={async () => { await fetchAPI(`/deals/${deal.id}/approve`, { method: 'POST' }); onReload(); }} className="btn-terminal" style={{ fontSize: '11px', padding: '6px 14px' }}>Approve</button>
                <button onClick={async () => { await fetchAPI(`/deals/${deal.id}/decline`, { method: 'POST' }); onReload(); }} className="btn-outline" style={{ fontSize: '11px', padding: '6px 14px' }}>Decline</button>
              </>}
            </div>
          </div>
        ))}
        {(!deals || deals.length === 0) && (
          <div style={{ gridColumn: '1 / -1', padding: '48px', textAlign: 'center', background: 'var(--bg-sunken)', borderRadius: 'var(--r-md)' }}>
            <div style={{ fontSize: '0.9rem', color: 'var(--fg-3)' }}>No deals yet. Add your first brand deal to get started.</div>
          </div>
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════
// CONTENT TAB
// ═══════════════════════════════════════

function ContentTab({ onReload }: { onReload: () => void }) {
  const [items, setItems] = useState<any[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ title: '', platform: 'instagram', content_type: 'post', brief: '', scheduled_date: '' });

  const loadItems = useCallback(async () => {
    try { setItems(await fetchAPI('/content')); } catch {}
  }, []);
  useEffect(() => { loadItems(); }, [loadItems]);

  const handleGenerate = async (id: number) => {
    await fetchAPI(`/agents/content/generate/${id}`, { method: 'POST' });
    loadItems(); onReload();
  };

  const handleAdd = async () => {
    if (!form.title.trim()) return;
    await fetchAPI('/content', { method: 'POST', body: JSON.stringify({
      title: form.title, platform: form.platform, content_type: form.content_type,
      brief: form.brief, scheduled_date: form.scheduled_date || null,
    })});
    setForm({ title: '', platform: 'instagram', content_type: 'post', brief: '', scheduled_date: '' });
    setShowForm(false); loadItems(); onReload();
  };

  const platformIcons: Record<string, string> = { instagram: '📸', youtube: '📹', tiktok: '🎬', twitter: '🕊️', blog: '📝', email: '📧' };

  return (
    <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div className="eyebrow" style={{ marginBottom: '8px' }}>Content pipeline</div>
          <h1 style={{ fontFamily: 'var(--font-display)', fontSize: 'clamp(32px, 4vw, 48px)' }}>Content</h1>
        </div>
        <button onClick={() => setShowForm(!showForm)} className="btn-outline" style={{ fontSize: '11px', padding: '10px 18px' }}>
          {showForm ? 'Cancel' : '+ Add Brief'}
        </button>
      </div>

      {showForm && (
        <div style={cardStyle}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="Content title" style={inputStyle} />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px' }}>
              <select value={form.platform} onChange={(e) => setForm({ ...form, platform: e.target.value })} style={inputStyle}>
                {['instagram', 'youtube', 'tiktok', 'twitter', 'blog', 'email'].map(p => <option key={p} value={p}>{p}</option>)}
              </select>
              <select value={form.content_type} onChange={(e) => setForm({ ...form, content_type: e.target.value })} style={inputStyle}>
                {['post', 'reel', 'video', 'story', 'thread', 'article', 'newsletter'].map(t => <option key={t} value={t}>{t}</option>)}
              </select>
              <input type="date" value={form.scheduled_date} onChange={(e) => setForm({ ...form, scheduled_date: e.target.value })} style={inputStyle} />
            </div>
            <textarea value={form.brief} onChange={(e) => setForm({ ...form, brief: e.target.value })} placeholder="Brief — what should the content cover?" rows={3} style={{ ...inputStyle, resize: 'vertical' }} />
            <button onClick={handleAdd} className="btn-terminal" style={{ alignSelf: 'flex-start' }}>Add brief</button>
          </div>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {items.map((item: any) => (
          <div key={item.id} style={{ ...cardStyle, display: 'flex', gap: '16px', alignItems: 'start' }}>
            <div style={{ fontSize: '1.5rem' }}>{platformIcons[item.platform] || '📄'}</div>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                <strong style={{ fontSize: '0.9rem' }}>{item.title}</strong>
                <span className="status-chip" style={{ background: 'var(--bg-sunken)', color: 'var(--fg-3)', border: 'none' }}>{item.platform} \u00b7 {item.content_type}</span>
              </div>
              {item.brief && <div style={{ fontSize: '0.8rem', color: 'var(--fg-3)', marginBottom: '8px' }}>{item.brief}</div>}
              {item.draft_content && (
                <div style={{ padding: '12px', background: 'var(--bg-sunken)', borderRadius: 'var(--r-sm)', fontSize: '0.78rem', lineHeight: 1.6, color: 'var(--fg-2)', whiteSpace: 'pre-wrap', maxHeight: '200px', overflow: 'auto' }}>
                  {item.draft_content}
                </div>
              )}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {!item.draft_content && <button onClick={() => handleGenerate(item.id)} className="btn-terminal" style={{ fontSize: '10px', padding: '6px 12px' }}>Generate</button>}
              <button onClick={async () => { await fetchAPI(`/content/${item.id}/publish`, { method: 'POST' }); loadItems(); }} className="btn-outline" style={{ fontSize: '10px', padding: '6px 12px' }}>Publish</button>
            </div>
          </div>
        ))}
        {items.length === 0 && (
          <div style={{ padding: '48px', textAlign: 'center', background: 'var(--bg-sunken)', borderRadius: 'var(--r-md)', color: 'var(--fg-3)', fontSize: '0.9rem' }}>
            No content briefs yet. Add a brief to let the Content Agent draft it.
          </div>
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════
// STOREFRONT TAB
// ═══════════════════════════════════════

function StorefrontTab({ products, stats, onReload }: any) {
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: '', price: '', description: '' });

  const handleAdd = async () => {
    if (!form.name.trim()) return;
    await fetchAPI('/products', { method: 'POST', body: JSON.stringify({
      name: form.name, price: parseFloat(form.price) || 0, description: form.description,
    })});
    setForm({ name: '', price: '', description: '' });
    setShowForm(false); onReload();
  };

  return (
    <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div className="eyebrow" style={{ marginBottom: '8px' }}>Digital storefront</div>
          <h1 style={{ fontFamily: 'var(--font-display)', fontSize: 'clamp(32px, 4vw, 48px)' }}>Storefront</h1>
        </div>
        <button onClick={() => setShowForm(!showForm)} className="btn-outline" style={{ fontSize: '11px', padding: '10px 18px' }}>
          {showForm ? 'Cancel' : '+ Add Product'}
        </button>
      </div>

      {showForm && (
        <div style={cardStyle}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 120px', gap: '12px' }}>
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Product name" style={inputStyle} />
              <input type="number" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} placeholder="Price ($)" style={inputStyle} />
            </div>
            <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Product description" rows={2} style={{ ...inputStyle, resize: 'vertical' }} />
            <button onClick={handleAdd} className="btn-terminal" style={{ alignSelf: 'flex-start' }}>Add product</button>
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '16px' }}>
        {(products || []).map((p: any) => (
          <div key={p.id} style={cardStyle}>
            <div style={{ height: '120px', background: 'var(--kit-gradient)', borderRadius: 'var(--r-sm)', marginBottom: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <span style={{ fontSize: '2rem' }}>📄</span>
            </div>
            <div style={{ fontWeight: 700, fontSize: '0.95rem', marginBottom: '4px' }}>{p.name}</div>
            {p.description && <div style={{ fontSize: '0.78rem', color: 'var(--fg-3)', marginBottom: '8px', lineHeight: 1.5 }}>{p.description}</div>}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ fontFamily: 'var(--font-display)', fontSize: '1.4rem' }}>${p.price}</div>
              <div className="eyebrow">{p.units_sold || 0} sold</div>
            </div>
          </div>
        ))}
        {(!products || products.length === 0) && (
          <div style={{ gridColumn: '1 / -1', padding: '48px', textAlign: 'center', background: 'var(--bg-sunken)', borderRadius: 'var(--r-md)', color: 'var(--fg-3)', fontSize: '0.9rem' }}>
            No products yet. Add your first digital product.
          </div>
        )}
      </div>
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
          <div className="eyebrow" style={{ marginBottom: '8px' }}>Agent memory</div>
          <h1 style={{ fontFamily: 'var(--font-display)', fontSize: 'clamp(32px, 4vw, 48px)' }}>Memory</h1>
        </div>
        <button onClick={onLearn} className="btn-terminal" style={{ fontSize: '11px', padding: '10px 18px' }}>
          Learn Patterns \u2192
        </button>
      </div>

      <p style={{ fontSize: 'var(--fs-body)', color: 'var(--fg-3)', maxWidth: '60ch' }}>
        The Memory Agent analyzes all deals, content, and outcomes to extract patterns. These insights inform future agent decisions.
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {(patterns || []).map((p: any, i: number) => (
          <div key={i} style={{ ...cardStyle, borderLeft: `3px solid var(--kit-fox)` }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <span className="eyebrow">{p.category || 'insight'}</span>
              <span className="mono" style={{ fontSize: '0.68rem', color: 'var(--fg-mute)' }}>{new Date(p.created_at).toLocaleDateString()}</span>
            </div>
            <div style={{ fontFamily: 'var(--font-display)', fontSize: '1.1rem', marginBottom: '8px' }}>{p.insight}</div>
            {p.evidence && <div style={{ fontSize: '0.8rem', color: 'var(--fg-3)', lineHeight: 1.5 }}>{p.evidence}</div>}
          </div>
        ))}
        {(!patterns || patterns.length === 0) && (
          <div style={{ padding: '48px', textAlign: 'center', background: 'var(--bg-sunken)', borderRadius: 'var(--r-md)', color: 'var(--fg-3)', fontSize: '0.9rem' }}>
            No patterns yet. Run the Memory Agent to analyze your deals and content.
          </div>
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════
// AGENTS TAB
// ═══════════════════════════════════════

function AgentsTab({ activities, thinking }: any) {
  const [agentTeam, setAgentTeam] = useState<any>(null);
  const [runningAutopilot, setRunningAutopilot] = useState(false);
  const [autopilotMsg, setAutopilotMsg] = useState('');

  const loadTeam = useCallback(async () => {
    try { setAgentTeam(await fetchAPI('/agents/team')); } catch {}
  }, []);
  useEffect(() => { loadTeam(); const int = setInterval(loadTeam, 5000); return () => clearInterval(int); }, [loadTeam]);

  const runAgent = async (name: string) => {
    try { await fetchAPI(`/agents/${name}/run`, { method: 'POST' }); setAutopilotMsg(`${name} executed`); setTimeout(loadTeam, 2000); }
    catch { setAutopilotMsg(`${name} running...`); }
  };

  const runAutopilot = async () => {
    setRunningAutopilot(true);
    setAutopilotMsg('Running pipeline: Memory \u2192 Strategy \u2192 Analytics...');
    try { await fetchAPI('/agents/autopilot', { method: 'POST' }); setAutopilotMsg('Autopilot complete.'); }
    catch { setAutopilotMsg('Pipeline started (running in background).'); }
    setRunningAutopilot(false); setTimeout(loadTeam, 3000);
  };

  const expertAgents = [
    { name: 'deal_agent', display: 'Deal Agent', icon: '🤝', desc: 'Researches brands, negotiates, generates contracts' },
    { name: 'content_agent', display: 'Content Agent', icon: '\u270D️', desc: 'Researches trends, writes content drafts' },
    { name: 'finance_agent', display: 'Finance Agent', icon: '💰', desc: 'Creates Stripe invoices, manages payments' },
    { name: 'memory_agent', display: 'Memory Agent', icon: '🧠', desc: 'Learns from outcomes, stores patterns' },
    { name: 'strategy_agent', display: 'Strategy Agent', icon: '🎯', desc: 'Analyzes market, plans growth' },
    { name: 'outreach_agent', display: 'Outreach Agent', icon: '📬', desc: 'Finds brands, sends DMs/emails' },
  ];
  const workerAgents = [
    { name: 'publisher_agent', display: 'Publisher', icon: '📱', desc: 'Posts to Instagram, YouTube, Twitter' },
    { name: 'email_agent', display: 'Email', icon: '📧', desc: 'Sends real emails via SMTP' },
    { name: 'contract_agent', display: 'Contract', icon: '📋', desc: 'Generates legal documents' },
    { name: 'analytics_agent', display: 'Analytics', icon: '📊', desc: 'Tracks metrics across platforms' },
    { name: 'scheduler_agent', display: 'Scheduler', icon: '📅', desc: 'Manages content calendar' },
    { name: 'notification_agent', display: 'Notification', icon: '🔔', desc: 'Sends Slack/Discord/Telegram alerts' },
  ];

  const AgentCard = ({ a }: { a: any }) => {
    const td = agentTeam?.agents?.find((t: any) => t.name === a.name);
    return (
      <div style={{ ...cardStyle, borderColor: td?.last_active ? 'var(--kit-fox)' : 'var(--border)', padding: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
          <span style={{ fontSize: '1.3rem' }}>{a.icon}</span>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 700, fontSize: '0.85rem' }}>{a.display}</div>
            <div style={{ fontSize: '0.65rem', color: td?.last_active ? '#16a34a' : 'var(--fg-mute)' }}>
              {td?.last_active ? `\u25CF ${td.total_activities} runs` : '\u25CB never run'}
            </div>
          </div>
        </div>
        <div style={{ fontSize: '0.74rem', color: 'var(--fg-3)', marginBottom: '10px', lineHeight: 1.5 }}>{a.desc}</div>
        <button onClick={() => runAgent(a.name)} className="btn-outline" style={{ width: '100%', fontSize: '10px', padding: '6px', justifyContent: 'center' }}>Run \u2192</button>
      </div>
    );
  };

  return (
    <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div className="eyebrow" style={{ marginBottom: '8px' }}>Agentic team</div>
          <h1 style={{ fontFamily: 'var(--font-display)', fontSize: 'clamp(32px, 4vw, 48px)' }}>Agent Team</h1>
        </div>
        <button onClick={runAutopilot} disabled={runningAutopilot} className="btn-terminal" style={{ fontSize: '12px' }}>
          {runningAutopilot ? 'Running...' : 'Run Autopilot \u2192'}
        </button>
      </div>

      {autopilotMsg && (
        <div style={{ padding: '12px 16px', background: 'var(--bg-sunken)', borderRadius: 'var(--r-sm)', fontSize: '0.82rem', border: '1px solid var(--border)' }}>
          {autopilotMsg}
        </div>
      )}

      {/* How it works */}
      <div style={cardStyle}>
        <div className="eyebrow" style={{ marginBottom: '10px' }}>The 2030 vision, live</div>
        <p style={{ fontSize: '0.82rem', color: 'var(--fg-3)', lineHeight: 1.7 }}>
          <strong style={{ color: 'var(--fg)' }}>12 AI agents</strong> work as a full autonomous company. {agentTeam?.expert_count || 6} expert agents (strategic) and {agentTeam?.worker_count || 6} worker agents (execution). Each uses a ReAct loop to plan, execute real tools, and analyze results. Agents delegate tasks to each other and take real actions on connected platforms.
        </p>
        <div style={{ marginTop: '12px', display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
          {['web_search', 'instagram_post', 'youtube_upload', 'send_email', 'stripe_invoice', 'twitter_post', 'send_notification', 'delegate_to_agent'].map(t => (
            <code key={t} className="mono" style={{ fontSize: '0.65rem', padding: '3px 8px', background: 'var(--bg-sunken)', borderRadius: 'var(--r-xs)', color: 'var(--fg-3)' }}>{t}</code>
          ))}
        </div>
      </div>

      {/* Expert Agents */}
      <div>
        <div className="eyebrow" style={{ marginBottom: '12px' }}>Strategic decision-makers</div>
        <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 'clamp(20px, 2.5vw, 28px)', marginBottom: '16px' }}>Expert Agents</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '12px' }}>
          {expertAgents.map(a => <AgentCard key={a.name} a={a} />)}
        </div>
      </div>

      {/* Worker Agents */}
      <div>
        <div className="eyebrow" style={{ marginBottom: '12px' }}>Real-world execution</div>
        <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 'clamp(20px, 2.5vw, 28px)', marginBottom: '16px' }}>Worker Agents</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '12px' }}>
          {workerAgents.map(a => <AgentCard key={a.name} a={a} />)}
        </div>
      </div>

      {/* Recent Activity */}
      <div>
        <div className="eyebrow" style={{ marginBottom: '12px' }}>Agent activity</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {(activities || []).slice(0, 15).map((a: any, i: number) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 14px', background: 'var(--bg-sunken)', borderRadius: 'var(--r-sm)', fontSize: '0.78rem' }}>
              <span className="mono" style={{ fontSize: '0.62rem', color: 'var(--kit-fox)', textTransform: 'uppercase' }}>{a.agent_name}</span>
              <span style={{ flex: 1, color: 'var(--fg-2)' }}>{a.summary}</span>
              <span className="mono" style={{ color: 'var(--fg-mute)', fontSize: '0.62rem' }}>{new Date(a.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════
// DOCUMENTS TAB
// ═══════════════════════════════════════

function DocumentsTab({ documents, onReload }: any) {
  const [selected, setSelected] = useState<any>(null);

  return (
    <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div>
        <div className="eyebrow" style={{ marginBottom: '8px' }}>Generated by agents</div>
        <h1 style={{ fontFamily: 'var(--font-display)', fontSize: 'clamp(32px, 4vw, 48px)' }}>Documents</h1>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: selected ? '1fr 1fr' : '1fr', gap: '16px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {(documents || []).map((doc: any) => (
            <div key={doc.id} onClick={() => setSelected(doc)} style={{ ...cardStyle, cursor: 'pointer', borderLeft: '3px solid var(--kit-fox)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <div className="eyebrow" style={{ marginBottom: '4px' }}>{doc.doc_type}</div>
                  <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{doc.title}</div>
                </div>
                <span style={{ fontSize: '1.2rem' }}>📄</span>
              </div>
            </div>
          ))}
          {(!documents || documents.length === 0) && (
            <div style={{ padding: '48px', textAlign: 'center', background: 'var(--bg-sunken)', borderRadius: 'var(--r-md)', color: 'var(--fg-3)', fontSize: '0.9rem' }}>
              No documents yet. Agents generate proposals, invoices, and contracts when deals are analyzed.
            </div>
          )}
        </div>

        {selected && (
          <div style={{ ...cardStyle, position: 'sticky', top: '80px', maxHeight: '70vh', overflow: 'auto' }}>
            <div className="eyebrow" style={{ marginBottom: '8px' }}>{selected.doc_type}</div>
            <h3 style={{ fontFamily: 'var(--font-display)', fontSize: '1.2rem', marginBottom: '16px' }}>{selected.title}</h3>
            <div style={{ fontSize: '0.82rem', lineHeight: 1.7, color: 'var(--fg-2)', whiteSpace: 'pre-wrap' }}>
              {selected.content}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════
// PLATFORMS TAB
// ═══════════════════════════════════════

function PlatformsTab() {
  const [platforms, setPlatforms] = useState<any[]>([]);
  const [actions, setActions] = useState<any[]>([]);
  const [connecting, setConnecting] = useState<string | null>(null);
  const [credForm, setCredForm] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState('');

  const loadPlatforms = useCallback(async () => {
    try {
      const [p, a] = await Promise.all([fetchAPI('/platforms'), fetchAPI('/platforms/actions?limit=20')]);
      setPlatforms(p.platforms || []); setActions(a.actions || []);
    } catch {}
  }, []);
  useEffect(() => { loadPlatforms(); }, [loadPlatforms]);

  const handleConnect = async (platform: string, fields: string[]) => {
    const credentials: Record<string, string> = {};
    for (const f of fields) {
      credentials[f] = credForm[`${platform}_${f}`] || '';
      if (!credentials[f]) { setMsg(`Please fill in ${f}`); return; }
    }
    try {
      await fetchAPI('/platforms/connect', { method: 'POST', body: JSON.stringify({ platform, credentials }) });
      setMsg(`${platform} connected.`); setCredForm({}); setConnecting(null); loadPlatforms();
    } catch (e: any) { setMsg(`Failed: ${e.message}`); }
  };

  const handleDisconnect = async (platform: string) => {
    await fetchAPI(`/platforms/${platform}/disconnect`, { method: 'POST' });
    loadPlatforms();
  };

  const platformInfo: Record<string, { icon: string; desc: string; fields: string[]; help: string }> = {
    instagram: { icon: '📸', desc: 'Post photos, reels, stories. Send DMs. Get insights.', fields: ['username', 'password'], help: 'Instagram username and password' },
    youtube: { icon: '📹', desc: 'Upload videos. Get analytics. Reply to comments.', fields: ['client_id', 'client_secret', 'access_token', 'refresh_token'], help: 'OAuth2 credentials from Google Cloud Console' },
    email: { icon: '📧', desc: 'Send real emails to brands, clients, partners.', fields: ['smtp_server', 'smtp_port', 'username', 'password'], help: 'SMTP server details (e.g. smtp.gmail.com:587)' },
    stripe: { icon: '💳', desc: 'Create real invoices, payment links, track payments.', fields: ['secret_key'], help: 'Stripe secret key (sk_...)' },
    twitter: { icon: '🕊️', desc: 'Post tweets and threads.', fields: ['consumer_key', 'consumer_secret', 'access_token', 'access_token_secret'], help: 'Twitter API v2 credentials' },
    slack: { icon: '💬', desc: 'Send notifications to Slack channels.', fields: ['webhook_url'], help: 'Slack incoming webhook URL' },
    github: { icon: '🐙', desc: 'Create issues, manage repos.', fields: ['token'], help: 'GitHub personal access token' },
    telegram: { icon: '\u2708}️', desc: 'Send notifications via Telegram bot.', fields: ['bot_token', 'chat_id'], help: 'Bot token from @BotFather' },
  };

  return (
    <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div>
        <div className="eyebrow" style={{ marginBottom: '8px' }}>Real-world connections</div>
        <h1 style={{ fontFamily: 'var(--font-display)', fontSize: 'clamp(32px, 4vw, 48px)' }}>Platforms</h1>
        <p style={{ fontSize: 'var(--fs-body)', color: 'var(--fg-3)', maxWidth: '60ch', marginTop: '8px' }}>
          Connect real platforms so agents can take real actions — post to Instagram, upload to YouTube, send emails, create Stripe invoices.
        </p>
      </div>

      {msg && <div style={{ padding: '10px 14px', background: 'var(--bg-sunken)', borderRadius: 'var(--r-sm)', fontSize: '0.82rem', border: '1px solid var(--border)' }}>{msg}</div>}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '16px' }}>
        {platforms.map((p) => {
          const info = platformInfo[p.platform] || { icon: '🔌', desc: p.description, fields: [], help: '' };
          return (
            <div key={p.platform} style={{ ...cardStyle, borderColor: p.connected ? 'var(--kit-fox)' : 'var(--border)' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span style={{ fontSize: '1.5rem' }}>{info.icon}</span>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: '0.9rem' }}>{p.display}</div>
                    <span className="status-chip" style={{ background: p.connected ? 'rgba(22,163,74,0.1)' : 'rgba(11,13,18,0.04)', color: p.connected ? '#16a34a' : 'var(--fg-mute)', border: 'none', fontSize: '0.6rem' }}>
                      {p.connected ? '\u25CF connected' : '\u25CB not connected'}
                    </span>
                  </div>
                </div>
              </div>
              <div style={{ fontSize: '0.76rem', color: 'var(--fg-3)', marginBottom: '14px', lineHeight: 1.5 }}>{info.desc}</div>
              {p.connected ? (
                <button onClick={() => handleDisconnect(p.platform)} className="btn-outline" style={{ width: '100%', fontSize: '0.75rem', justifyContent: 'center' }}>Disconnect</button>
              ) : connecting === p.platform ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {info.fields.map((f) => (
                    <input key={f} type={f.includes('password') || f.includes('secret') || f.includes('token') || f.includes('key') ? 'password' : 'text'} placeholder={f} value={credForm[`${p.platform}_${f}`] || ''} onChange={(e) => setCredForm({ ...credForm, [`${p.platform}_${f}`]: e.target.value })} style={inputStyle} />
                  ))}
                  <div className="mono" style={{ fontSize: '0.62rem', color: 'var(--fg-mute)' }}>{info.help}</div>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button onClick={() => handleConnect(p.platform, info.fields)} className="btn-terminal" style={{ flex: 1, fontSize: '0.75rem', justifyContent: 'center' }}>Connect</button>
                    <button onClick={() => { setConnecting(null); setCredForm({}); }} className="btn-outline" style={{ fontSize: '0.75rem' }}>Cancel</button>
                  </div>
                </div>
              ) : (
                <button onClick={() => setConnecting(p.platform)} className="btn-terminal" style={{ width: '100%', fontSize: '0.75rem', justifyContent: 'center' }}>Connect {p.display}</button>
              )}
            </div>
          );
        })}
      </div>

      {actions.length > 0 && (
        <div>
          <div className="eyebrow" style={{ marginBottom: '12px' }}>Audit trail</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {actions.map((a, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 14px', background: 'var(--bg-sunken)', borderRadius: 'var(--r-sm)', fontSize: '0.76rem' }}>
                <span style={{ color: a.status === 'success' ? '#16a34a' : '#dc2626' }}>{a.status === 'success' ? '\u2705' : '\u274C'}</span>
                <strong>{a.platform}</strong>
                <span style={{ color: 'var(--fg-3)' }}>{a.action}</span>
                <span className="mono" style={{ marginLeft: 'auto', color: 'var(--fg-mute)', fontSize: '0.62rem' }}>{new Date(a.created_at).toLocaleString()}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════
// AI PROVIDERS TAB
// ═══════════════════════════════════════

function ProvidersTab({ providers, activeProvider, keyProvider, setKeyProvider, keyValue, setKeyValue, onAddKey, onRemoveKey, keyMsg }: any) {
  return (
    <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div>
        <div className="eyebrow" style={{ marginBottom: '8px' }}>LLM providers</div>
        <h1 style={{ fontFamily: 'var(--font-display)', fontSize: 'clamp(32px, 4vw, 48px)' }}>AI Providers</h1>
        <p style={{ fontSize: 'var(--fs-body)', color: 'var(--fg-3)', maxWidth: '60ch', marginTop: '8px' }}>
          Add API keys to make agents smarter. The system automatically uses the best available provider. LLM7.io free tier is always available as fallback.
        </p>
      </div>

      {/* Active provider */}
      {activeProvider && (
        <div style={{ ...cardStyle, display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span className="status-chip approved"><span className="dot" /> Active</span>
          <span style={{ fontWeight: 600 }}>{PROVIDER_INFO[activeProvider]?.label || activeProvider}</span>
          <span style={{ fontSize: '0.8rem', color: 'var(--fg-3)' }}>{PROVIDER_INFO[activeProvider]?.description}</span>
        </div>
      )}

      {/* Add key form */}
      <div style={cardStyle}>
        <div className="eyebrow" style={{ marginBottom: '12px' }}>Add API key</div>
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          <select value={keyProvider} onChange={(e) => setKeyProvider(e.target.value)} style={{ ...inputStyle, width: 'auto', minWidth: '160px' }}>
            {Object.entries(PROVIDER_INFO).filter(([k]) => k !== 'llm7-free').map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
          </select>
          <input type="password" value={keyValue} onChange={(e) => setKeyValue(e.target.value)} placeholder="Paste API key..." style={{ ...inputStyle, flex: 1, minWidth: '200px' }} />
          <button onClick={onAddKey} className="btn-terminal">Add key</button>
        </div>
        {keyMsg && <div style={{ marginTop: '12px', fontSize: '0.82rem', color: 'var(--fg-3)' }}>{keyMsg}</div>}
        {PROVIDER_INFO[keyProvider]?.signupUrl && (
          <div style={{ marginTop: '8px' }}>
            <a href={PROVIDER_INFO[keyProvider].signupUrl} target="_blank" rel="noopener" className="btn-ghost" style={{ fontSize: '0.78rem' }}>
              Get a free {PROVIDER_INFO[keyProvider].label} key \u2192
            </a>
          </div>
        )}
      </div>

      {/* Provider list */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '12px' }}>
        {providers.map((p: LLMProvider) => (
          <div key={p.name} style={{ ...cardStyle, borderColor: p.enabled ? 'var(--kit-fox)' : 'var(--border)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <strong style={{ fontSize: '0.9rem' }}>{PROVIDER_INFO[p.name]?.label || p.name}</strong>
              {p.enabled ? (
                <span className="status-chip approved"><span className="dot" /> Enabled</span>
              ) : p.is_rate_limited ? (
                <span className="status-chip execute"><span className="dot" /> Rate limited</span>
              ) : (
                <span className="eyebrow" style={{ color: 'var(--fg-mute)' }}>No key</span>
              )}
            </div>
            <div style={{ fontSize: '0.76rem', color: 'var(--fg-3)', marginBottom: '8px' }}>{PROVIDER_INFO[p.name]?.description}</div>
            <div style={{ display: 'flex', gap: '12px', fontSize: '0.7rem', color: 'var(--fg-mute)' }}>
              <span>{p.total_calls} calls</span>
              {p.total_errors > 0 && <span style={{ color: '#dc2626' }}>{p.total_errors} errors</span>}
            </div>
            {p.enabled && p.name !== 'llm7-free' && (
              <button onClick={() => onRemoveKey(p.name)} className="btn-outline" style={{ marginTop: '10px', width: '100%', fontSize: '0.7rem', justifyContent: 'center' }}>Remove key</button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
