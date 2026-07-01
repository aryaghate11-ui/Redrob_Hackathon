import {
  Activity,
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  BarChart3,
  BriefcaseBusiness,
  Check,
  ChevronDown,
  CircleGauge,
  Database,
  Download,
  FileSearch,
  Fingerprint,
  FlaskConical,
  Gauge,
  Import,
  LayoutDashboard,
  MapPin,
  Menu,
  Search,
  ShieldCheck,
  Sparkles,
  Star,
  UploadCloud,
  Users,
  X,
} from "lucide-react";

export const Icons = {
  Activity,
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  BarChart3,
  BriefcaseBusiness,
  Check,
  ChevronDown,
  CircleGauge,
  Database,
  Download,
  FileSearch,
  Fingerprint,
  FlaskConical,
  Gauge,
  Import,
  LayoutDashboard,
  MapPin,
  Menu,
  Search,
  ShieldCheck,
  Sparkles,
  Star,
  UploadCloud,
  Users,
  X,
};

export function MetricBar({ label, value, accent = "cyan" }) {
  return (
    <div className="metric-bar">
      <div className="metric-row">
        <span>{label}</span>
        <strong>{Math.round(value)}</strong>
      </div>
      <div className="metric-track">
        <div
          className={`metric-fill ${accent}`}
          style={{ width: `${Math.max(2, value)}%` }}
        />
      </div>
    </div>
  );
}

export function ScoreRing({ value, label }) {
  const degrees = Math.max(0, Math.min(100, value)) * 3.6;
  return (
    <div
      className="score-ring"
      style={{
        background: `conic-gradient(var(--cyan) ${degrees}deg, var(--line) ${degrees}deg)`,
      }}
    >
      <div>
        <strong>{Math.round(value)}</strong>
        <span>{label}</span>
      </div>
    </div>
  );
}

export function TierBadge({ tier }) {
  return <span className={`tier tier-${tier}`}>T{tier}</span>;
}

export function EmptyState({ title, detail }) {
  return (
    <div className="empty-state">
      <FileSearch size={28} />
      <strong>{title}</strong>
      <span>{detail}</span>
    </div>
  );
}
