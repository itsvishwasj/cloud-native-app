/**
 * Client-side logic for the Single-Tab CloudOps Control Center.
 * Operates all 7 dashboard panels simultaneously in real-time without requiring tab navigation.
 */

document.addEventListener("DOMContentLoaded", () => {
  let workloadChart = null;
  let monitoringChart = null;
  let lastTermCount = 0;
  let lastPodTermCount = 0;
  let selectedProfile = "spike";
  let consecutiveFailures = 0;
  const MAX_POINTS = 12;
  const workloadSeries = { labels: [], measured: [], predicted: [] };
  const monitoringSeries = { labels: [], cpu: [], p95: [] };

  // -------------------------------------------------------------------
  // Connection status
  // -------------------------------------------------------------------
  const connDot = document.getElementById("top-conn-dot");
  const connLabel = document.getElementById("top-conn-status");

  function reportConnection(ok) {
    if (ok) {
      consecutiveFailures = 0;
    } else {
      consecutiveFailures += 1;
    }
    if (!connDot || !connLabel) return;
    if (consecutiveFailures === 0) {
      connDot.className = "dot green pulse";
      connLabel.textContent = "LIVE";
      connLabel.className = "val state-live";
    } else if (consecutiveFailures < 3) {
      connDot.className = "dot amber pulse";
      connLabel.textContent = "DEGRADED";
      connLabel.className = "val state-degraded";
    } else {
      connDot.className = "dot red";
      connLabel.textContent = "OFFLINE";
      connLabel.className = "val state-offline";
    }
  }

  async function getJSON(url, options) {
    try {
      const res = await fetch(url, options);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      reportConnection(true);
      return data;
    } catch (err) {
      reportConnection(false);
      return null;
    }
  }

  function flashValue(el) {
    if (!el) return;
    el.classList.remove("flash");
    void el.offsetWidth;
    el.classList.add("flash");
  }

  // -------------------------------------------------------------------
  // 1. View Mode Toggle
  // -------------------------------------------------------------------
  const btnSimple = document.getElementById("btn-simple-mode");
  const btnTech = document.getElementById("btn-tech-mode");

  if (btnSimple && btnTech) {
    btnSimple.addEventListener("click", () => {
      btnSimple.classList.add("active");
      btnTech.classList.remove("active");
      document.body.classList.remove("technical-mode");
    });
    btnTech.addEventListener("click", () => {
      btnTech.classList.add("active");
      btnSimple.classList.remove("active");
      document.body.classList.add("technical-mode");
    });
  }

  // -------------------------------------------------------------------
  // 2. Panel 1: GitHub Commits Feed
  // -------------------------------------------------------------------
  async function fetchGitCommits() {
    const data = await getJSON("/api/git/commits");
    if (!data || !data.commits) return;
    const container = document.getElementById("git-commits-list");
    if (!container) return;

    container.innerHTML = data.commits
      .map(
        (c) => `
      <div class="commit-item">
        <span class="commit-hash">${c.hash}</span>
        <div class="commit-details">
          <span class="commit-msg">${c.message}</span>
          <span class="commit-meta">${c.author} · ${c.date}</span>
        </div>
      </div>
    `
      )
      .join("");
  }

  // -------------------------------------------------------------------
  // 3. Panel 2 & 4: Pipeline Trigger & Demo Controls
  // -------------------------------------------------------------------
  const btnTrigger = document.getElementById("btn-trigger-pipeline");
  const btnStop = document.getElementById("btn-demo-stop");
  const btnReset = document.getElementById("btn-demo-reset");

  if (btnTrigger) {
    btnTrigger.addEventListener("click", async () => {
      if (btnStop) btnStop.disabled = false;
      await fetch("/api/demo/start", { method: "POST" });
      updateOverview();
    });
  }

  if (btnStop) {
    btnStop.addEventListener("click", async () => {
      await fetch("/api/demo/stop", { method: "POST" });
      if (btnStop) btnStop.disabled = true;
      updateOverview();
    });
  }

  if (btnReset) {
    btnReset.addEventListener("click", async () => {
      await fetch("/api/demo/reset", { method: "POST" });
      if (btnStop) btnStop.disabled = true;
      lastTermCount = 0;
      lastPodTermCount = 0;
      updateOverview();
    });
  }

  // -------------------------------------------------------------------
  // 4. Panel 3: AI Line-by-Line Error Diagnostics
  // -------------------------------------------------------------------
  async function fetchAIDiagnostics() {
    const data = await getJSON("/api/ai-diagnostics");
    if (!data) return;

    const sevEl = document.getElementById("ai-severity");
    const errTypeEl = document.getElementById("ai-error-type");
    const fileEl = document.getElementById("ai-affected-file");
    const explEl = document.getElementById("ai-explanation");
    const diffEl = document.getElementById("ai-diff-patch");
    const lineContainer = document.getElementById("ai-line-errors-container");

    if (sevEl) sevEl.textContent = `SEVERITY: ${data.severity || "HIGH"}`;
    if (errTypeEl) errTypeEl.textContent = data.error_type || "CPU_QUEUEING";
    if (fileEl) fileEl.textContent = `File: ${data.component || "app/cpu-worker.js"}`;
    if (explEl) explEl.textContent = data.explanation || "";
    if (diffEl) diffEl.textContent = data.code_diff || "";

    if (lineContainer && data.line_by_line_errors) {
      lineContainer.innerHTML = data.line_by_line_errors
        .map(
          (item) => `
        <div class="code-error-item">
          <span class="line-num">Line ${item.line}</span>
          <code class="code-snippet-line">${item.code}</code>
          <span class="issue-msg">⚠ Issue: ${item.issue}</span>
          <span class="fix-msg">✓ Fix: ${item.fix}</span>
        </div>
      `
        )
        .join("");
    }
  }

  // -------------------------------------------------------------------
  // 5. Panel 5: Synthetic Traffic Generator (Fake Requests)
  // -------------------------------------------------------------------
  const sliderRPS = document.getElementById("rps-slider");
  const sliderValLabel = document.getElementById("rps-slider-val");
  const profileBtns = document.querySelectorAll(".profile-btn");
  const btnSendTraffic = document.getElementById("btn-send-traffic");
  const btnStopTraffic = document.getElementById("btn-stop-traffic");

  if (sliderRPS && sliderValLabel) {
    sliderRPS.addEventListener("input", () => {
      sliderValLabel.textContent = `${parseFloat(sliderRPS.value).toFixed(2)} RPS`;
    });
  }

  profileBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      profileBtns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      selectedProfile = btn.getAttribute("data-profile");
    });
  });

  if (btnSendTraffic) {
    btnSendTraffic.addEventListener("click", async () => {
      const rpsVal = parseFloat(sliderRPS ? sliderRPS.value : 15);
      const pill = document.getElementById("traffic-status-pill");
      if (pill) {
        pill.textContent = `SENDING ${rpsVal} RPS (${selectedProfile.toUpperCase()})`;
        pill.className = "pill blue";
      }
      await fetch("/api/traffic/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rps: rpsVal, profile: selectedProfile }),
      });
      updateOverview();
    });
  }

  if (btnStopTraffic) {
    btnStopTraffic.addEventListener("click", async () => {
      const pill = document.getElementById("traffic-status-pill");
      if (pill) {
        pill.textContent = "STOPPED";
        pill.className = "pill amber";
      }
      await fetch("/api/traffic/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rps: 0.0, profile: "idle" }),
      });
      updateOverview();
    });
  }

  // -------------------------------------------------------------------
  // 6. Primary Real-Time Dashboard Updates
  // -------------------------------------------------------------------
  async function updateOverview() {
    const data = await getJSON("/api/overview");
    if (!data) return;

    // Metrics Cards
    const rpsEl = document.getElementById("ov-val-rps");
    const predEl = document.getElementById("ov-val-pred");
    const p95El = document.getElementById("ov-val-p95");
    const cpuEl = document.getElementById("ov-val-cpu");
    const repEl = document.getElementById("ov-val-rep");

    if (rpsEl) rpsEl.innerText = `${data.current_rps.toFixed(2)}`;
    if (predEl) predEl.innerText = `${data.predicted_rps_30s.toFixed(2)}`;
    if (p95El) p95El.innerText = `${data.p95_latency_sec.toFixed(3)}s`;
    if (cpuEl) cpuEl.innerText = `${data.current_cpu_percent.toFixed(1)}%`;
    if (repEl) repEl.innerText = `${data.current_replicas} Pods`;
    [rpsEl, predEl, p95El, cpuEl, repEl].forEach(flashValue);

    // Active Task Status Bar (Panel 4)
    const taskEl = document.getElementById("active-task-text");
    if (taskEl && data.active_task) {
      taskEl.innerText = data.active_task;
    }

    // Workload Box (Panel 5)
    const simRps = document.getElementById("sim-rps-val");
    const simPred = document.getElementById("sim-pred-val");
    const simPods = document.getElementById("sim-pods-val");
    if (simRps) simRps.innerText = `${data.current_rps.toFixed(2)} RPS`;
    if (simPred) simPred.innerText = `${data.predicted_rps_30s.toFixed(2)} RPS`;
    if (simPods) simPods.innerText = `${data.current_replicas} Pods`;

    // Command Terminal Output (Panel 4)
    const term = document.getElementById("demo-event-terminal");
    if (term && data.terminal_logs) {
      if (data.terminal_logs.length > lastTermCount) {
        const newLines = data.terminal_logs.slice(lastTermCount);
        newLines.forEach((msg) => {
          const div = document.createElement("div");
          div.className = "term-line";
          div.textContent = msg;
          term.appendChild(div);
        });
        lastTermCount = data.terminal_logs.length;
        term.scrollTop = term.scrollHeight;
      }
    }

    // Pod Watcher Terminal Output (Panel 6)
    const podTerm = document.getElementById("k8s-pod-terminal");
    if (podTerm && data.pod_terminal_logs) {
      if (data.pod_terminal_logs.length > lastPodTermCount) {
        const newLines = data.pod_terminal_logs.slice(lastPodTermCount);
        newLines.forEach((msg) => {
          const div = document.createElement("div");
          div.className = "term-line";
          div.textContent = msg;
          podTerm.appendChild(div);
        });
        lastPodTermCount = data.pod_terminal_logs.length;
        podTerm.scrollTop = podTerm.scrollHeight;
      }
    }

    // Kubernetes Pod Tile Cards (Panel 6)
    fetchKubernetesPods(data.current_replicas);
  }

  async function fetchKubernetesPods(targetCount) {
    const k8sData = await getJSON("/api/kubernetes");
    const container = document.getElementById("pod-tiles-container");
    const meta = document.getElementById("k8s-meta");
    if (!container || !k8sData) return;

    if (meta) {
      meta.innerText = `spec: ${k8sData.spec_replicas || targetCount} · available: ${k8sData.current_replicas || targetCount} · ready: ${targetCount}`;
    }

    const pods = k8sData.pods || [];
    container.innerHTML = pods
      .map(
        (p) => `
      <div class="metric-card" style="border-left:3px solid var(--color-green);">
        <div class="card-head">${p.name}</div>
        <div class="card-val green-txt" style="font-size:1.05rem;margin-top:4px;">${p.phase}</div>
        <div class="card-sub">Ready: ${p.ready ? "1/1" : "0/1"}</div>
      </div>
    `
      )
      .join("");
  }

  // -------------------------------------------------------------------
  // 7. Panel 7: Prometheus Telemetry Charts
  // -------------------------------------------------------------------
  function initCharts() {
    const elW = document.getElementById("chart-workload-overlay");
    if (elW) {
      workloadChart = new Chart(elW.getContext("2d"), {
        type: "line",
        data: {
          labels: [],
          datasets: [
            { label: "Measured RPS", data: [], borderColor: "#4CC2F0", backgroundColor: "transparent", tension: 0.3, fill: false },
            { label: "Predicted 30s RPS", data: [], borderColor: "#33D69F", borderDash: [4, 4], backgroundColor: "transparent", tension: 0.3, fill: false },
          ],
        },
        options: {
          responsive: true,
          animation: { duration: 200 },
          scales: {
            y: { beginAtZero: true, grid: { color: "#1A222C" }, ticks: { color: "#838C99" } },
            x: { grid: { color: "#1A222C" }, ticks: { color: "#838C99" } },
          },
          plugins: { legend: { labels: { color: "#EDEFF2" } } },
        },
      });
    }

    const elM = document.getElementById("chart-monitoring-series");
    if (elM) {
      monitoringChart = new Chart(elM.getContext("2d"), {
        type: "line",
        data: {
          labels: [],
          datasets: [
            { label: "CPU %", data: [], borderColor: "#F5B843", backgroundColor: "transparent", tension: 0.3, fill: false },
            { label: "P95 Latency (s)", data: [], borderColor: "#F2685C", backgroundColor: "transparent", tension: 0.3, fill: false },
          ],
        },
        options: {
          responsive: true,
          animation: { duration: 200 },
          scales: {
            y: { beginAtZero: true, grid: { color: "#1A222C" }, ticks: { color: "#838C99" } },
            x: { grid: { color: "#1A222C" }, ticks: { color: "#838C99" } },
          },
          plugins: { legend: { labels: { color: "#EDEFF2" } } },
        },
      });
    }
  }

  function pushPoint(series, label, values) {
    series.labels.push(label);
    Object.keys(values).forEach((k) => series[k].push(values[k]));
    if (series.labels.length > MAX_POINTS) {
      series.labels.shift();
      Object.keys(values).forEach((k) => series[k].shift());
    }
  }

  async function fetchWorkloadPoint() {
    const data = await getJSON("/api/workload");
    if (!data || !workloadChart) return;
    pushPoint(workloadSeries, data.timestamp, {
      measured: data.current_rps,
      predicted: data.predicted_rps_30s,
    });
    workloadChart.data.labels = workloadSeries.labels;
    workloadChart.data.datasets[0].data = workloadSeries.measured;
    workloadChart.data.datasets[1].data = workloadSeries.predicted;
    workloadChart.update("none");
  }

  async function fetchMonitoringPoint() {
    const data = await getJSON("/api/monitoring");
    if (!data || !monitoringChart) return;
    pushPoint(monitoringSeries, data.timestamp, {
      cpu: data.cpu_percent,
      p95: data.p95_latency,
    });
    monitoringChart.data.labels = monitoringSeries.labels;
    monitoringChart.data.datasets[0].data = monitoringSeries.cpu;
    monitoringChart.data.datasets[1].data = monitoringSeries.p95;
    monitoringChart.update("none");
  }

  // -------------------------------------------------------------------
  // Startup & Polling Loops
  // -------------------------------------------------------------------
  initCharts();
  fetchGitCommits();
  fetchAIDiagnostics();
  updateOverview();

  // Poll all panels continuously for simultaneous real-time monitoring
  setInterval(updateOverview, 2000);
  setInterval(fetchWorkloadPoint, 3000);
  setInterval(fetchMonitoringPoint, 3000);
  setInterval(fetchGitCommits, 10000);
});
