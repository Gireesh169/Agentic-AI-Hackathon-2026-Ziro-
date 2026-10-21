import { useMemo, useState } from "react";
import { useEffect } from "react";
import { createClient } from "@supabase/supabase-js";
import {
  Activity, ArrowDownRight, ArrowRight, BookOpen, Bot, CalendarDays,
  Check, CheckCircle2, ChevronRight, CircleHelp, Clock3, ExternalLink,
  GraduationCap, LayoutDashboard, Link2, LoaderCircle, Play, RefreshCw,
  ShieldCheck, Sparkles, Target, WandSparkles, XCircle
} from "lucide-react";

const API = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;
const supabase = supabaseUrl && supabaseAnonKey ? createClient(supabaseUrl, supabaseAnonKey) : null;

async function api(path, options = {}) {
  const session = supabase ? (await supabase.auth.getSession()).data.session : null;
  const response = await fetch(`${API}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {}),
      ...(options.headers || {})
    },
    ...options
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
  return data;
}

function Badge({ children, tone = "neutral" }) {
  return <span className={`badge ${tone}`}>{children}</span>;
}

export default function App() {
  const [session, setSession] = useState(null);
  const [authLoading, setAuthLoading] = useState(Boolean(supabase));
  const [form, setForm] = useState({
    goal: "Become a Data Analyst",
    level: "Beginner",
    weekly_hours: 5,
    duration_months: 6
  });
  const [record, setRecord] = useState(null);
  const [active, setActive] = useState("Overview");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [verification, setVerification] = useState({});
  const [tests, setTests] = useState(null);
  const [preview, setPreview] = useState(null);
  const [approved, setApproved] = useState(false);
  const [apiStatus, setApiStatus] = useState(null);
  const [savedRoadmaps, setSavedRoadmaps] = useState([]);
  const [profile, setProfile] = useState(null);
  const [saveState, setSaveState] = useState("idle");

  useEffect(() => {
    if (!supabase) {
      setAuthLoading(false);
      return undefined;
    }
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setAuthLoading(false);
    });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, nextSession) => setSession(nextSession));
    return () => listener.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (!session) return;
    setError("");
    Promise.all([api("/api/roadmaps"), api("/api/me")])
      .then(([roadmaps, currentProfile]) => {
        setSavedRoadmaps(roadmaps);
        setProfile(currentProfile);
      })
      .catch(e => setError(`Unable to load your account data: ${e.message}`));
  }, [session]);

  const weeks = record?.weeks || record?.plan?.weeks || [];
  const resources = useMemo(() => {
    const map = new Map();
    const savedResources = (record?.weeks || []).flatMap(week => week.resources || []);
    [...Object.values(record?.resources_by_week || {}).flat(), ...savedResources].forEach(r => map.set(r.id, r));
    return [...map.values()];
  }, [record]);
  const budget = form.weekly_hours * Math.round(form.duration_months * 52 / 12);

  const updateForm = (key, value) => setForm(p => ({ ...p, [key]: value }));

  async function checkApi() {
    try {
      const status = await api("/health");
      setApiStatus(status);
      setNotice("Backend connection successful.");
      setError("");
    } catch (e) {
      setApiStatus(null);
      setError(`Backend not reachable: ${e.message}. Start FastAPI on port 8000.`);
    }
  }

  async function generatePlan(e) {
    e?.preventDefault();
    setBusy(true); setError(""); setNotice(""); setVerification({});
    try {
      const data = await api("/api/plan", { method: "POST", body: JSON.stringify(form) });
      setRecord(data);
      setSaveState("idle");
      setPreview(null); setApproved(false);
      setActive("Roadmap");
      setNotice("Learning plan generated. Verify the resource links before relying on them.");
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  async function saveGeneratedRoadmap() {
    if (!record || saveState === "saving" || saveState === "saved") return;
    setSaveState("saving"); setError(""); setNotice("");
    try {
      const saved = await api("/api/roadmaps", {
        method: "POST",
        body: JSON.stringify({
          preview_id: record.id,
          goal: record.input,
          generation: {
            plan: record.plan,
            generation: record.generation
          },
          resources_by_week: record.resources_by_week || {}
        })
      });
      setRecord(saved);
      setSavedRoadmaps(p => [saved, ...p.filter(item => item.id !== saved.id)]);
      setSaveState("saved");
      setNotice("Saved Successfully");
    } catch (e) {
      setSaveState("error");
      setError(`Save failed: ${e.message}`);
    }
  }

  async function login() {
    if (!supabase) {
      setError("Supabase authentication is not configured. Add VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY.");
      return;
    }
    const { error: authError } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: window.location.origin }
    });
    if (authError) setError(authError.message);
  }

  async function logout() {
    if (supabase) await supabase.auth.signOut();
    setSession(null);
    setRecord(null);
    setSavedRoadmaps([]);
    setProfile(null);
  }

  async function updateRoadmapStatus(id, status) {
    try {
      const updated = await api(`/api/roadmaps/${id}`, { method: "PATCH", body: JSON.stringify({ status }) });
      setSavedRoadmaps(p => p.map(item => item.id === id ? updated : item));
      setNotice(`Roadmap ${status}.`);
    } catch (e) { setError(e.message); }
  }

  async function openSavedRoadmap(id) {
    try {
      const data = await api(`/api/roadmaps/${id}`);
      setRecord(data);
      setSaveState("saved");
      setActive("Roadmap");
    } catch (e) { setError(e.message); }
  }

  async function duplicateRoadmap(id) {
    try {
      const copy = await api(`/api/roadmaps/${id}/duplicate`, { method: "POST" });
      setSavedRoadmaps(p => [copy, ...p]);
      setNotice("Roadmap duplicated.");
    } catch (e) { setError(e.message); }
  }

  async function deleteRoadmap(id) {
    if (!window.confirm("Delete this saved roadmap and its progress?")) return;
    try {
      await api(`/api/roadmaps/${id}`, { method: "DELETE" });
      setSavedRoadmaps(p => p.filter(item => item.id !== id));
      if (record?.id === id) setRecord(null);
      setNotice("Roadmap deleted.");
    } catch (e) { setError(e.message); }
  }

  async function updateWeekStatus(weekId, completion_status) {
    if (!record?.id) return;
    try {
      await api(`/api/roadmaps/${record.id}/weeks/${weekId}`, { method: "PATCH", body: JSON.stringify({ completion_status }) });
      const refreshed = await api(`/api/roadmaps/${record.id}`);
      setRecord(refreshed);
      setSavedRoadmaps(p => p.map(item => item.id === refreshed.id ? { ...item, progress_percent: refreshed.progress_percent ?? item.progress_percent } : item));
    } catch (e) { setError(e.message); }
  }

  async function updateResourceStatus(resourceId, is_completed) {
    if (!record?.id) return;
    try {
      await api(`/api/roadmaps/${record.id}/resources/${resourceId}`, { method: "PATCH", body: JSON.stringify({ is_completed }) });
      const refreshed = await api(`/api/roadmaps/${record.id}`);
      setRecord(refreshed);
    } catch (e) { setError(e.message); }
  }

  const weekView = week => ({
    title: week.title || week.topic,
    hours: week.estimated_hours ?? week.hours,
    activities: week.activities || [],
    outcome: week.learning_objectives?.[0] || week.outcome,
    resources: week.resources || record?.resources_by_week?.[String(week.week_number ?? week.week)] || [],
    id: week.id,
    number: week.week_number ?? week.week,
    completion_status: week.completion_status
  });

  async function verifyOne(resource) {
    setVerification(p => ({ ...p, [resource.id]: { loading: true } }));
    try {
      const result = await api("/api/resources/verify", {
        method: "POST",
        body: JSON.stringify({ url: resource.url })
      });
      setVerification(p => ({ ...p, [resource.id]: result }));
    } catch (e) {
      setVerification(p => ({ ...p, [resource.id]: { error: e.message } }));
    }
  }

  async function verifyAll() {
    setBusy(true); setError(""); setNotice("");
    for (const resource of resources) await verifyOne(resource);
    setBusy(false);
    setNotice("Resource checks finished. UNKNOWN pricing statuses need manual review.");
  }

  async function loadPreview() {
    if (!record) return;
    if (saveState !== "saved") {
      setError("Save the roadmap before preparing schedule actions.");
      return;
    }
    setBusy(true); setError(""); setNotice("");
    try {
      const data = await api("/api/approvals/preview", {
        method: "POST", body: JSON.stringify({ plan_id: record.id })
      });
      setPreview(data);
      setApproved(false);
      setActive("Approval");
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  async function submitApproval(approvedValue) {
    if (!record) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const data = await api(`/api/approvals/${record.id}`, {
        method: "POST", body: JSON.stringify({ approved: approvedValue })
      });
      setNotice(data.execution.message);
      setApproved(approvedValue);
      setRecord(p => ({ ...p, approval_status: data.approval.approved ? "APPROVED" : "REJECTED", execution_status: data.execution.status }));
      if (preview) setPreview(p => ({ ...p, execution: data.execution }));
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  async function runTests() {
    setBusy(true); setError(""); setNotice("");
    try {
      const data = await api("/api/test-cases/run-all", { method: "POST", body: "{}" });
      setTests(data);
      setActive("Test Lab");
      setNotice("Test scenarios executed. Review fixture limitations in the evidence.");
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }

  if (authLoading) return <div className="auth-shell"><LoaderCircle className="spin" size={25}/><p>Restoring your session…</p></div>;
  if (!session) return <div className="auth-shell"><div className="auth-card"><div className="brand-icon"><WandSparkles size={21}/></div><h1>Welcome to PathPilot</h1><p>Sign in to save your learning roadmaps and track progress.</p><button className="primary-button full" onClick={login}>Continue with Google</button>{!supabase && <small>Authentication requires Supabase frontend environment variables.</small>}{error && <div className="alert error">{error}</div>}</div></div>;

  const nav = [
    ["Overview", LayoutDashboard], ["Roadmap", BookOpen], ["Saved Roadmaps", GraduationCap],
    ["Resources", Link2], ["Approval", CalendarDays], ["Test Lab", ShieldCheck]
  ];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon"><WandSparkles size={21} /></div>
          <div><strong>PathPilot</strong><span>AI LEARNING AGENT</span></div>
        </div>
        <div className="workspace-label">WORKSPACE</div>
        <nav>
          {nav.map(([name, Icon]) => (
            <button key={name} className={`nav-item ${active === name ? "selected" : ""}`} onClick={() => setActive(name)}>
              <Icon size={18} /><span>{name}</span>{active === name && <ChevronRight size={15} className="nav-arrow" />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="agent-status"><span className="status-dot" /><div><b>Agent workspace</b><small>{apiStatus ? "Backend connected" : "Local demo mode"}</small></div></div>
          <button className="text-button" onClick={checkApi}><RefreshCw size={14}/> Check backend</button>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="crumb">Workspace <ChevronRight size={14} /> <b>{active}</b></div>
          <div className="top-actions"><span className="environment-pill"><span /> HACKATHON MVP</span><span className="user-name">{profile?.display_name || session.user.email}</span><button className="text-button" onClick={logout}>Log out</button><div className="avatar">{(profile?.display_name || "U").slice(0,2).toUpperCase()}</div></div>
        </header>

        <div className="page-content">
          {error && <div className="alert error"><XCircle size={17}/><span>{error}</span><button onClick={() => setError("")}><XCircle size={15}/></button></div>}
          {notice && <div className="alert success"><CheckCircle2 size={17}/><span>{notice}</span><button onClick={() => setNotice("")}><XCircle size={15}/></button></div>}

          {active === "Overview" && <>
            <section className="hero">
              <div className="hero-copy">
                <div className="eyebrow"><Sparkles size={14}/> YOUR PERSONAL AI LEARNING AGENT</div>
                <h1>Turn your ambition<br/>into a <span>learning path.</span></h1>
                <p>Build a realistic, resource-backed plan for your next career move. Your agent plans, checks sources, and asks before taking action.</p>
                <button className="primary-button" onClick={() => setActive("Roadmap")}>Build my learning path <ArrowRight size={17}/></button>
              </div>
              <div className="hero-art">
                <div className="orb orb-one"/><div className="orb orb-two"/>
                <div className="orbit-card orbit-top"><span className="mini-icon purple"><Bot size={18}/></span><div><b>AI Planner</b><small>Goal understood</small></div><CheckCircle2 size={17} className="green-icon"/></div>
                <div className="central-orb"><WandSparkles size={40}/></div>
                <div className="orbit-card orbit-bottom"><span className="mini-icon green"><ShieldCheck size={18}/></span><div><b>Evidence check</b><small>Sources traceable</small></div><Activity size={17} className="green-icon"/></div>
              </div>
            </section>
            <section className="stats-grid">
              <Stat icon={Target} label="Learning goal" value={record ? "Created" : "Not set"} note={record ? record.input.goal : "Ready when you are"} />
              <Stat icon={Clock3} label="Available time" value={`${budget} hrs`} note={`${form.weekly_hours} hours each week`} />
              <Stat icon={BookOpen} label="Roadmap sessions" value={record ? weeks.length : "—"} note={record ? "Weekly sessions generated" : "Generate a plan to begin"} />
              <Stat icon={ShieldCheck} label="Verification" value={resources.length ? `${resources.filter(r => verification[r.id] && !verification[r.id].loading).length}/${resources.length}` : "—"} note="Resources checked this session" />
            </section>
            <section className="two-column">
              <div className="panel goal-panel">
                <PanelTitle icon={Target} title="Define your goal" subtitle="Tell the agent where you want to go."/>
                <GoalForm form={form} updateForm={updateForm} onSubmit={generatePlan} busy={busy}/>
              </div>
              <div className="panel workflow-panel">
                <PanelTitle icon={Bot} title="Agent workflow" subtitle="Four focused stages, one coordinated agent."/>
                <div className="workflow-list">
                  <WorkflowItem number="01" title="Plan" desc="Order skills and fit the time budget" tone="purple" />
                  <WorkflowItem number="02" title="Discover" desc="Match topics to public resources" tone="blue" />
                  <WorkflowItem number="03" title="Verify" desc="Check links and pricing evidence" tone="green" />
                  <WorkflowItem number="04" title="Act safely" desc="Request approval before scheduling" tone="orange" />
                </div>
                <button className="subtle-button full" onClick={() => setActive("Test Lab")}>Explore official test cases <ArrowRight size={15}/></button>
              </div>
            </section>
          </>}

          {active === "Roadmap" && <>
            <PageHeading eyebrow="YOUR PERSONAL CURRICULUM" title="Learning roadmap" desc="A week-by-week plan with a strict time budget and topic-specific resources."/>
            <div className="panel goal-panel">
              <GoalForm form={form} updateForm={updateForm} onSubmit={generatePlan} busy={busy}/>
            </div>
            {record && <>
              <div className="roadmap-summary">
                <div><span className="eyebrow">GENERATED PLAN</span><h2>{record.plan.title}</h2><p>{record.plan.summary}</p>
                  {record.generation && <div className="generation-meta">
                    <Badge tone={record.generation.generation_mode === "ai" ? "green" : "orange"}>
                      {record.generation.generation_mode === "ai" ? "AI generated" : "Fallback generated"}
                    </Badge>
                    {record.generation.model && <span>Model: {record.generation.model}</span>}
                    <span>Validation: {record.generation.validation_status}</span>
                  </div>}
                  {record.generation?.warnings?.map((warning, index) => <div className="alert warning" key={index}>{warning}</div>)}
                </div>
                <div className="budget-card"><small>HOUR BUDGET</small><strong>{record.plan.planned_hours} <em>/ {record.plan.total_available_hours}</em></strong><div className="progress"><span style={{width: `${Math.min(100, record.plan.planned_hours / Math.max(1,record.plan.total_available_hours)*100)}%`}}/></div><Badge tone={record.plan.fits_budget ? "green" : "red"}>{record.plan.fits_budget ? "Fits budget" : "Over budget"}</Badge></div>
              </div>
              {!record.plan.fits_budget && <div className="alert error">This plan exceeds the hour budget and must be corrected before use.</div>}
              <div className="week-list">
                {weeks.map(rawWeek => { const w = weekView(rawWeek); return <div className="week-card" key={w.number}><div className="week-number">W{String(w.number).padStart(2,"0")}</div><div className="week-body"><div className="week-top"><h3>{w.title}</h3><Badge tone="purple">{w.hours} hrs</Badge></div><ul>{w.activities.map((a,i)=><li key={i}>{a}</li>)}</ul>{w.outcome && <p className="week-outcome"><b>Outcome:</b> {w.outcome}</p>}<div className="week-resource">{w.resources.slice(0,2).map(r=><span className="resource-progress" key={r.id}><label><input type="checkbox" checked={Boolean(r.is_completed)} onChange={e => updateResourceStatus(r.id, e.target.checked)} disabled={saveState !== "saved"}/> <a href={r.url} target="_blank" rel="noreferrer">{r.title} <ExternalLink size={12}/></a></label></span>)}</div>{w.id && <button className="text-button" disabled={saveState !== "saved"} onClick={() => updateWeekStatus(w.id, w.completion_status === "completed" ? "in_progress" : "completed")}>{w.completion_status === "completed" ? "Mark in progress" : "Mark completed"}</button>}</div></div>})}
              </div>
              <div className="panel save-roadmap-panel">
                <button className="primary-button" onClick={saveGeneratedRoadmap} disabled={saveState === "saving" || saveState === "saved" || !record.plan.fits_budget}>
                  {saveState === "saving" ? "Saving..." : saveState === "saved" ? "Saved Successfully" : saveState === "error" ? "Retry Save" : "Add to Saved Roadmaps"}
                </button>
                {saveState === "error" && <p className="alert error">The generated roadmap is still available. Correct the issue and retry saving.</p>}
              </div>
              <div className="action-row"><button className="secondary-button" onClick={() => setActive("Resources")}>Verify resources <ShieldCheck size={16}/></button><button className="primary-button" onClick={loadPreview} disabled={busy || !record.plan.fits_budget || saveState !== "saved"}>Review schedule actions <ArrowRight size={16}/></button></div>
            </>}
          </>}

          {active === "Saved Roadmaps" && <>
              <PageHeading eyebrow="YOUR HISTORY" title="Saved roadmaps" desc="Every generated roadmap is saved separately to your account."/>
              {savedRoadmaps.length === 0 ? <EmptyState icon={GraduationCap} title="No saved roadmaps yet" desc="Generate your first roadmap to start your learning history." onClick={() => setActive("Roadmap")} button="Generate roadmap"/> :
                <div className="saved-roadmaps">{savedRoadmaps.map(item => {
                  const progress = item.progress_percent ?? 0;
                  return <div className="panel saved-card" key={item.id}><div><span className="eyebrow">{item.status.toUpperCase()}</span><h2>{item.title}</h2><p>{item.skill_level} · {item.duration_weeks} weeks · {item.weekly_hours} hours/week</p><div className="progress"><span style={{width: `${progress}%`}}/></div><small>{progress}% complete</small></div><div className="saved-actions"><button className="secondary-button" onClick={() => openSavedRoadmap(item.id)}>Open</button><button className="text-button" onClick={() => duplicateRoadmap(item.id)}>Duplicate</button>{item.status === "archived" ? <button className="text-button" onClick={() => updateRoadmapStatus(item.id, "active")}>Restore</button> : <button className="text-button" onClick={() => updateRoadmapStatus(item.id, "archived")}>Archive</button>}<button className="text-button" onClick={() => deleteRoadmap(item.id)}>Delete</button></div></div>
                })}</div>}
          </>}

          {active === "Resources" && <>
            <PageHeading eyebrow="SOURCE EVIDENCE" title="Resource verification" desc="Live links are checked separately from pricing claims. Unknown means review is needed."/>
            {!record ? <EmptyState icon={BookOpen} title="Generate a roadmap first" desc="The agent will attach relevant resources to your weekly topics." onClick={() => setActive("Roadmap")} button="Create roadmap"/> : <>
              <div className="resource-toolbar"><div><b>{resources.length} unique resources</b><span>from the current roadmap</span></div><button className="primary-button" onClick={verifyAll} disabled={busy}>{busy ? <LoaderCircle className="spin" size={16}/> : <RefreshCw size={16}/>} Verify all links</button></div>
              <div className="resource-list">{resources.map(r => {
                const v = verification[r.id];
                return <div className="resource-card" key={r.id}><div className="resource-symbol"><BookOpen size={20}/></div><div className="resource-info"><h3>{r.title}</h3><a href={r.url} target="_blank" rel="noreferrer">{r.url} <ExternalLink size={12}/></a><p>{r.note}</p>{v?.evidence && <div className="evidence"><b>Evidence:</b> {v.evidence}<small>Checked {v.checked_at}</small></div>}{v?.error && <p className="error-text">{v.error}</p>}</div><div className="resource-status">{v?.loading ? <Badge tone="blue">Checking…</Badge> : v ? <><Badge tone={v.link_status === "LIVE" && v.pricing_status === "FREE" ? "green" : v.link_status === "BROKEN" || v.pricing_status === "PAID" ? "red" : "orange"}>{v.link_status}</Badge><Badge tone={v.pricing_status === "FREE" ? "green" : v.pricing_status === "PAID" ? "red" : "orange"}>{v.pricing_status}</Badge></> : <Badge>Not checked</Badge>}<button className="icon-button" title="Verify resource" onClick={() => verifyOne(r)}><RefreshCw size={15}/></button></div></div>;
              })}</div>
              <div className="note-box"><CircleHelp size={18}/><p><b>Evidence matters.</b> An HTTP 200 response does not prove a course is free. Pricing detection is heuristic; use UNKNOWN when the page does not clearly establish access conditions.</p></div>
            </>}
          </>}

          {active === "Approval" && <>
            <PageHeading eyebrow="HUMAN-IN-THE-LOOP" title="Approval center" desc="Review proposed changes before the agent executes any scheduling action."/>
            {!record ? <EmptyState icon={CalendarDays} title="No plan to schedule yet" desc="Generate a learning plan before reviewing its sessions." onClick={() => setActive("Roadmap")} button="Create roadmap"/> : <>
              {!preview ? <div className="panel approval-intro"><div className="approval-icon"><CalendarDays size={25}/></div><h2>Ready to prepare your schedule?</h2><p>The agent will propose one session per roadmap week. This starter uses a mock scheduler, so no real calendar is changed.</p><button className="primary-button" onClick={loadPreview} disabled={busy}>Prepare preview <ArrowRight size={16}/></button></div> : <>
                <div className="alert warning"><CircleHelp size={17}/><span><b>Mock action only.</b> No Google Calendar events or course enrollments will be created by this starter.</span></div>
                <div className="panel approval-panel"><div className="approval-header"><div><h2>Proposed learning sessions</h2><p>{preview.proposed_sessions.length} sessions · {record.plan.planned_hours} total hours</p></div><Badge tone="orange">Awaiting approval</Badge></div>
                  <div className="session-table">{preview.proposed_sessions.slice(0,10).map(s=><div className="session-row" key={s.session_key}><div className="session-week">W{s.week}</div><div className="session-details"><b>{s.title}</b><small>{s.scheduled_for}</small></div><span>{s.hours}h</span><Badge>Proposed</Badge></div>)}</div>
                  {preview.proposed_sessions.length > 10 && <p className="muted">Showing first 10 of {preview.proposed_sessions.length} proposed sessions.</p>}
                  <label className="approval-check"><input type="checkbox" checked={approved} onChange={e=>setApproved(e.target.checked)}/> I reviewed the proposed actions and approve mock session creation.</label>
                  <div className="action-row"><button className="secondary-button" onClick={() => submitApproval(false)} disabled={busy}>Reject</button><button className="primary-button" onClick={() => submitApproval(true)} disabled={busy || !approved}>Approve and execute mock actions <Check size={16}/></button></div>
                  {preview.execution && <div className="execution-result"><CheckCircle2 size={18}/><div><b>{preview.execution.status}</b><p>{preview.execution.message} Created in this run: {preview.execution.created}. Total existing: {preview.execution.total_existing ?? "—"}.</p><button className="text-button" onClick={() => submitApproval(true)}><RefreshCw size={13}/> Retry to test idempotency</button></div></div>}
                </div>
              </>}
            </>}
          </>}

          {active === "Test Lab" && <>
            <PageHeading eyebrow="OFFICIAL SCENARIOS" title="Agent test lab" desc="Run all four required scenarios and inspect the expected result, actual result, and evidence."/>
            <div className="test-summary panel"><div className="test-icon"><ShieldCheck size={24}/></div><div><h2>Validation suite</h2><p>TC1 checks budget logic; TC2–TC4 use deterministic fixtures so results are reproducible.</p></div><button className="primary-button" onClick={runTests} disabled={busy}>{busy ? <LoaderCircle size={16} className="spin"/> : <Play size={16}/>} Run all tests</button></div>
            <div className="test-cases">
              {[
                ["TC1","Budget constraint","Six months at five hours/week","Plan fits within 130 hours"],
                ["TC2","Paid course","Pricing status changes to paid","Replaced or flagged"],
                ["TC3","Broken link","Original link returns a simulated 404","Replaced and rechecked"],
                ["TC4","Idempotent rerun","Run scheduling twice with existing sessions","Only missing sessions added"]
              ].map(([id,title,scenario,expected]) => {
                const result = tests?.results?.find(r => r.case_id === id);
                return <div className="test-card" key={id}><div className={`test-id ${result?.passed ? "passed" : ""}`}>{result?.passed ? <Check size={16}/> : id}</div><div className="test-main"><div className="test-title"><h3>{title}</h3>{result && <Badge tone={result.passed ? "green" : "red"}>{result.passed ? "PASS" : "FAIL"}</Badge>}</div><p>{scenario}</p><div className="test-expected"><span>EXPECTED</span>{expected}</div>{result && <><div className="test-expected"><span>ACTUAL</span><code>{JSON.stringify(result.actual)}</code></div><div className="evidence"><b>Evidence:</b> {result.evidence}</div></>}</div></div>;
              })}
            </div>
            {tests && <div className="note-box"><CircleHelp size={18}/><p>These are controlled scenario results, not proof that every external course is currently free. TC3 uses a simulated broken link and simulated replacement recheck. Verify real resources separately.</p></div>}
          </>}
          <footer><span>PathPilot · Free Learning Path Builder</span><span>Evidence-first · Approval-gated · Idempotent</span></footer>
        </div>
      </main>
    </div>
  );
}

function Stat({ icon: Icon, label, value, note }) {
  return <div className="stat-card"><div className="stat-top"><span>{label}</span><span className="stat-icon"><Icon size={17}/></span></div><strong>{value}</strong><small>{note}</small></div>;
}
function PanelTitle({ icon: Icon, title, subtitle }) {
  return <div className="panel-title"><div className="panel-title-icon"><Icon size={18}/></div><div><h2>{title}</h2><p>{subtitle}</p></div></div>;
}
function GoalForm({ form, updateForm, onSubmit, busy }) {
  return <form className="goal-form" onSubmit={onSubmit}>
    <label>Career or learning goal<input value={form.goal} onChange={e=>updateForm("goal",e.target.value)} minLength={4} required placeholder="e.g. Become a Data Analyst"/></label>
    <div className="form-grid"><label>Starting level<select value={form.level} onChange={e=>updateForm("level",e.target.value)}><option>Beginner</option><option>Intermediate</option><option>Advanced</option></select></label>
      <label>Target duration<select value={form.duration_months} onChange={e=>updateForm("duration_months",Number(e.target.value))}><option value={3}>3 months</option><option value={6}>6 months</option><option value={9}>9 months</option><option value={12}>12 months</option></select></label></div>
    <label className="range-label"><span>Study hours per week <b>{form.weekly_hours} hours</b></span><input type="range" min="1" max="20" value={form.weekly_hours} onChange={e=>updateForm("weekly_hours",Number(e.target.value))}/><span className="range-scale"><small>1 hour</small><small>20 hours</small></span></label>
    <div className="budget-preview"><Clock3 size={17}/><div><small>Estimated available time</small><b>{form.weekly_hours * Math.round(form.duration_months*52/12)} total hours</b></div></div>
    <button className="primary-button full" type="submit" disabled={busy}>{busy ? <LoaderCircle size={17} className="spin"/> : <Sparkles size={17}/>} Generate AI learning path</button>
  </form>;
}
function WorkflowItem({ number, title, desc, tone }) {
  return <div className="workflow-item"><span className={`workflow-number ${tone}`}>{number}</span><div><b>{title}</b><small>{desc}</small></div><ArrowDownRight size={15} className="workflow-arrow"/></div>;
}
function PageHeading({ eyebrow, title, desc }) {
  return <div className="page-heading"><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{desc}</p></div>;
}
function EmptyState({ icon: Icon, title, desc, onClick, button }) {
  return <div className="empty-state"><div><Icon size={25}/></div><h2>{title}</h2><p>{desc}</p><button className="primary-button" onClick={onClick}>{button} <ArrowRight size={15}/></button></div>;
}
