import React from 'react';
import type { AppState } from '../hooks/useWebSockets';

interface Props {
  state: AppState;
}

const TrackSchematic: React.FC<Props> = ({ state }) => {
  if (!state.scada || !state.trains) {
    return <div className="text-gray-400 p-4 border border-gray-700 rounded">Waiting for track data...</div>;
  }

  const { tracks, points, signals } = state.scada;
  const { trains } = state.trains as any;

  const getSignalColor = (aspect: string) => {
    switch (aspect) {
      case 'red': return '#ff4444';
      case 'yellow': return '#ffbb33';
      case 'green': return '#00C851';
      default: return '#555';
    }
  };

  const getTrackColor = (isOccupied: boolean) => isOccupied ? '#ff4444' : '#4b5563';

  return (
    <div className="bg-[#0f172a] p-6 rounded-lg border border-gray-700 mb-6 shadow-inner">
      <h2 className="text-xl font-bold mb-2 text-gray-200 flex justify-between items-center">
        <span>Live Track Telemetry</span>
        <span className="text-xs font-normal text-green-400 flex items-center gap-1">
          <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></span>
          RailRadar LIVE
        </span>
      </h2>
      
      <div className="relative w-full overflow-hidden bg-[#1e293b] rounded-xl border border-gray-800 flex justify-center py-6">
        <svg viewBox="0 0 900 340" className="w-full h-auto max-w-5xl">
          <defs>
            <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
            <filter id="trainGlow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          </defs>

          {/* Grid */}
          <g stroke="#334155" strokeWidth="0.5" strokeDasharray="10 10" opacity="0.2">
            {[...Array(10)].map((_, i) => <line key={`v${i}`} x1={i * 100} y1="0" x2={i * 100} y2="340" />)}
            {[...Array(4)].map((_, i) => <line key={`h${i}`} x1="0" y1={i * 100} x2="900" y2={i * 100} />)}
          </g>

          {/* ── INTERLOCKING TRACKS ── */}
          <g strokeWidth="8" strokeLinecap="round">
            <line x1="20" y1="120" x2="220" y2="120" stroke={getTrackColor(tracks['T1'])} />
            <text x="120" y="105" fill="#64748b" fontSize="13" textAnchor="middle" fontWeight="bold">T1</text>

            {points['P1'] === 'normal' && <line x1="220" y1="120" x2="270" y2="120" stroke={getTrackColor(tracks['T2'])} />}
            <line x1="270" y1="120" x2="680" y2="120" stroke={getTrackColor(tracks['T2'])} />
            {points['P2'] === 'normal' && <line x1="680" y1="120" x2="730" y2="120" stroke={getTrackColor(tracks['T2'])} />}
            <text x="475" y="105" fill="#64748b" fontSize="13" textAnchor="middle" fontWeight="bold">T2 (MAIN LINE)</text>

            {points['P1'] === 'reverse' && <line x1="220" y1="120" x2="320" y2="220" stroke={getTrackColor(tracks['T3'])} strokeDasharray="12 6" />}
            <line x1="320" y1="220" x2="630" y2="220" stroke={getTrackColor(tracks['T3'])} />
            {points['P2'] === 'reverse' && <line x1="630" y1="220" x2="730" y2="120" stroke={getTrackColor(tracks['T3'])} strokeDasharray="12 6" />}
            <text x="475" y="250" fill="#64748b" fontSize="13" textAnchor="middle" fontWeight="bold">T3 (LOOP LINE)</text>

            <line x1="730" y1="120" x2="880" y2="120" stroke={getTrackColor(tracks['T4'])} />
            <text x="805" y="105" fill="#64748b" fontSize="13" textAnchor="middle" fontWeight="bold">T4</text>
          </g>

          {/* ── POINTS ── */}
          <g>
            <circle cx="220" cy="120" r="7" fill={points['P1'] === 'reverse' ? '#ef4444' : '#fbbf24'} filter="url(#glow)" />
            <text x="205" y="155" fill="#fbbf24" fontSize="11" fontWeight="bold">P1: {points['P1'].toUpperCase()}</text>

            <circle cx="730" cy="120" r="7" fill={points['P2'] === 'reverse' ? '#ef4444' : '#fbbf24'} filter="url(#glow)" />
            <text x="710" y="155" fill="#fbbf24" fontSize="11" fontWeight="bold">P2: {points['P2'].toUpperCase()}</text>
          </g>

          {/* ── SIGNALS ── */}
          {[{ id: 'S1', x: 175, aspect: signals['S1'] }, { id: 'S2', x: 650, aspect: signals['S2'] }].map(sig => (
            <g key={sig.id} transform={`translate(${sig.x}, 50)`}>
              <rect x="0" y="0" width="18" height="44" rx="5" fill="#111827" stroke="#374151" strokeWidth="2" />
              <rect x="7" y="44" width="4" height="22" fill="#475569" />
              <circle cx="9" cy="11" r="5" fill={sig.aspect === 'red' ? getSignalColor('red') : '#333'} filter={sig.aspect === 'red' ? 'url(#glow)' : undefined} />
              <circle cx="9" cy="22" r="5" fill={sig.aspect === 'yellow' ? getSignalColor('yellow') : '#333'} filter={sig.aspect === 'yellow' ? 'url(#glow)' : undefined} />
              <circle cx="9" cy="33" r="5" fill={sig.aspect === 'green' ? getSignalColor('green') : '#333'} filter={sig.aspect === 'green' ? 'url(#glow)' : undefined} />
              <text x="25" y="28" fill="#e2e8f0" fontSize="14" fontWeight="bold">{sig.id}</text>
            </g>
          ))}

          {/* ── TRAINS (from RailRadar) ── */}
          {Object.entries(trains).map(([id, t]: [string, any]) => {
            const tx = (t.x / 120) * 860 + 20;
            const ty = t.y === 10 ? 120 : 220;
            const isGhost = id.startsWith('GHOST');
            const fillColor = isGhost ? '#ef4444' : '#3b82f6';
            const strokeColor = isGhost ? '#dc2626' : '#2563eb';
            
            return (
              <g key={id} className="transition-all duration-1000 ease-linear">
                {/* Train body */}
                <rect x={tx - 45} y={ty - 14} width="90" height="28" rx="5" fill={fillColor} stroke={strokeColor} strokeWidth="2" filter="url(#trainGlow)" />
                
                {/* Train windows */}
                <rect x={tx - 35} y={ty - 8} width="12" height="16" rx="2" fill={isGhost ? '#fca5a5' : '#93c5fd'} />
                <rect x={tx - 18} y={ty - 8} width="12" height="16" rx="2" fill={isGhost ? '#fca5a5' : '#93c5fd'} />
                <rect x={tx - 1} y={ty - 8} width="12" height="16" rx="2" fill={isGhost ? '#fca5a5' : '#93c5fd'} />
                <rect x={tx + 16} y={ty - 8} width="12" height="16" rx="2" fill={isGhost ? '#fca5a5' : '#93c5fd'} />
                
                {/* Direction arrow */}
                {t.direction === 1 ? (
                  <polygon points={`${tx+50},-4 ${tx+58},0 ${tx+50},4`} fill={fillColor} transform={`translate(0, ${ty})`} />
                ) : (
                  <polygon points={`${tx-50},-4 ${tx-58},0 ${tx-50},4`} fill={fillColor} transform={`translate(0, ${ty})`} />
                )}

                {/* Train info card */}
                <g transform={`translate(${tx}, ${ty - 55})`}>
                  <rect x="-80" y="-15" width="160" height="38" rx="6" fill="#0f172a" stroke="#334155" strokeWidth="1" opacity="0.95" />
                  <text x="0" y="-1" fill="#e2e8f0" fontSize="10" textAnchor="middle" fontWeight="bold">
                    {t.trainName ? (t.trainName.length > 28 ? t.trainName.substring(0, 28) + '...' : t.trainName) : id}
                  </text>
                  <text x="0" y="14" fill={t.delayMinutes > 0 ? '#fbbf24' : '#4ade80'} fontSize="9" textAnchor="middle">
                    {t.currentStation || 'En Route'} {t.delayMinutes > 0 ? `(+${t.delayMinutes} min late)` : '(On Time)'}
                  </text>
                </g>
              </g>
            );
          })}

          {/* ── STATION LABEL ── */}
          <text x="450" y="300" fill="#475569" fontSize="16" textAnchor="middle" fontFamily="monospace" fontWeight="bold">
            SIMULATED INTERLOCKING ZONE — BALASORE MODEL
          </text>
        </svg>
      </div>
    </div>
  );
};

export default TrackSchematic;
