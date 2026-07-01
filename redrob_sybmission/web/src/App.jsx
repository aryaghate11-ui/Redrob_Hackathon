import { useEffect, useMemo, useRef, useState } from "react";
import { getCandidates, getStatus, importDataset } from "./api";
import { EmptyState, Icons, MetricBar, ScoreRing, TierBadge } from "./components";

const nav = [
  ["jd_match", "JD Match", Icons.FileSearch],
  ["workdna", "WorkDNA", Icons.Fingerprint],
  ["skill_evidence", "Skill Evidence", Icons.ShieldCheck],
  ["career_physics", "Career Physics", Icons.Activity],
  ["assessment", "Interview", Icons.Users],
  ["explain", "Explain", Icons.FileSearch],
  ["datasets", "Datasets", Icons.Database],
];

const modelCopy = {
  jd_match: { title: "JD Match ranking", subtitle: "Paste a JD, extract role missions, and rerank candidates live" },
  workdna: { title: "WorkDNA ranking", subtitle: "Baseline evidence and job-readiness ranking" },
  skill_evidence: { title: "Skill Evidence Ratio", subtitle: "Ranks claimed skills by how strongly career evidence supports them" },
  career_physics: { title: "Career Physics", subtitle: "Ranks growth velocity, complexity, acceleration, and recovery" },
  assessment: { title: "Interview Calibration", subtitle: "Structured interviewer evidence creates a post-interview rank" },
  explain: { title: "How the ranking works", subtitle: "Simple language guide with best-vs-worst candidate examples" },
};

const tabs = ["Evidence", "Career", "Stability"];
const defaultJobDescription = `Senior AI Engineer / Applied ML Engineer
We need someone who can own retrieval, ranking, RAG, recommendation, and evaluation systems in production. The role requires hands-on Python/ML, strong product judgment, relevance metrics, offline-online evaluation, A/B testing, monitoring, and the ability to design and ship reliable systems rather than demos.`;

const missionKeywordMap = {
  production: ["production", "deployed", "deploy", "shipping", "ship", "monitoring", "observability", "reliable", "scale", "latency", "users", "operations", "on-call", "mlops"],
  retrieval: ["retrieval", "search", "ranking", "rank", "recommendation", "recommender", "rag", "vector", "embedding", "semantic", "relevance", "bm25", "llm"],
  evaluation: ["evaluation", "eval", "metric", "metrics", "benchmark", "labels", "labeling", "a/b", "ab test", "experiment", "offline-online", "human judgment", "quality"],
  ownership: ["own", "owned", "lead", "led", "architect", "design", "designed", "mentor", "senior", "principal", "responsible", "stakeholder"],
  transferability: ["product", "business", "domain", "customer", "impact", "cross-functional", "judgment", "startup", "ambiguous", "0 to 1", "end-to-end"]
};

function analyzeJobDescription(text) {
  const source = (text || "").toLowerCase();
  const raw = Object.fromEntries(Object.entries(missionKeywordMap).map(([mission, words]) => {
    const hits = words.filter((word) => source.includes(word));
    return [mission, { hits, count: hits.length }];
  }));
  const base = { production: 1, retrieval: 1, evaluation: 1, ownership: 1, transferability: 1 };
  const boosted = Object.fromEntries(Object.entries(base).map(([mission, value]) => [mission, value + Math.min(4, raw[mission].count) * 0.45]));
  const total = Object.values(boosted).reduce((sum, value) => sum + value, 0) || 1;
  const weights = Object.fromEntries(Object.entries(boosted).map(([mission, value]) => [mission, value / total]));
  const topSignals = Object.entries(raw).flatMap(([mission, item]) => item.hits.slice(0, 4).map((hit) => ({ mission, hit })));
  const emphasis = Object.entries(weights).sort((a, b) => b[1] - a[1]).map(([mission, weight]) => ({ mission, weight }));
  return { weights, raw, topSignals, emphasis };
}

function jdCandidateScore(candidate, jdProfile) {
  const mission = candidate.mission || {};
  const weights = jdProfile.weights;
  const missionScore = Object.entries(weights).reduce((sum, [key, weight]) => sum + (mission[key] || 0) * weight, 0);
  const skillProof = candidate.model_scores?.skill_evidence ?? candidate.skill_evidence?.score ?? candidate.score ?? 0;
  const physics = candidate.model_scores?.career_physics ?? candidate.career_physics?.score ?? 0;
  const availability = candidate.open_to_work ? 4 : 0;
  const responsiveness = Math.min(4, Math.max(0, Number(candidate.response_rate || 0) * 4));
  const contradictionPenalty = Math.min(18, (candidate.contradictions || 0) * 4);
  return Math.max(0, Math.min(100, missionScore * 0.72 + skillProof * 0.15 + physics * 0.08 + availability + responsiveness - contradictionPenalty));
}

function Sidebar({ active, setActive }) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">W</div>
        <div>
          <strong>WorkDNA</strong>
          <span>Evidence intelligence</span>
        </div>
      </div>
      <nav>
        {nav.map(([id, label, Icon]) => (
          <button
            key={id}
            className={active === id ? "active" : ""}
            onClick={() => setActive(id)}
          >
            <Icon size={17} />
            <span>{label}</span>
          </button>
        ))}
      </nav>
      <div className="sidebar-foot">
        <div className="offline-dot" />
        <div>
          <strong>Offline model</strong>
          <span>No network inference</span>
        </div>
      </div>
    </aside>
  );
}

function UploadDialog({ open, onClose, onImported }) {
  const inputRef = useRef(null);
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  if (!open) return null;

  async function submit() {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      await importDataset(file);
      await onImported();
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div className="modal" onMouseDown={(event) => event.stopPropagation()}>
        <div className="modal-head">
          <div>
            <h2>Import candidate dataset</h2>
            <p>JSONL or JSON using the challenge candidate schema.</p>
          </div>
          <button className="icon-button" onClick={onClose}>
            <Icons.X size={18} />
          </button>
        </div>
        <button className="dropzone" onClick={() => inputRef.current?.click()}>
          <Icons.UploadCloud size={30} />
          <strong>{file ? file.name : "Choose a dataset"}</strong>
          <span>
            {file
              ? `${(file.size / 1024 / 1024).toFixed(2)} MB ready to rank`
              : "The original dataset remains untouched"}
          </span>
          <input
            ref={inputRef}
            type="file"
            accept=".json,.jsonl,application/json"
            hidden
            onChange={(event) => setFile(event.target.files?.[0] || null)}
          />
        </button>
        <div className="schema-note">
          <Icons.ShieldCheck size={17} />
          <span>
            Processing stays on this machine. Unknown project descriptions are
            conservatively scored until reviewed.
          </span>
        </div>
        {error && <div className="error-box">{error}</div>}
        <div className="modal-actions">
          <button className="button secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            className="button primary"
            disabled={!file || busy}
            onClick={submit}
          >
            {busy ? "Ranking dataset..." : "Import and rank"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Filters({ filters, setFilters, summary }) {
  const tiers = Object.entries(summary?.tier_counts || {})
    .sort(([a], [b]) => Number(b) - Number(a))
    .map(([tier, count]) => ({ tier, count }));

  return (
    <aside className="filters">
      <div className="panel-title">
        <span>Role mission</span>
        <Icons.CircleGauge size={16} />
      </div>
      <h2>Senior AI Engineer</h2>
      <p>
        Own retrieval, ranking, evaluation, production operations, and the
        intelligence layer.
      </p>
      <div className="mission-list">
        {[
          "Hybrid retrieval",
          "Ranking evaluation",
          "Production ownership",
          "Hands-on Python",
          "Product judgment",
        ].map((item) => (
          <div key={item}>
            <Icons.Check size={14} />
            <span>{item}</span>
          </div>
        ))}
      </div>

      <div className="filter-section">
        <label>Evidence tier</label>
        <div className="tier-filter">
          <button
            className={filters.tier === "all" ? "active" : ""}
            onClick={() => setFilters({ ...filters, tier: "all" })}
          >
            All <span>{summary?.candidate_count || 0}</span>
          </button>
          {tiers.map(({ tier, count }) => (
            <button
              key={tier}
              className={filters.tier === tier ? "active" : ""}
              onClick={() => setFilters({ ...filters, tier })}
            >
              Tier {tier} <span>{count}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="filter-section">
        <label>Availability</label>
        <select
          value={filters.availability}
          onChange={(event) =>
            setFilters({ ...filters, availability: event.target.value })
          }
        >
          <option value="all">Any availability</option>
          <option value="open">Open to work</option>
          <option value="fast">&lt;=30 day notice</option>
        </select>
      </div>

      <div className="dataset-health">
        <div className="panel-title">
          <span>Dataset health</span>
          <Icons.Activity size={16} />
        </div>
        <dl>
          <div>
            <dt>Profiles</dt>
            <dd>{summary?.candidate_count?.toLocaleString() || "-"}</dd>
          </div>
          <div>
            <dt>Open to work</dt>
            <dd>{summary?.open_to_work_count?.toLocaleString() || "-"}</dd>
          </div>
          <div>
            <dt>Credibility flags</dt>
            <dd>{summary?.contradiction_count || 0}</dd>
          </div>
          <div>
            <dt>Ranking time</dt>
            <dd>{summary?.processing_seconds || "-"}s</dd>
          </div>
        </dl>
      </div>
    </aside>
  );
}

function comparisonRows(candidate, benchmark, model) {
  if (!candidate || !benchmark) return [];
  if (model === "career_physics") {
    const career = benchmark.career;
    const physics = candidate.career_physics;
    return [
      ["Current complexity", physics.current_complexity, career.current_complexity, physics.current_complexity, career.current_complexity],
      ["Velocity", Math.max(0, Math.min(100, 50 + physics.velocity * 5)), Math.max(0, Math.min(100, 50 + career.velocity * 5)), physics.velocity, career.velocity],
      ["Acceleration", Math.max(0, Math.min(100, 50 + physics.acceleration * 2)), Math.max(0, Math.min(100, 50 + career.acceleration * 2)), physics.acceleration, career.acceleration],
      ["Recovery", Math.min(100, physics.recovery), Math.min(100, career.recovery), physics.recovery, career.recovery],
      ["Year 5 projection", physics.forecast?.at(-1)?.complexity || 0, career.forecast?.at(-1) || 0, physics.forecast?.at(-1)?.complexity || 0, career.forecast?.at(-1) || 0],
    ];
  }
  return Object.entries(candidate.mission).map(([key, value]) => [key[0].toUpperCase() + key.slice(1), value, benchmark.workdna[key], value, benchmark.workdna[key]]);
}

function MedianComparison({ candidate, benchmark, model = "workdna", compact = false }) {
  const rows = comparisonRows(candidate, benchmark, model);
  return (
    <div className={`median-comparison ${compact ? "compact" : ""}`}>
      <div className="comparison-head"><div><span>Candidate vs dataset median</span><strong>{candidate.candidate_id}</strong></div><small>{benchmark?.population_size?.toLocaleString()} profiles</small></div>
      <div className="comparison-legend"><span className="employee">Employee</span><span className="median">Median</span></div>
      <div className="comparison-bars">{rows.map(([label, employee, median, employeeRaw, medianRaw]) => <div className="comparison-row" key={label}><div><span>{label}</span><small>{Number(employeeRaw).toFixed(1)} vs {Number(medianRaw).toFixed(1)}</small></div><div className="dual-track"><i className="median-bar" style={{ width: `${Math.max(1, median)}%` }} /><i className="employee-bar" style={{ width: `${Math.max(1, employee)}%` }} /></div></div>)}</div>
    </div>
  );
}
function CandidateLedger({ candidates, selected, onSelect, loading, model = "workdna", assessments = {}, benchmark }) {
  return (
    <section className="ledger">
      <div className="ledger-head">
        <div>
          <h2>{modelCopy[model]?.title || "Ranked candidates"}</h2>
          <span>{candidates.length} profiles - {modelCopy[model]?.subtitle}</span>
        </div>
        <div className="ledger-legend">
          <span>
            <i className="dot green" /> strong evidence
          </span>
          <span>
            <i className="dot amber" /> review
          </span>
        </div>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Rank</th>
              <th>Candidate</th>
              <th>Evidence</th>
              <th>Score</th>
              <th>Stability</th>
              <th>Availability</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan="6" className="loading-cell">
                  Running the offline evidence model...
                </td>
              </tr>
            ) : (
              candidates.map((candidate) => {
                const isSelected =
                  selected?.candidate_id === candidate.candidate_id;
                const stability =
                  candidate.stability?.stability_scores?.overall_stability;
                return (
                  <tr
                    key={candidate.candidate_id}
                    className={isSelected ? "selected" : ""}
                    onClick={() => onSelect(candidate)}
                  >
                    <td className="rank-cell">
                      <strong>{candidate.displayRank ?? candidate.rankings?.[model] ?? candidate.rank}</strong>
                    </td>
                    <td>
                      <div className="candidate-cell">
                        <strong>{candidate.name}</strong>
                        <span>
                          {candidate.current_title} - {candidate.current_company}
                        </span>
                        <small className="candidate-id-hover" tabIndex="0">{candidate.candidate_id}<span className="candidate-benchmark-popover"><MedianComparison candidate={candidate} benchmark={benchmark} model={model === "career_physics" ? "career_physics" : "workdna"} compact /></span></small>
                      </div>
                    </td>
                    <td>
                      <TierBadge tier={candidate.tier} />
                    </td>
                    <td className="score-cell">{(candidate.displayScore ?? candidate.model_scores?.[model] ?? candidate.score).toFixed(1)}</td>
                    <td>
                      <span
                        className={`stability ${
                          stability >= 85 ? "good" : "review"
                        }`}
                      >
                        {stability ?? "-"}
                      </span>
                    </td>
                    <td>
                      <div className="availability-cell">
                        <i
                          className={
                            candidate.open_to_work
                              ? "availability open"
                              : "availability closed"
                          }
                        />
                        <span>
                          {candidate.open_to_work
                            ? "Open"
                            : `${candidate.notice_days}d`}
                        </span>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function EvidenceTab({ candidate, benchmark }) {
  return (
    <>
      <MedianComparison candidate={candidate} benchmark={benchmark} model="workdna" />
      <div className="mission-grid">
        {Object.entries(candidate.mission).map(([label, value]) => (
          <MetricBar
            key={label}
            label={label[0].toUpperCase() + label.slice(1)}
            value={value}
            accent={value >= 80 ? "green" : value >= 60 ? "cyan" : "amber"}
          />
        ))}
      </div>
      <div className="inspector-section">
        <div className="section-label">
          <span>Strongest project evidence</span>
          <Icons.Fingerprint size={15} />
        </div>
        {candidate.evidence.length ? (
          candidate.evidence.slice(0, 3).map((item) => (
            <article className="evidence-item" key={`${item.company}-${item.title}`}>
              <div>
                <strong>{item.title}</strong>
                <span>{item.company}</span>
              </div>
              <p>{item.description}</p>
              <div className="evidence-marks">
                <span>Retrieval {item.retrieval}/5</span>
                <span>Evaluation {item.evaluation}/5</span>
                <span>Ownership {item.ownership}/5</span>
              </div>
            </article>
          ))
        ) : (
          <EmptyState
            title="No direct evidence"
            detail="This profile is ranked through transferable experience."
          />
        )}
      </div>
    </>
  );
}

function CareerTab({ candidate }) {
  return (
    <div className="career-list">
      {candidate.career_history.map((role, index) => (
        <article key={`${role.company}-${index}`}>
          <div className="timeline-node" />
          <div>
            <strong>{role.title}</strong>
            <span>
              {role.company} - {role.duration_months} months
            </span>
            <p>{role.description}</p>
          </div>
        </article>
      ))}
    </div>
  );
}

function StabilityTab({ candidate }) {
  const audit = candidate.stability;
  if (!audit) return <EmptyState title="Audit unavailable" detail="This profile has not completed the strict evidence audit." />;
  const scores = audit.stability_scores;
  const checks = audit.hard_checks;
  const metrics = [
    ["Skill proof", scores.skill_proof],
    ["Project breadth", scores.project_breadth],
    ["Narrative specificity", scores.narrative_specificity],
    ["Project reliance", scores.project_reliance],
    ["Context independence", scores.context_independence],
    ["Credibility", scores.credibility],
  ];
  return (
    <>
      <div className="stability-grid">
        {metrics.map(([label, value]) => <div key={label}><strong>{value}</strong><span>{label}</span></div>)}
      </div>
      <div className="counterfactual-list">
        <div><span>Relevant career proofs</span><strong>{checks.relevant_roles}</strong></div>
        <div><span>Distinct relevant projects</span><strong>{checks.distinct_relevant_projects}</strong></div>
        <div><span>Quantified / production / ownership roles</span><strong>{checks.quantified_roles} / {checks.production_roles} / {checks.ownership_roles}</strong></div>
        <div><span>Strict audit verdict</span><strong className={scores.overall_stability >= 70 ? "stable" : "drop"}>{audit.verdict.replaceAll("_", " ")}</strong></div>
        {(checks.failed_gates || []).map((gate) => <div key={gate}><span>Failed gate</span><strong className="drop">{gate}</strong></div>)}
      </div>
    </>
  );
}
function RecruiterRating({ rating, onChange }) {
  const current = rating || { score: 0, note: "" };
  return (
    <div className="recruiter-rating">
      <div className="section-label">
        <span>Your recruiter rating</span>
        <Icons.Star size={15} />
      </div>
      <div className="rating-row">
        <div className="stars" aria-label="Recruiter rating">
          {[1, 2, 3, 4, 5].map((value) => (
            <button
              key={value}
              className={current.score >= value ? "selected" : ""}
              aria-label={`Rate ${value} out of 5`}
              onClick={() => onChange({ ...current, score: value })}
            >
              <Icons.Star size={17} />
            </button>
          ))}
        </div>
        <strong>{current.score ? `${current.score}/5` : "Not rated"}</strong>
      </div>
      <textarea
        value={current.note}
        placeholder="Add interview notes or a hiring recommendation..."
        onChange={(event) => onChange({ ...current, note: event.target.value })}
      />
      <span className="saved-locally">Saved locally on this device</span>
    </div>
  );
}

function SkillEvidencePanel({ candidate }) {
  const skill = candidate.skill_evidence;
  return (
    <div className="model-detail">
      <div className="model-score-block"><ScoreRing value={skill.score} label="Skill proof" /><div><span>Skill Evidence Ratio</span><h3>{skill.supported_count} of {skill.claimed_count} skills supported</h3><p>Career narrative, assessment, duration, and endorsements are combined. Unsupported lists are penalized rather than rewarded.</p></div></div>
      <div className="skill-proof-columns"><div><span>Supported claims</span>{skill.supported.length ? skill.supported.map((item) => <div className="skill-proof supported" key={item.name}><Icons.Check size={13} /><strong>{item.name}</strong><small>{item.text_support ? "career text" : item.assessment_support ? "assessment" : "duration / endorsements"}</small></div>) : <p>No supported skills found.</p>}</div><div><span>Needs verification</span>{skill.unsupported.length ? skill.unsupported.map((item) => <div className="skill-proof unsupported" key={item.name}><Icons.AlertTriangle size={13} /><strong>{item.name}</strong><small>not backed by strong evidence</small></div>) : <p>All listed skills are supported.</p>}</div></div>
    </div>
  );
}

function CareerPhysicsPanel({ candidate, benchmark }) {
  const physics = candidate.career_physics;
  const historical = physics.historical || [];
  const forecast = physics.forecast || [];
  const series = [...historical, ...forecast];
  const width = 640;
  const height = 310;
  const margin = { left: 54, right: 20, top: 22, bottom: 48 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const years = series.map((point) => point.year);
  const minYear = Math.min(...years);
  const maxYear = Math.max(...years);
  const x = (year) => margin.left + ((year - minYear) / Math.max(maxYear - minYear, 1)) * plotWidth;
  const y = (value) => margin.top + (1 - value / 100) * plotHeight;
  const coordinates = (items) => items.map((point) => [x(point.year), y(point.complexity)]);
  const smoothPath = (coords) => {
    if (!coords.length) return "";
    if (coords.length === 1) return `M ${coords[0][0]} ${coords[0][1]}`;
    return coords.slice(1).reduce((path, point, index) => {
      const previous = coords[index];
      const controlX = (previous[0] + point[0]) / 2;
      return `${path} C ${controlX} ${previous[1]}, ${controlX} ${point[1]}, ${point[0]} ${point[1]}`;
    }, `M ${coords[0][0]} ${coords[0][1]}`);
  };
  const historicalPath = smoothPath(coordinates(historical));
  const forecastSeries = historical.length ? [historical.at(-1), ...forecast] : forecast;
  const forecastPath = smoothPath(coordinates(forecastSeries));
  const confidencePoints = forecast.length
    ? [
        `${x(historical.at(-1)?.year ?? forecast[0].year)},${y(historical.at(-1)?.complexity ?? forecast[0].complexity)}`,
        ...forecast.map((point) => `${x(point.year)},${y(point.high)}`),
        ...[...forecast].reverse().map((point) => `${x(point.year)},${y(point.low)}`),
      ].join(" ")
    : "";
  const yTicks = [0, 25, 50, 75, 100];
  const xTicks = years.filter((year, index) => index === 0 || index === years.length - 1 || index % Math.max(1, Math.ceil(years.length / 8)) === 0);
  const forecastStart = forecast[0]?.year;
  const benchmarkCareer = benchmark?.career || { current_complexity: 0, velocity: 0, forecast: [0, 0, 0, 0, 0] };
  const lastHistoricalYear = historical.at(-1)?.year || minYear;
  const medianHistorical = historical.map((point) => ({ year: point.year, complexity: Math.max(0, Math.min(100, benchmarkCareer.current_complexity - benchmarkCareer.velocity * (lastHistoricalYear - point.year))) }));
  const medianForecast = forecast.map((point, index) => ({ year: point.year, complexity: benchmarkCareer.forecast[index] || benchmarkCareer.current_complexity }));
  const medianPath = smoothPath(coordinates([...medianHistorical, ...medianForecast]));

  return (
    <div className="model-detail">
      <div className="physics-summary"><div><span>Career Physics score</span><strong>{physics.score}</strong><small>Rank #{physics.rank}</small></div><div><span>Capability velocity</span><strong>{physics.velocity >= 0 ? "+" : ""}{physics.velocity}</strong><small>{physics.velocity_percentile} percentile</small></div><div><span>5-year projected level</span><strong>{forecast.at(-1)?.complexity ?? "-"}</strong><small>scenario, not guarantee</small></div><div><span>Forecast confidence</span><strong>{physics.forecast_confidence}%</strong><small>uncertainty widens over time</small></div></div>
      <MedianComparison candidate={candidate} benchmark={benchmark} model="career_physics" />
      <div className="trajectory-chart">
        <div className="chart-heading"><div><span>Capability complexity trajectory</span><strong>Observed career history + five-year projection</strong></div><div className="chart-legend"><span className="observed">Observed</span><span className="projected">Projected</span><span className="range">Uncertainty range</span><span className="population">Dataset median</span></div></div>
        <div className="chart-canvas">
          <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Career capability complexity by year with a five-year forecast">
            {yTicks.map((tick) => <g key={tick}><line className="grid-line" x1={margin.left} y1={y(tick)} x2={width - margin.right} y2={y(tick)} /><text className="axis-tick y-tick" x={margin.left - 10} y={y(tick) + 4}>{tick}</text></g>)}
            {xTicks.map((tick) => <g key={tick}><line className="x-mark" x1={x(tick)} y1={height - margin.bottom} x2={x(tick)} y2={height - margin.bottom + 5} /><text className="axis-tick" x={x(tick)} y={height - margin.bottom + 19}>{tick}</text></g>)}
            <line className="axis-line" x1={margin.left} y1={margin.top} x2={margin.left} y2={height - margin.bottom} />
            <line className="axis-line" x1={margin.left} y1={height - margin.bottom} x2={width - margin.right} y2={height - margin.bottom} />
            <text className="axis-title y-title" transform={`translate(15 ${margin.top + plotHeight / 2}) rotate(-90)`}>Capability complexity (0–100)</text>
            <text className="axis-title x-title" x={margin.left + plotWidth / 2} y={height - 8}>Calendar year</text>
            {forecastStart && <><line className="forecast-divider" x1={x(forecastStart) - plotWidth / Math.max(maxYear - minYear, 1) / 2} y1={margin.top} x2={x(forecastStart) - plotWidth / Math.max(maxYear - minYear, 1) / 2} y2={height - margin.bottom} /><text className="forecast-label" x={x(forecastStart)} y={margin.top + 12}>5-year projection</text></>}
            {confidencePoints && <polygon className="confidence-band" points={confidencePoints} />}
            <path className="median-curve" d={medianPath} />
            <path className="history-curve" d={historicalPath} />
            <path className="forecast-curve" d={forecastPath} />
            {historical.map((point) => <circle className="history-point" key={`h-${point.year}`} cx={x(point.year)} cy={y(point.complexity)} r="3"><title>{point.year}: observed complexity {point.complexity}</title></circle>)}
            {forecast.map((point) => <circle className="forecast-point" key={`f-${point.year}`} cx={x(point.year)} cy={y(point.complexity)} r="3"><title>{point.year}: projected {point.complexity}, range {point.low}–{point.high}</title></circle>)}
          </svg>
        </div>
        <div className="forecast-table"><div className="forecast-row header"><span>Year</span><span>Projected complexity</span><span>Reasonable range</span></div>{forecast.map((point) => <div className="forecast-row" key={point.year}><strong>{point.year}</strong><span>{point.complexity}</span><span>{point.low}–{point.high}</span></div>)}</div>
        <p className="forecast-disclaimer">Projection uses observed project complexity, recency-weighted velocity, acceleration and recovery. It estimates a capability scenario; it does not claim to predict promotions, behavior, or actual employment outcomes.</p>
      </div>
    </div>
  );
}
const interviewDimensions = [
  ["communication", "Technical communication"],
  ["problem_solving", "Problem decomposition"],
  ["tradeoffs", "Trade-off reasoning"],
  ["collaboration", "Collaboration"],
  ["ownership", "Ownership examples"],
  ["learning", "Learning agility"],
];

function InterviewPanel({ candidate, assessment, onChange }) {
  const current = assessment || {};
  const rated = interviewDimensions.filter(([key]) => current[key]);
  const average = rated.length ? rated.reduce((sum, [key]) => sum + Number(current[key]), 0) / rated.length : 0;
  return (
    <div className="model-detail interview-panel">
      <div className="interview-score"><div><span>Pre-interview WorkDNA</span><strong>{candidate.model_scores.workdna}</strong></div><div><span>Interview evidence</span><strong>{average ? (average * 20).toFixed(1) : "Not assessed"}</strong></div><div><span>Post-interview score</span><strong>{candidate.displayScore?.toFixed(1) || candidate.model_scores.workdna}</strong></div></div>
      <p className="assessment-note">Rate only observed interview evidence. Unassessed dimensions remain neutral and do not fabricate soft-skill predictions.</p>
      <div className="assessment-grid">{interviewDimensions.map(([key, label]) => <label key={key}><span>{label}</span><select value={current[key] || ""} onChange={(event) => onChange({ ...current, [key]: Number(event.target.value) || null })}><option value="">Not assessed</option><option value="1">1 - weak evidence</option><option value="2">2 - below bar</option><option value="3">3 - meets bar</option><option value="4">4 - strong</option><option value="5">5 - exceptional</option></select></label>)}</div>
      <label className="interview-notes"><span>Interview evidence notes</span><textarea value={current.note || ""} onChange={(event) => onChange({ ...current, note: event.target.value })} placeholder="Record the answer or behavior that supports these ratings..." /></label>
      <span className="saved-locally">Saved locally on this device</span>
    </div>
  );
}

const methodology = {
  workdna: {
    title: "How WorkDNA ranks this candidate",
    summary: "A local pairwise logistic ranking model compares candidates using 23 engineered features. It learns which profile should outrank another, scores the full population, then sorts those scores into the final order.",
    formula: "Project evidence + role fit + corroboration + bounded real-world availability signals − contradictions and disqualifiers",
    steps: [
      ["1. Parse career projects", "Every role description is normalized and assigned to a stable project archetype."],
      ["2. Build evidence dimensions", "The archetype provides reviewed 0–5 depth labels, converted to a 0–100 display scale."],
      ["3. Engineer 23 features", "Best and second-best relevance, mission coverage, project count, experience fit, assessments, activity, availability and credibility are included."],
      ["4. Pairwise ranking", "A NumPy RankNet-style logistic regression learns candidate A versus candidate B preferences and produces the population order."],
    ],
  },
  skill_evidence: {
    title: "How Skill Evidence ranks this candidate",
    summary: "The model does not reward a long skill list. It checks whether each claimed skill is supported by project text, a skill assessment, sustained duration or meaningful endorsements.",
    formula: "65% supported-skill ratio + 35% WorkDNA evidence score",
    steps: [
      ["Career narrative", "A matching project or role description contributes two evidence points."],
      ["Assessment proof", "A matching assessment score of at least 50 contributes two points."],
      ["Duration and endorsement", "At least 12 months or 10 endorsements each contribute one point."],
      ["Support threshold", "A skill needs at least two evidence points; unsupported claims reduce the ratio."],
    ],
  },
  career_physics: {
    title: "How Career Physics ranks this candidate",
    summary: "Career Physics models how project complexity changes through time. It rewards candidates whose ownership, production depth, scale and measurable impact increase rather than remaining flat.",
    formula: "35% current complexity + 35% velocity percentile + 20% acceleration percentile + 10% recovery percentile",
    steps: [
      ["Complexity per role", "Ownership, production, retrieval, evaluation and transferability form an 80-point base; scale, impact and operational evidence add headroom."],
      ["Velocity", "A closed-form regression estimates the annual slope of complexity across dated roles."],
      ["Acceleration and recovery", "Recent slope change and recovery after a career dip measure momentum and resilience proxies."],
      ["Five-year scenario", "A bounded recency-weighted projection approaches a personalized ceiling and widens its uncertainty every year."],
    ],
  },
};

const dimensionGlossary = [
  ["Production", "Evidence that work was shipped, deployed, monitored or operated for real users—not only a prototype."],
  ["Retrieval", "Depth in search, ranking, recommendation, semantic retrieval, re-ranking or information-retrieval systems."],
  ["Evaluation", "Use of metrics, experiments, benchmarks, validation, A/B tests or measurable quality checks."],
  ["Ownership", "Whether the candidate led, designed, architected or owned outcomes instead of only assisting."],
  ["Transferability", "How directly the demonstrated project pattern can be applied to the target role, even when exact keywords differ."],
];

function CandidateSummary({ candidate, model }) {
  const supported = candidate.skill_evidence?.supported_count || 0;
  const claimed = candidate.skill_evidence?.claimed_count || 0;
  const physics = candidate.career_physics;
  const modelSentence = model === "career_physics"
    ? `Their capability complexity is ${physics.current_complexity.toFixed(1)}, with velocity at the ${physics.velocity_percentile.toFixed(0)}th population percentile and a five-year scenario of ${physics.forecast?.at(-1)?.complexity ?? "-"}.`
    : model === "skill_evidence"
      ? `${supported} of ${claimed} claimed skills are supported by career, assessment, duration or endorsement evidence.`
      : `Their strongest evidence is ${Object.entries(candidate.mission).sort((a, b) => b[1] - a[1])[0]?.[0]}, while the strict audit score is ${candidate.stability?.stability_scores?.overall_stability ?? "-"}/100.`;
  return (
    <section className="candidate-summary-card">
      <div className="section-label"><span>Candidate summary</span><Icons.Sparkles size={16} /></div>
      <p>{candidate.summary || candidate.reasoning}</p>
      <p>{modelSentence} {candidate.open_to_work ? "They are currently marked open to work." : `They are not marked open to work and report a ${candidate.notice_days}-day notice period.`}</p>
    </section>
  );
}

function ModelMethodology({ model }) {
  const selected = methodology[model] || methodology.workdna;
  return (
    <details className="model-methodology">
      <summary><span>{selected.title}</span><Icons.ChevronDown size={16} /></summary>
      <div className="methodology-body">
        <p>{selected.summary}</p>
        <div className="formula-block"><span>Ranking formula</span><strong>{selected.formula}</strong></div>
        <div className="methodology-steps">{selected.steps.map(([title, detail]) => <article key={title}><strong>{title}</strong><p>{detail}</p></article>)}</div>
        {model === "workdna" && <div className="dimension-glossary"><span>What the five WorkDNA dimensions mean</span>{dimensionGlossary.map(([term, meaning]) => <div key={term}><strong>{term}</strong><p>{meaning}</p></div>)}</div>}
      </div>
    </details>
  );
}
function CandidateInspector({ candidate, rating, onRatingChange, model = "workdna", assessment, onAssessmentChange, benchmark, expanded, onToggle }) {
  const [tab, setTab] = useState("Evidence");
  if (!candidate) {
    return (
      <aside className={`inspector ${expanded ? "expanded" : "collapsed"}`}>
        <button className="inspector-toggle" onClick={onToggle}><Icons.ChevronDown size={18} /><span>{expanded ? "Collapse" : "Details"}</span></button>
        <EmptyState
          title="Select a candidate"
          detail="Inspect mission coverage, work evidence, and stability."
        />
      </aside>
    );
  }
  const stability =
    candidate.stability?.stability_scores?.overall_stability || 0;
  return (
    <aside className={`inspector ${expanded ? "expanded" : "collapsed"}`}>
      <button className="inspector-toggle" onClick={onToggle} aria-label={expanded ? "Collapse candidate details" : "Expand candidate details"}><Icons.ChevronDown size={18} /><span>{expanded ? "Collapse" : "Details"}</span></button>
      <div className="inspector-content">
      <div className="candidate-hero">
        <div className="candidate-meta">
          <span>
            #{candidate.displayRank ?? candidate.rankings?.[model] ?? candidate.rank} - <TierBadge tier={candidate.tier} />
          </span>
          <h2>{candidate.name}</h2>
          <p>
            {candidate.current_title} at {candidate.current_company}
          </p>
          <div className="candidate-facts">
            <span>
              <Icons.BriefcaseBusiness size={14} />
              {candidate.years} years
            </span>
            <span>
              <Icons.MapPin size={14} />
              {candidate.location}
            </span>
          </div>
        </div>
        <ScoreRing value={candidate.displayScore ?? candidate.model_scores?.[model] ?? candidate.score} label={model === "career_physics" ? "Physics" : model === "skill_evidence" ? "Skill proof" : model === "assessment" ? "Post interview" : "WorkDNA"} />
      </div>
      <CandidateSummary candidate={candidate} model={model} />
      <ModelMethodology key={model} model={model} />

      {model === "skill_evidence" ? (
        <SkillEvidencePanel candidate={candidate} />
      ) : model === "career_physics" ? (
        <CareerPhysicsPanel candidate={candidate} benchmark={benchmark} />
      ) : model === "assessment" ? (
        <InterviewPanel candidate={candidate} assessment={assessment} onChange={onAssessmentChange} />
      ) : (
        <>
          <div className="trust-line"><div><Icons.ShieldCheck size={16} /><span>Strict evidence audit</span></div><strong>{stability || "-"}/100</strong></div>
          <div className="tabs">{tabs.map((item) => <button key={item} className={tab === item ? "active" : ""} onClick={() => setTab(item)}>{item}</button>)}</div>
          <div className="tab-content">{tab === "Evidence" && <EvidenceTab candidate={candidate} benchmark={benchmark} />}{tab === "Career" && <CareerTab candidate={candidate} />}{tab === "Stability" && <StabilityTab candidate={candidate} />}</div>
          <div className="reasoning"><span>Recruiter rationale</span><p>{candidate.reasoning}</p></div>
          <RecruiterRating rating={rating} onChange={onRatingChange} />
        </>
      )}
      </div>
    </aside>
  );
}

function ProcessOverview({ status, onNavigate }) {
  const stages = [
    ["01", "Understand the JD", "Convert the role into five success missions and explicit disqualifiers."],
    ["02", "Extract work evidence", "Map 300,171 career entries into 44 stable project archetypes."],
    ["03", "Create digital twins", "Compare candidates with the same work evidence but different real-world signals."],
    ["04", "Learn pairwise order", "Train our local model to choose the stronger candidate in each comparison."],
    ["05", "Stress-test the answer", "Remove skills, inject keywords, and delete project evidence to verify causality."],
  ];
  return (
    <section className="process-page">
      <div className="process-intro">
        <div>
          <span className="page-index">WorkDNA methodology</span>
          <h2>From 100,000 profiles to an evidence-defensible shortlist</h2>
          <p>The hackathon asked for a trustworthy top 100 under a five-minute, CPU-only, no-network constraint. This is the complete path behind the rating.</p>
        </div>
        <div className="process-stat">
          <strong>{status?.summary?.candidate_count?.toLocaleString() || "100,000"}</strong>
          <span>candidates ranked offline</span>
        </div>
      </div>
      <div className="process-flow">
        {stages.map(([number, title, detail]) => (
          <article key={number}>
            <span>{number}</span>
            <div><h3>{title}</h3><p>{detail}</p></div>
          </article>
        ))}
      </div>
      <div className="challenge-brief">
        <div><Icons.BriefcaseBusiness size={20} /><span>What was asked</span></div>
        <ul>
          <li>Understand the role beyond keywords</li>
          <li>Use career, behavioral, and platform evidence</li>
          <li>Return exactly 100 ranked candidates with factual reasoning</li>
          <li>Finish within five minutes on CPU with no network</li>
        </ul>
        <button className="button primary" onClick={() => onNavigate("evidence")}>Explore the evidence engine</button>
      </div>
    </section>
  );
}

function EvidenceLab({ candidates, status }) {
  const sample = candidates[0];
  const stages = [
    ["Raw profile", "Career descriptions, skills, dates and Redrob activity"],
    ["Project DNA", "Problem, action, ownership, scale, evaluation and result"],
    ["Archetype label", "Reviewed relevance tier and mission dimensions"],
    ["23 model features", "Technical evidence plus bounded hireability factors"],
  ];
  return (
    <section className="evidence-page">
      <div className="lab-head">
        <div><span className="page-index">System 1</span><h2>WorkDNA Evidence Engine</h2><p>Why a project is trusted, and why a skill list alone is not.</p></div>
        <div className="lab-metrics"><div><strong>44</strong><span>project archetypes</span></div><div><strong>23</strong><span>model features</span></div><div><strong>{status?.summary?.contradiction_count || 68}</strong><span>credibility flags</span></div></div>
      </div>
      <div className="evidence-pipeline">
        {stages.map(([title, detail], index) => <article key={title}><span>{index + 1}</span><h3>{title}</h3><p>{detail}</p>{index < stages.length - 1 && <Icons.ArrowDownRight size={18} />}</article>)}
      </div>
      {sample && <div className="live-evidence-example">
        <div className="example-source"><span>Live example - Rank #{sample.rank}</span><h3>{sample.current_title} at {sample.current_company}</h3><p>{sample.evidence?.[0]?.description || sample.summary}</p></div>
        <div className="example-output"><div><span>Evidence tier</span><TierBadge tier={sample.tier} /></div>{Object.entries(sample.mission).map(([key, value]) => <MetricBar key={key} label={key} value={value} accent={value >= 80 ? "green" : "cyan"} />)}</div>
      </div>}
      <div className="anti-keyword-proof"><Icons.ShieldCheck size={20} /><div><strong>Anti-keyword safeguard</strong><p>Perfect AI keyword injection changes zero scores. Removing genuine project evidence drops Tier-5 candidates by a median 8.67 model points.</p></div></div>
    </section>
  );
}

function TwinCandidate({ label, candidate, winner }) {
  return (
    <article className={`twin-card ${winner ? "winner" : ""}`}>
      <div className="twin-label"><span>{label}</span>{winner && <strong>Model preference</strong>}</div>
      <h3>{candidate.name}</h3><p>{candidate.current_title} - {candidate.current_company}</p>
      <dl><div><dt>Same work archetype</dt><dd>{candidate.best_archetype_id?.replace("ARCH_", "")}</dd></div><div><dt>Open to work</dt><dd>{candidate.open_to_work ? "Yes" : "No"}</dd></div><div><dt>Response rate</dt><dd>{Math.round(candidate.response_rate * 100)}%</dd></div><div><dt>Notice</dt><dd>{candidate.notice_days} days</dd></div><div><dt>Activity</dt><dd>{candidate.activity_score}</dd></div></dl>
      <div className="twin-result"><span>Rank</span><strong>#{candidate.rank}</strong><small>Score {candidate.score.toFixed(1)}</small></div>
    </article>
  );
}

function TwinAudit({ candidates }) {
  const groups = useMemo(() => {
    const map = new Map();
    candidates.forEach((candidate) => {
      const key = candidate.best_archetype_id;
      if (!key) return;
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(candidate);
    });
    return [...map.values()].filter((group) => group.length >= 2).map((group) => [group[0], group[group.length - 1]]);
  }, [candidates]);
  const [example, setExample] = useState(0);
  const pair = groups[example % Math.max(groups.length, 1)] || candidates.slice(0, 2);
  if (pair.length < 2) return <EmptyState title="Twin pair unavailable" detail="Load at least two candidates sharing a project archetype." />;
  const [better, weaker] = pair[0].rank < pair[1].rank ? pair : [pair[1], pair[0]];
  return (
    <section className="twin-page">
      <div className="lab-head"><div><span className="page-index">System 2 + 3</span><h2>Digital Twin Ranking Lab</h2><p>Hold work evidence constant. Change one real-world factor. Observe whether ranking moves rationally.</p></div><button className="button secondary" onClick={() => setExample((value) => value + 1)}><Icons.FlaskConical size={16} />Next real twin</button></div>
      <div className="twin-steps">{[["1", "Match", "Find identical dominant project archetypes"], ["2", "Control", "Keep technical evidence constant"], ["3", "Compare", "Expose behavior and credibility differences"], ["4", "Decide", "Learn which candidate should rank higher"]].map(([n,t,d]) => <div key={n}><span>{n}</span><strong>{t}</strong><small>{d}</small></div>)}</div>
      <div className="twin-comparison"><TwinCandidate label="Candidate A" candidate={better} winner /><div className="versus"><span>PAIRWISE</span><strong>VS</strong><small>same Project DNA</small></div><TwinCandidate label="Candidate B" candidate={weaker} /></div>
      <div className="decision-explainer"><div><Icons.Fingerprint size={20} /><span>Controlled evidence</span><strong>Same archetype: {better.best_archetype_id}</strong></div><div><Icons.Activity size={20} /><span>Observed difference</span><strong>{better.open_to_work !== weaker.open_to_work ? "Availability changed" : better.notice_days !== weaker.notice_days ? "Notice period changed" : "Engagement behavior changed"}</strong></div><div><Icons.Gauge size={20} /><span>Ranking impact</span><strong>{Math.abs(weaker.rank - better.rank)} positions</strong></div></div>
      <div className="twin-note"><Icons.AlertTriangle size={18} /><p><strong>This does not let behavior replace technical fit.</strong> Digital twins are only used after candidates share comparable work evidence. A marketing profile with perfect activity still cannot outrank a Tier-5 search engineer.</p></div>
    </section>
  );
}

function JDMatchPanel({ jdText, setJdText, jdProfile, onUseDefault }) {
  const missionLabels = {
    production: "Production",
    retrieval: "Retrieval / Ranking",
    evaluation: "Evaluation",
    ownership: "Ownership",
    transferability: "Transferability",
  };
  return (
    <section className="jd-match-panel">
      <div className="jd-editor-card">
        <div className="section-heading compact">
          <span className="page-index">Live JD understanding</span>
          <h2>Paste a job description. The ranking adapts.</h2>
          <p>The system extracts role missions from the JD and reranks candidates using evidence already computed from the dataset. No API call, no hallucinated requirements.</p>
        </div>
        <textarea
          value={jdText}
          onChange={(event) => setJdText(event.target.value)}
          placeholder="Paste the target job description here..."
        />
        <div className="jd-actions">
          <button className="button secondary" onClick={onUseDefault}>Use AI ranking JD</button>
          <span>{jdText.trim().split(/\s+/).filter(Boolean).length} words analyzed locally</span>
        </div>
      </div>
      <div className="jd-signal-card">
        <div className="jd-signal-head">
          <strong>Extracted mission weights</strong>
          <small>Used to rerank the candidate ledger below</small>
        </div>
        <div className="jd-weight-list">
          {jdProfile.emphasis.map(({ mission, weight }) => (
            <MetricBar key={mission} label={missionLabels[mission]} value={weight * 100} accent={weight >= 0.24 ? "green" : "cyan"} />
          ))}
        </div>
        <div className="jd-chip-cloud">
          {jdProfile.topSignals.length ? jdProfile.topSignals.slice(0, 14).map(({ mission, hit }) => <span key={`${mission}-${hit}`}>{hit}</span>) : <span>No strong mission terms yet</span>}
        </div>
        <p className="jd-note">Demo-safe interpretation: keywords only set role priorities; candidates still win or lose through project evidence, skill proof, trajectory, and audit checks.</p>
      </div>
    </section>
  );
}
function ExplainPage() {
  const modelCards = [
    {
      title: "WorkDNA",
      question: "Can this person do this exact job?",
      formula: "Project evidence + production proof + evaluation maturity + ownership + transferability - contradictions",
      points: ["Reads the career/project text", "Scores production, retrieval, evaluation, ownership, and transferability", "Rewards real shipped ranking/search/RAG systems over generic AI keywords"],
    },
    {
      title: "Skill Evidence Ratio",
      question: "Are their claimed skills actually proven?",
      formula: "65% supported-skill ratio + 35% WorkDNA evidence score",
      points: ["Checks every claimed skill against project text, assessments, duration, and endorsements", "Penalizes unsupported skill lists", "Prevents keyword stuffing from winning"],
    },
    {
      title: "Career Physics",
      question: "How is this candidate moving over time?",
      formula: "35% current complexity + 35% velocity + 20% acceleration + 10% recovery",
      points: ["Turns each role into a complexity score", "Plots complexity year by year", "Ranks growth, recovery, acceleration, and plateau risk"],
    },
  ];

  const rows = [
    ["Role fit", "Search Engineer building ranking/RAG systems", "Accountant with operations, marketing, support, design history"],
    ["WorkDNA", "100.00 - Rank #1", "0.00 - Rank #100,000"],
    ["Skill Evidence", "81.43 - 10 of 14 skills supported", "0.00 - 0 of 5 skills supported"],
    ["Career Physics", "72.88 - strong current complexity and recovery", "65.04 - improving career movement, but not role fit"],
    ["Why it matters", "Direct evidence for this AI ranking challenge", "Some operational growth, but no AI/retrieval proof"],
  ];

  const timeline = [
    ["Nisha / Apple ML Engineer", "2018", "85.00", "Owned ranking layer, relevance labels, learning-to-rank"],
    ["Nisha / Freshworks ML Engineer", "2019", "60.36", "RAG support chatbot and evaluation framework"],
    ["Nisha / Aganitha ML Engineer", "2021", "80.00", "Ranking models, offline-online correlation, product metrics"],
    ["Nisha / Sarvam AI Search Engineer", "2023", "85.00", "Current high-complexity search/ranking ownership"],
    ["Arnav / Infosys Graphic Designer", "2018", "3.84", "Brand/design work, weak fit for AI ranking"],
    ["Arnav / Pied Piper Accountant", "2025", "25.48", "Owned operations across 3 warehouses, team of 80, 22% productivity gain"],
  ];

  const sanityChecks = [
    {
      id: "CAND_0064326",
      name: "Nisha Pillai",
      type: "Obvious winner",
      naive: "Keyword search likes her because she has search, ranking, RAG, and ML terms.",
      ours: "We also rank her #1, but because the projects prove ownership, evaluation, production impact, and transferability.",
      verdict: "Correct agreement",
      scores: "WorkDNA 100.00 / Skill 81.43 / Physics 72.88",
    },
    {
      id: "CAND_0056983",
      name: "Arnav Mittal",
      type: "Keyword stuffer trap",
      naive: "A simple parser may notice Rust, Next.js, Redis, MongoDB, Salesforce CRM and keep him in the pool.",
      ours: "We reject him: 0 of 5 skills supported, 5 contradictions, no AI/retrieval/ML production evidence.",
      verdict: "Correct disagreement",
      scores: "WorkDNA 0.00 / Skill 0.00 / Physics 65.04",
    },
    {
      id: "CAND_0007412",
      name: "Pranav Shah",
      type: "Strong but needs interview question",
      naive: "Keyword ranking would probably place him at the very top because he has RAG, Pinecone, BM25, recsys, and ML projects.",
      ours: "We keep him high on fit, but Career Physics warns that current complexity fell from an earlier 85 peak to 60.36.",
      verdict: "Nuanced disagreement",
      scores: "WorkDNA 99.91 / Skill 89.13 / Physics 25.44",
    },
    {
      id: "CAND_0036863",
      name: "Vikram Bansal",
      type: "Clean skill-proof candidate",
      naive: "A keyword model sees many relevant ML terms but cannot tell whether the list is believable.",
      ours: "Skill Evidence ranks him #1 because the claimed skills are heavily corroborated instead of just listed.",
      verdict: "Proof over volume",
      scores: "WorkDNA 95.23 / Skill 98.33 / Physics 67.45",
    },
    {
      id: "CAND_0008425",
      name: "Myra Krishnan",
      type: "High-growth outlier",
      naive: "Keyword rank might miss the story if she is not the absolute top keyword overlap candidate.",
      ours: "Career Physics ranks her #1 because her complexity, velocity, acceleration, and recovery are the strongest trajectory pattern.",
      verdict: "Trajectory signal found",
      scores: "WorkDNA 96.21 / Skill 83.38 / Physics 95.17",
    },
  ];

  return (
    <section className="explain-page">
      <div className="explain-hero">
        <div>
          <span className="page-index">Judge-friendly explanation</span>
          <h2>We do not ask only who matches keywords. We ask three recruiter questions.</h2>
          <p>WorkDNA checks job fit, Skill Evidence checks whether claims are proven, and Career Physics checks whether the candidate is growing or plateauing.</p>
        </div>
        <div className="explain-equation">
          <strong>Final idea</strong>
          <span>Fit + proof + movement</span>
          <small>Three different lenses, one trustworthy shortlist.</small>
        </div>
      </div>

      <div className="explain-model-grid">
        {modelCards.map((card) => (
          <article key={card.title}>
            <h3>{card.title}</h3>
            <p className="plain-question">{card.question}</p>
            <code>{card.formula}</code>
            <ul>{card.points.map((point) => <li key={point}>{point}</li>)}</ul>
          </article>
        ))}
      </div>

      <div className="sanity-section">
        <div className="section-heading">
          <span className="page-index">Stress-test slide</span>
          <h2>Where keyword search gets it wrong</h2>
          <p>These five real candidates are the sanity check. The model should agree with keywords when the evidence is real, disagree when skills are unsupported, and add nuance when trajectory changes the recruiter question.</p>
        </div>
        <div className="sanity-grid">
          {sanityChecks.map((item) => (
            <article key={item.id} className="sanity-card">
              <div className="sanity-card-head">
                <span>{item.type}</span>
                <strong>{item.verdict}</strong>
              </div>
              <h3>{item.id} / {item.name}</h3>
              <div className="sanity-compare">
                <div>
                  <small>Naive keyword view</small>
                  <p>{item.naive}</p>
                </div>
                <div>
                  <small>Our evidence engine</small>
                  <p>{item.ours}</p>
                </div>
              </div>
              <footer>{item.scores}</footer>
            </article>
          ))}
        </div>
        <div className="sanity-demo-line">
          <Icons.AlertTriangle size={18} />
          <p><strong>Judge line:</strong> If our ranking always agreed with keywords, it would not be intelligent. The win is that it agrees only when the evidence is real, and disagrees when the resume is noisy.</p>
        </div>
      </div>

      <div className="comparison-section">
        <div className="section-heading">
          <span className="page-index">Real dataset comparison</span>
          <h2>Best candidate vs worst candidate</h2>
          <p>This shows why multiple models are useful. The worst WorkDNA candidate still has some career movement, but no evidence for this AI ranking role.</p>
        </div>
        <div className="comparison-cards">
          <article className="candidate-example best">
            <span>Best fit</span>
            <h3>CAND_0064326 / Nisha Pillai</h3>
            <p>Search Engineer at Sarvam AI with direct ranking, retrieval, RAG, labeling, evaluation, and production ML evidence.</p>
            <div className="score-row"><ScoreRing value={100} label="WorkDNA" /><ScoreRing value={81.43} label="Skill proof" /><ScoreRing value={72.88} label="Physics" /></div>
          </article>
          <article className="candidate-example weak">
            <span>Weakest role fit</span>
            <h3>CAND_0056983 / Arnav Mittal</h3>
            <p>Accountant/operations profile with unsupported technical skills and no direct AI, ranking, retrieval, or ML production evidence.</p>
            <div className="score-row"><ScoreRing value={0} label="WorkDNA" /><ScoreRing value={0} label="Skill proof" /><ScoreRing value={65.04} label="Physics" /></div>
          </article>
        </div>
        <table className="explain-table">
          <tbody>{rows.map(([label, best, weak]) => <tr key={label}><th>{label}</th><td>{best}</td><td>{weak}</td></tr>)}</tbody>
        </table>
      </div>

      <div className="career-physics-explain">
        <div className="section-heading">
          <span className="page-index">Career Physics, simply</span>
          <h2>How does the model decide which year or role is high?</h2>
          <p>Every role becomes a point on a timeline. A role scores high when its text proves ownership, shipped work, retrieval/ranking depth, evaluation maturity, scale, and measurable impact.</p>
        </div>
        <div className="physics-rule-grid">
          {["Ownership: owned, led, designed, architected", "Production: shipped, deployed, monitored, real users", "Retrieval: search, ranking, RAG, recommendation, relevance", "Evaluation: labels, metrics, A/B tests, human judgment", "Impact: revenue, percent gains, users, latency, cost or time saved"].map((rule) => <div key={rule}>{rule}</div>)}
        </div>
        <table className="explain-table timeline-table">
          <thead><tr><th>Timeline point</th><th>Year</th><th>Complexity</th><th>Why it scored that way</th></tr></thead>
          <tbody>{timeline.map(([role, year, score, why]) => <tr key={role}><td>{role}</td><td>{year}</td><td>{score}</td><td>{why}</td></tr>)}</tbody>
        </table>
        <div className="demo-script">
          <Icons.Sparkles size={20} />
          <p><strong>Demo line:</strong> WorkDNA tells us whether they can do this job. Skill Evidence tells us whether their skills are backed by proof. Career Physics tells us whether they are moving upward, recovering, or plateauing.</p>
        </div>
      </div>
    </section>
  );
}
function DatasetPage({ status, onImport }) {
  return <section className="dataset-page"><div><Icons.Database size={34} /><span className="page-index">Local dataset workspace</span><h2>{status?.dataset?.name || "Candidate dataset"}</h2><p>The original challenge data remains untouched. Import a compatible JSON or JSONL file to run the same offline model end to end.</p><dl><div><dt>Profiles</dt><dd>{status?.summary?.candidate_count?.toLocaleString()}</dd></div><div><dt>Mode</dt><dd>CPU - offline</dd></div><div><dt>Model</dt><dd>Pairwise WorkDNA</dd></div></dl><button className="button primary" onClick={onImport}><Icons.Import size={16} />Import another dataset</button></div></section>;
}

function AnalyticsStrip({ candidates, status }) {
  const top = candidates.slice(0, 100);
  const robust = top.filter(
    (item) =>
      item.stability?.verdict === "robust_evidence_driven",
  ).length;
  const open = top.filter((item) => item.open_to_work).length;
  const average =
    top.reduce((sum, item) => sum + item.score, 0) / Math.max(top.length, 1);
  return (
    <footer className="analytics-strip">
      <div>
        <span>Top-100 evidence score</span>
        <strong>{average.toFixed(1)}</strong>
        <small>mean normalized score</small>
      </div>
      <div>
        <span>Robust certificates</span>
        <strong>{robust}</strong>
        <small>counterfactual verified</small>
      </div>
      <div>
        <span>Open to work</span>
        <strong>{open}</strong>
        <small>within current shortlist</small>
      </div>
      <div className="trust-summary">
        <div className="trust-bars">
          <i style={{ width: "100%" }} />
          <i style={{ width: "95%" }} />
          <i style={{ width: "89%" }} />
        </div>
        <div>
          <span>Model trust</span>
          <strong>Evidence-led</strong>
          <small>keywords 0% causal influence</small>
        </div>
      </div>
      <div className="dataset-foot">
        <span>Active dataset</span>
        <strong>{status?.dataset?.name || "Loading..."}</strong>
        <small>{status?.summary?.candidate_count?.toLocaleString()} profiles</small>
      </div>
    </footer>
  );
}

export function App() {
  const [active, setActive] = useState("workdna");
  const [status, setStatus] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [benchmark, setBenchmark] = useState(null);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [inspectorExpanded, setInspectorExpanded] = useState(true);
  const [jdText, setJdText] = useState(defaultJobDescription);
  const [ratings, setRatings] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("workdna-ratings") || "{}");
    } catch {
      return {};
    }
  });
  const [assessments, setAssessments] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("workdna-assessments") || "{}");
    } catch {
      return {};
    }
  });
  const [filters, setFilters] = useState({
    search: "",
    tier: "all",
    availability: "all",
  });

  async function refreshStatus() {
    const nextStatus = await getStatus();
    setStatus(nextStatus);
    return nextStatus;
  }

  async function refreshCandidates(nextFilters = filters) {
    setLoading(true);
    try {
      const payload = await getCandidates({ ...nextFilters, model: ["assessment", "jd_match"].includes(active) ? "workdna" : active });
      setCandidates(payload.items);
      setBenchmark(payload.benchmark);
      setSelected((current) => {
        if (!payload.items.length) return null;
        if (
          current &&
          payload.items.some(
            (item) => item.candidate_id === current.candidate_id,
          )
        )
          return current;
        return payload.items[0];
      });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    Promise.all([refreshStatus(), refreshCandidates()]).catch(console.error);
  }, []);

  useEffect(() => {
    const timeout = setTimeout(() => refreshCandidates(filters), 180);
    return () => clearTimeout(timeout);
  }, [filters, active]);

  useEffect(() => {
    localStorage.setItem("workdna-ratings", JSON.stringify(ratings));
  }, [ratings]);

  useEffect(() => {
    localStorage.setItem("workdna-assessments", JSON.stringify(assessments));
  }, [assessments]);

  function updateAssessment(candidateId, value) {
    setAssessments((current) => ({ ...current, [candidateId]: value }));
  }

  function updateRating(candidateId, value) {
    setRatings((current) => ({ ...current, [candidateId]: value }));
  }

  async function afterImport() {
    await refreshStatus();
    await refreshCandidates({ search: "", tier: "all", availability: "all" });
    setFilters({ search: "", tier: "all", availability: "all" });
  }

  const jdProfile = useMemo(() => analyzeJobDescription(jdText), [jdText]);

  const displayCandidates = useMemo(() => {
    if (active === "jd_match") {
      const ranked = candidates.map((candidate) => ({
        ...candidate,
        displayScore: jdCandidateScore(candidate, jdProfile),
        jdScore: jdCandidateScore(candidate, jdProfile),
      })).sort((a, b) => b.displayScore - a.displayScore || (a.rankings?.workdna ?? a.rank) - (b.rankings?.workdna ?? b.rank));
      return ranked.map((candidate, index) => ({ ...candidate, displayRank: index + 1 }));
    }
    if (active !== "assessment") {
      return candidates.map((candidate) => ({
        ...candidate,
        displayRank: candidate.rankings?.[active] ?? candidate.rank,
        displayScore: candidate.model_scores?.[active] ?? candidate.score,
      }));
    }
    const ranked = candidates.map((candidate) => {
      const assessment = assessments[candidate.candidate_id] || {};
      const values = interviewDimensions.map(([key]) => assessment[key]).filter(Boolean).map(Number);
      const interviewScore = values.length ? (values.reduce((sum, value) => sum + value, 0) / values.length) * 20 : 50;
      return {
        ...candidate,
        displayScore: 0.7 * candidate.model_scores.workdna + 0.3 * interviewScore,
      };
    }).sort((a, b) => b.displayScore - a.displayScore || a.candidate_id.localeCompare(b.candidate_id));
    return ranked.map((candidate, index) => ({ ...candidate, displayRank: index + 1 }));
  }, [candidates, active, assessments, jdProfile]);

  const displaySelected = useMemo(() => {
    if (!displayCandidates.length) return null;
    return displayCandidates.find((candidate) => candidate.candidate_id === selected?.candidate_id) || displayCandidates[0];
  }, [displayCandidates, selected]);
  const title = modelCopy[active]?.title || "Dataset workspace";

  function exportCurrentRanking() {
    const rows = displayCandidates.slice(0, 100).map((candidate) => ({
      rank: candidate.displayRank,
      candidate_id: candidate.candidate_id,
      score: Number(candidate.displayScore || 0).toFixed(2),
      title: candidate.title,
      location: candidate.location,
      model: active,
    }));
    const headers = Object.keys(rows[0] || {});
    const escape = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;
    const csv = [headers.join(","), ...rows.map((row) => headers.map((key) => escape(row[key])).join(","))].join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${active}-ranking.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="app-shell">
      <Sidebar active={active} setActive={setActive} />
      <main>
        <header className="topbar">
          <div>
            <h1>{title}</h1>
            <span>{modelCopy[active]?.subtitle || status?.dataset?.name || "Loading..."}</span>
          </div>
          <div className="top-actions">
            {active === "explain" ? (
              <button className="button primary" onClick={() => setActive("workdna")}>
                <Icons.Fingerprint size={16} />
                Open ranking
              </button>
            ) : (
              <>
                <div className="search">
                  <Icons.Search size={16} />
                  <input
                    value={filters.search}
                    onChange={(event) =>
                      setFilters({ ...filters, search: event.target.value })
                    }
                    placeholder="Search title, company, location..."
                  />
                </div>
                <button
                  className="button secondary"
                  onClick={() => setUploadOpen(true)}
                >
                  <Icons.Import size={16} />
                  Import dataset
                </button>
                <button className="button primary" onClick={exportCurrentRanking}>
                  <Icons.Download size={16} />
                  Export current ranking
                </button>
              </>
            )}
          </div>
        </header>

        {active === "jd_match" && <JDMatchPanel jdText={jdText} setJdText={setJdText} jdProfile={jdProfile} onUseDefault={() => setJdText(defaultJobDescription)} />}

        {active !== "datasets" && active !== "explain" && (
          <div className={`workspace ${inspectorExpanded ? "inspector-open" : "inspector-closed"}`}>
            <Filters filters={filters} setFilters={setFilters} summary={status?.summary} />
            <CandidateLedger
              candidates={displayCandidates}
              selected={displaySelected}
              onSelect={setSelected}
              loading={loading}
              model={active}
              assessments={assessments}
              benchmark={benchmark}
            />
            <CandidateInspector
              candidate={displaySelected}
              model={active === "jd_match" ? "workdna" : active}
              rating={displaySelected ? ratings[displaySelected.candidate_id] : null}
              onRatingChange={(value) => displaySelected && updateRating(displaySelected.candidate_id, value)}
              assessment={displaySelected ? assessments[displaySelected.candidate_id] : {}}
              onAssessmentChange={(value) => displaySelected && updateAssessment(displaySelected.candidate_id, value)}
              benchmark={benchmark}
              expanded={inspectorExpanded}
              onToggle={() => setInspectorExpanded((value) => !value)}
            />
          </div>
        )}
        {active === "explain" && <ExplainPage />}
        {active === "datasets" && <DatasetPage status={status} onImport={() => setUploadOpen(true)} />}
        <AnalyticsStrip candidates={displayCandidates} status={status} />
      </main>
      <UploadDialog
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onImported={afterImport}
      />
    </div>
  );
}
