import { useEffect, useState } from 'react'
import {
  Activity, Boxes, ChartNoAxesCombined, CheckCircle2, CircleHelp,
  Clock3, Cloud, Cpu, Moon, RefreshCw, Server, Settings2,
  Sun, Terminal, TrendingUp, Wifi, WifiOff, Zap
} from 'lucide-react'
import {
  Area, AreaChart, CartesianGrid, Legend, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis
} from 'recharts'
import './App.css'

const API = import.meta.env.VITE_API_URL || ''

function formatChartTime(value) {
  if (!value) return ''
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? String(value)
    : date.toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      })
}

function formatRps(value) {
  return value == null || !Number.isFinite(Number(value))
    ? 'No data'
    : `${Number(value).toFixed(5)} RPS`
}

function formatReplicas(value) {
  return value == null || !Number.isFinite(Number(value))
    ? 'No data'
    : `${Number(value)} pods`
}


function Metric({ title, value, unit, icon: Icon, color, detail }) {
  const displayValue =
    value == null
      ? '—'
      : unit === 'RPS' && Number.isFinite(Number(value))
        ? Number(value).toFixed(3)
        : value

  return (
    <article className="metric card">
      <div className="metric-top">
        <span>{title}</span>
        <span className={`metric-icon ${color}`}><Icon size={18} /></span>
      </div>
      <div className="metric-value">{displayValue} <small>{unit || ''}</small></div>
      <div className="metric-detail">{detail || 'Waiting for live data'}</div>
    </article>
  )
}

function Panel({ title, subtitle, icon: Icon, children, action }) {
  return (
    <section className="card panel">
      <div className="panel-heading">
        <div className="panel-title">
          {Icon && <span className="panel-icon"><Icon size={17} /></span>}
          <div>
            <h2>{title}</h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
        </div>
        {action}
      </div>
      {children}
    </section>
  )
}

function Empty({ children = 'Waiting for data from the backend' }) {
  return <div className="empty"><CircleHelp size={22} /><span>{children}</span></div>
}

function App() {
  const [theme, setTheme] = useState(() => localStorage.getItem('ema-theme') || 'dark')
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [lastUpdated, setLastUpdated] = useState(null)
  const [busy, setBusy] = useState(false)
  const [tab, setTab] = useState('Overview')

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('ema-theme', theme)
  }, [theme])

  async function refresh() {
    setBusy(true)
    try {
      const response = await fetch(`${API}/api/dashboard`, {
        headers: { Accept: 'application/json' }
      })
      if (!response.ok) throw new Error(`API returned HTTP ${response.status}`)
      const payload = await response.json()
      setData(payload)
      setError('')
      setLastUpdated(new Date())
    } catch (err) {
      setError(err.message || 'Backend unavailable')
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    refresh()
    const timer = setInterval(refresh, 5000)
    return () => clearInterval(timer)
  }, [])

  const metrics = data?.metrics || {}
  const pods = data?.pods || []
  const events = data?.events || []
  const logs = data?.logs || []
  const history = data?.history || []
  const evaluation = data?.evaluation || {}
  const hpa = data?.hpa || {}

  const current = metrics.actualRps
  const predicted = metrics.predictedRps30
  const currentReplicas = metrics.currentReplicas
  const desiredReplicas = metrics.desiredReplicas
  const connected = Boolean(data)

  const navItems = [
    ['Overview', Activity], ['Metrics', ChartNoAxesCombined],
    ['Pods', Boxes], ['Events', Clock3], ['Logs', Terminal]
  ]

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-logo"><Cloud size={24} /></div>
          <div><strong>EMA-TAP</strong><span>Predictive Autoscaling</span></div>
        </div>

        <div className="nav-label">WORKSPACE</div>
        <nav>
          {navItems.map(([name, Icon]) => (
            <button key={name} className={`nav-item ${tab === name ? 'active' : ''}`}
              onClick={() => setTab(name)}>
              <Icon size={18} /><span>{name}</span>
              {name === 'Events' && events.length > 0 && <small>{events.length}</small>}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="cluster-box">
            <div className="cluster-heading"><span className="status-dot" /> Kubernetes</div>
            <strong>{data?.cluster?.name || 'Cluster status unknown'}</strong>
            <span>{data?.cluster?.namespace || 'Namespace not reported'}</span>
            <div className="cluster-line"><span>API connection</span><b>{connected ? 'Connected' : 'Offline'}</b></div>
          </div>
          <div className="sidebar-footer">EMA-TAP · Trend-Adjusted EMA</div>
        </div>
      </aside>

      <section className="main-content">
        <header className="topbar">
          <div className="breadcrumbs">Cloud Native <span>/</span> Autoscaling</div>
          <div className="top-actions">
            <span className={`connection ${connected ? 'online' : 'offline'}`}>
              {connected ? <Wifi size={15} /> : <WifiOff size={15} />}
              {connected ? 'API connected' : 'Disconnected'}
            </span>
            <button className="icon-button" title="Refresh metrics" onClick={refresh} disabled={busy}>
              <RefreshCw size={17} className={busy ? 'spin' : ''} />
            </button>
            <button className="icon-button" title="Toggle theme"
              onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>
              {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
            </button>
          </div>
        </header>

        <div className="page-heading">
          <div>
            <div className="eyebrow"><Zap size={14} /> PREDICTIVE CONTROL PLANE</div>
            <h1>{tab === 'Overview' ? 'Autoscaling Overview' : tab}</h1>
            <p>Monitor workload forecasts, Kubernetes replicas and controller decisions.</p>
          </div>
          <div className="updated">
            <span className={`status-dot ${connected ? 'green' : 'red'}`} />
            <div><strong>{connected ? 'Data source reachable' : 'Waiting for backend'}</strong>
              <span>{lastUpdated ? `Updated ${lastUpdated.toLocaleTimeString()}` : 'No successful data fetch yet'}</span>
            </div>
          </div>
        </div>

        {error && (
          <div className="notice">
            <WifiOff size={18} />
            <div><strong>Live data is not connected</strong>
              <span>{error}. Metrics and pod states will remain empty until the API is available.</span>
            </div>
          </div>
        )}

        {tab === 'Overview' || tab === 'Metrics' ? (
          <>
            <div className="section-caption">LIVE TELEMETRY <span>· refreshed every 5 seconds</span></div>
            <div className="metrics-grid">
              <Metric title="Current request rate" value={current} unit="RPS" icon={Activity} color="blue" />
              <Metric title="Predicted request rate" value={predicted} unit="RPS" icon={TrendingUp} color="purple" detail="EMA-TAP · 30-second horizon" />
              <Metric title="Current replicas" value={currentReplicas} icon={Boxes} color="green" detail="Observed deployment replicas" />
              <Metric title="Desired replicas" value={desiredReplicas} icon={Zap} color="orange" detail="Controller-reported target" />
            </div>

            <div className="charts-grid">
              <Panel title="Actual vs predicted RPS" subtitle="Measured workload and forecast" icon={ChartNoAxesCombined}>
                {history.length ? (
                  <div className="chart-wrap">
                    <ResponsiveContainer width="100%" height={260}>
                      <LineChart data={history} margin={{ top: 12, right: 12, bottom: 0, left: -15 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--grid)" />
                        <XAxis
                          dataKey="time"
                          tickFormatter={formatChartTime}
                          minTickGap={35}
                          tick={{ fill: 'var(--muted)', fontSize: 11 }}
                          axisLine={{ stroke: 'var(--border)' }}
                          tickLine={{ stroke: 'var(--border)' }}
                        />
                        <YAxis
                          tickFormatter={(value) => Number(value).toFixed(3)}
                          tick={{ fill: 'var(--muted)', fontSize: 11 }}
                          axisLine={{ stroke: 'var(--border)' }}
                          tickLine={{ stroke: 'var(--border)' }}
                          width={55}
                          domain={['auto', 'auto']}
                        />
                        <Tooltip
                          labelFormatter={(value) => `Time: ${formatChartTime(value)}`}
                          formatter={(value, name) => [formatRps(value), name]}
                          contentStyle={{
                            background: 'var(--panel)',
                            borderColor: 'var(--border)',
                            borderRadius: 10,
                          }}
                        />
                        <Legend />
                        <Line type="natural" dataKey="actual" name="Actual RPS" stroke="#36a3ff" dot={false} strokeWidth={2.4} connectNulls={false} />
                        <Line type="natural" dataKey="predicted" name="Predicted RPS" stroke="#b18aff" dot={false} strokeWidth={2.4} strokeDasharray="5 4" connectNulls={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                ) : <Empty>No real RPS history received yet</Empty>}
              </Panel>

              <Panel title="Replica scaling" subtitle="Observed vs desired replicas" icon={Boxes}>
                {history.some(point => point.replicas != null || point.desired != null) ? (
                  <div className="chart-wrap">
                    <ResponsiveContainer width="100%" height={260}>
                      <AreaChart data={history} margin={{ top: 12, right: 12, bottom: 0, left: -15 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--grid)" />
                        <XAxis
                          dataKey="time"
                          tickFormatter={formatChartTime}
                          minTickGap={35}
                          tick={{ fill: 'var(--muted)', fontSize: 11 }}
                          axisLine={{ stroke: 'var(--border)' }}
                          tickLine={{ stroke: 'var(--border)' }}
                        />
                        <YAxis
                          allowDecimals={false}
                          tick={{ fill: 'var(--muted)', fontSize: 11 }}
                          axisLine={{ stroke: 'var(--border)' }}
                          tickLine={{ stroke: 'var(--border)' }}
                          width={45}
                        />
                        <Tooltip
                          labelFormatter={(value) => `Time: ${formatChartTime(value)}`}
                          formatter={(value, name) => [formatReplicas(value), name]}
                          contentStyle={{
                            background: 'var(--panel)',
                            borderColor: 'var(--border)',
                            borderRadius: 10,
                          }}
                        />
                        <Legend />
                        <Area type="stepAfter" dataKey="replicas" name="Current" stroke="#27c994" fill="#27c994" fillOpacity={0.12} />
                        <Area type="stepAfter" dataKey="desired" name="Desired" stroke="#b18aff" fill="#b18aff" fillOpacity={0.10} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                ) : <Empty>No replica history received yet</Empty>}
              </Panel>
            </div>
          </>
        ) : null}

        {tab === 'Overview' || tab === 'Pods' ? (
          <Panel title="Kubernetes pod fleet" subtitle="Pod status reported by Kubernetes" icon={Boxes}
            action={<span className="small-badge">{pods.length} observed</span>}>
            {pods.length ? (
              <div className="pod-topology">
                <div className="deployment-node">
                  <span className="deployment-node-icon">
                    <Server size={22} />
                  </span>
                  <strong>web-app Deployment</strong>
                  <span>{pods.length} observed pod{pods.length === 1 ? '' : 's'}</span>
                  <span className="deployment-node-status">
                    <span className="status-dot green" />
                    Kubernetes reported
                  </span>
                </div>
                <div className="deployment-connector" aria-hidden="true">
                  <svg viewBox="0 0 600 55" preserveAspectRatio="none">
                    {pods.map((pod, index) => {
                      const x = 600 * (index + 0.5) / pods.length
                      return (
                        <g key={pod.name}>
                          <path
                            className="topology-branch"
                            d={`M300 0 V18 H${x} V55`}
                          />
                          <circle
                            className="topology-node"
                            cx={x}
                            cy="55"
                            r="3"
                          />
                          <circle
                            className="topology-particle"
                            r="3.5"
                            fill="#a4ffdf"
                          >
                            <animateMotion
                              dur={`${1.4 + index * 0.25}s`}
                              repeatCount="indefinite"
                              path={`M300 0 V18 H${x} V55`}
                            />
                          </circle>
                        </g>
                      )
                    })}
                  </svg>
                </div>
                <div className="pod-fleet">
                <div className="pods-grid">
                {pods.map((pod) => (
                  <article
                    className={`pod-card ${
                      pod.phase === 'Failed'
                        ? 'pod-failed'
                        : pod.phase === 'Running' && pod.ready === true
                          ? 'pod-running'
                          : 'pod-pending'
                    }`}
                    key={pod.name}
                  >
                    <div className="pod-visual">
                      <div className="pod-cube"><Boxes size={25} /></div>
                      <span
                        className={`pod-led ${
                          pod.phase === 'Failed'
                            ? 'red'
                            : pod.phase === 'Running' && pod.ready === true
                              ? 'green'
                              : 'amber'
                        }`}
                      />
                    </div>
                    <strong title={pod.name}>{pod.name}</strong>
                    <span className="pod-phase">{pod.phase || 'Unknown'}</span>
                    <span
                      className={`pod-health-badge ${
                        pod.phase === 'Failed'
                          ? 'health-failed'
                          : pod.phase === 'Running' && pod.ready === true
                            ? 'health-healthy'
                            : 'health-warning'
                      }`}
                    >
                      {pod.phase === 'Failed'
                        ? 'Failed'
                        : pod.phase === 'Running' && pod.ready === true
                          ? 'Healthy'
                          : 'Not ready'}
                    </span>
                    <span className="pod-meta">Ready: {pod.ready ?? '—'} · Restarts: {pod.restarts ?? '—'}</span>
                  </article>
                ))}
                </div>
                </div>
              </div>
            ) : <Empty>No Kubernetes pod data received</Empty>}
          </Panel>
        ) : null}

        {tab === 'Overview' || tab === 'Metrics' ? (
          <div className="comparison-grid">
            <Panel title="EMA-TAP controller" subtitle="Predictive scaling status" icon={Zap}>
              <div className="detail-list">
                <div><span>Controller status</span><b>{data?.controller?.status || 'Unknown'}</b></div>
                <div><span>Last decision</span><b>{data?.controller?.lastAction || '—'}</b></div>
                <div><span>Decision reason</span><b>{data?.controller?.reason || '—'}</b></div>
                <div><span>Scaling mode</span><b>{data?.controller?.mode || '—'}</b></div>
              </div>
              <p className="footnote">Live controller data must come from the controller's API or exported metrics.</p>
            </Panel>
            <Panel title="HPA comparison" subtitle="Kubernetes Horizontal Pod Autoscaler" icon={Cpu}>
              <div className="hpa-stats">
                <div><span>Current replicas</span><strong>{hpa.currentReplicas ?? '—'}</strong></div>
                <div><span>Desired replicas</span><strong>{hpa.desiredReplicas ?? '—'}</strong></div>
                <div><span>CPU utilization</span><strong>{hpa.cpuUtilization == null ? '—' : `${hpa.cpuUtilization}%`}</strong></div>
                <div><span>Target CPU</span><strong>{hpa.targetCpu == null ? '—' : `${hpa.targetCpu}%`}</strong></div>
              </div>
              <p className="footnote">HPA values are separate from EMA-TAP recommendations. This view does not change either controller.</p>
            </Panel>
          </div>
        ) : null}

        {tab === 'Overview' || tab === 'Metrics' ? (
          <Panel title="Model evaluation" subtitle="Recorded test results — not live predictions" icon={ChartNoAxesCombined}>
            {evaluation.mae != null || evaluation.rmse != null || evaluation.r2 != null ? (
              <>
                <div className="evaluation-grid">
                  <div><span>MAE</span><strong>{evaluation.mae ?? '—'}</strong><small>RPS</small></div>
                  <div><span>RMSE</span><strong>{evaluation.rmse ?? '—'}</strong><small>RPS</small></div>
                  <div><span>R²</span><strong>{evaluation.r2 ?? '—'}</strong><small>Test score</small></div>
                  <div><span>Horizon</span><strong>{evaluation.horizonSeconds == null ? '—' : `${evaluation.horizonSeconds}s`}</strong><small>Forecast</small></div>
                </div>
                <p className="footnote">Evaluation values are displayed only when supplied by the backend.</p>
              </>
            ) : <Empty>No evaluation results received</Empty>}
          </Panel>
        ) : null}

        {tab === 'Overview' || tab === 'Events' ? (
          <Panel title="Scaling events" subtitle="Events supplied by the controller or Kubernetes" icon={Clock3}>
            {events.length ? <div className="event-list">
              {events.map((event, i) => <div className="event-row" key={event.id || i}>
                <span className="event-dot" />
                <span className="event-time">{event.time || '—'}</span>
                <div className="event-copy"><strong>{event.action || 'Event'}</strong><span>{event.message || 'No details supplied'}</span></div>
                <span className="event-source">{event.source || 'Unknown source'}</span>
              </div>)}
            </div> : <Empty>No scaling events received</Empty>}
          </Panel>
        ) : null}

        {tab === 'Overview' || tab === 'Logs' ? (
          <Panel title="Controller logs" subtitle="Actual messages received from the controller" icon={Terminal}
            action={<span className="small-badge">{logs.length} entries</span>}>
            {logs.length ? <div className="logs">
              {logs.map((log, i) => <div className="log-row" key={log.id || i}>
                <span className="log-time">{log.time || '—'}</span>
                <span className={`log-level ${String(log.level).toLowerCase()}`}>{log.level || 'INFO'}</span>
                <span className="log-message">{log.message || ''}</span>
              </div>)}
            </div> : <Empty>No controller log messages received</Empty>}
          </Panel>
        ) : null}

        <footer className="page-footer">
          <span><Server size={14} /> EMA-TAP · Predictive Autoscaling</span>
          <span><Settings2 size={14} /> Read-only dashboard · no scaling commands issued</span>
        </footer>
      </section>
    </main>
  )
}

export default App
