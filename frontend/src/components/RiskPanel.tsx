import type { AppState, CoachPosition, RiskScore } from '../hooks/useWebSockets';

interface Props {
  state: AppState;
}

const RISK_COLOR: Record<string, string> = {
  none: 'text-green-400 border-green-800 bg-green-900/20',
  low: 'text-yellow-400 border-yellow-700 bg-yellow-900/20',
  moderate: 'text-orange-400 border-orange-700 bg-orange-900/20',
  severe: 'text-red-400 border-red-700 bg-red-900/30',
};

const RISK_LABEL: Record<string, string> = {
  none: 'CLEAR',
  low: 'LOW',
  moderate: 'MODERATE',
  severe: 'SEVERE',
};

function CoachCard({ coach }: { coach: CoachPosition }) {
  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 p-3 text-sm">
      <div className="flex justify-between items-center mb-1">
        <span className="font-bold text-white font-mono">Coach {coach.coach_id}</span>
        <span className={`text-xs px-2 py-0.5 rounded border font-bold ${coach.matched ? 'text-green-400 border-green-800 bg-green-900/20' : 'text-gray-500 border-gray-700'}`}>
          {coach.matched ? 'MATCHED' : 'UNMATCHED'}
        </span>
      </div>
      <div className="text-gray-400 text-xs space-y-0.5">
        <div>Lat: {coach.lat.toFixed(5)} · Lng: {coach.long.toFixed(5)}</div>
        {coach.calculated_speed != null && (
          <div>Speed: <span className="text-white font-mono">{coach.calculated_speed.toFixed(1)} km/h</span></div>
        )}
        {coach.route_segment_id && (
          <div>Segment: <span className="text-blue-400 font-mono">{coach.route_segment_id}</span></div>
        )}
        {coach.match_distance_meters != null && (
          <div>Match dist: <span className="font-mono">{coach.match_distance_meters.toFixed(1)} m</span></div>
        )}
      </div>
    </div>
  );
}

function RiskBadge({ segmentId, risk }: { segmentId: string; risk: RiskScore }) {
  const colorClass = RISK_COLOR[risk.risk_level] ?? RISK_COLOR.none;
  return (
    <div className={`rounded border px-3 py-2 text-xs ${colorClass}`}>
      <div className="flex justify-between items-center">
        <span className="font-mono text-gray-400">{segmentId}</span>
        <span className="font-black text-sm">{RISK_LABEL[risk.risk_level] ?? risk.risk_level.toUpperCase()}</span>
      </div>
      <div className="text-gray-500 mt-0.5">Source: {risk.source}</div>
    </div>
  );
}

const RiskPanel = ({ state }: Props) => {
  const hasCoaches = state.coach_positions.length > 0;
  const riskEntries = Object.entries(state.risk_scores).filter(
    ([, r]) => r.risk_level !== 'none'
  );
  const allRiskEntries = Object.entries(state.risk_scores);

  if (!hasCoaches && allRiskEntries.length === 0) return null;

  return (
    <div className="mt-6 bg-railPanel p-4 rounded-lg border border-gray-700">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-bold text-gray-300">Live Coach GPS &amp; Risk Layer</h3>
        <span className="text-xs font-mono text-emerald-400 bg-emerald-900/30 px-2 py-1 rounded border border-emerald-800">
          PERSON2 LIVE
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Coach positions */}
        <div>
          <h4 className="text-sm font-bold text-gray-400 mb-3">COACH POSITIONS</h4>
          {hasCoaches ? (
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {state.coach_positions.map(c => (
                <CoachCard key={c.coach_id} coach={c} />
              ))}
            </div>
          ) : (
            <p className="text-gray-500 italic text-sm">
              No coach GPS data yet. Open{' '}
              <a href="http://localhost:8001/gps-client/" target="_blank" rel="noreferrer"
                 className="text-blue-400 underline">GPS Client</a>{' '}
              on a phone to start sending.
            </p>
          )}
        </div>

        {/* Risk scores */}
        <div>
          <h4 className="text-sm font-bold text-gray-400 mb-3">
            SEGMENT RISK SCORES
            {riskEntries.length > 0 && (
              <span className="ml-2 text-red-400">({riskEntries.length} active)</span>
            )}
          </h4>
          {riskEntries.length > 0 ? (
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {riskEntries.map(([seg, risk]) => (
                <RiskBadge key={seg} segmentId={seg} risk={risk} />
              ))}
            </div>
          ) : allRiskEntries.length > 0 ? (
            <div className="text-green-400 text-sm font-bold flex items-center gap-2">
              <span className="text-xl">✓</span>
              All {allRiskEntries.length} segments clear — no flood or weather risk detected.
            </div>
          ) : (
            <p className="text-gray-500 italic text-sm">Loading risk data…</p>
          )}
        </div>
      </div>
    </div>
  );
};

export default RiskPanel;
