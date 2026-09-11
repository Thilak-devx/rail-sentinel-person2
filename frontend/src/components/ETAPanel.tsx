import type { AppState, ETAPrediction } from '../hooks/useWebSockets';

interface Props {
  state: AppState;
}

function delayColor(min: number): string {
  if (min > 30) return 'text-red-400';
  if (min > 10) return 'text-yellow-400';
  return 'text-green-400';
}

function ConfidenceBar({ low, high }: { low: number; high: number }) {
  const max = Math.max(high, 1);
  const leftPct = (low / max) * 100;
  const widthPct = ((high - low) / max) * 100;
  return (
    <div className="mt-2 w-full bg-gray-700 rounded-full h-1.5 relative overflow-hidden">
      <div
        className="absolute h-1.5 rounded-full bg-blue-500/50"
        style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
      />
    </div>
  );
}

function TrainETACard({
  trainId,
  pred,
  trainName,
  currentStation,
}: {
  trainId: string;
  pred: ETAPrediction;
  trainName?: string;
  currentStation?: string;
}) {
  const color = delayColor(pred.predicted_delay_min);
  const sign = pred.predicted_delay_min >= 0 ? '+' : '';
  return (
    <div className="bg-gray-800 p-4 rounded-lg border border-gray-700">
      <div className="flex justify-between items-start mb-3">
        <div>
          <span className="font-mono text-xs text-gray-500">#{trainId}</span>
          <p className="font-bold text-white text-sm leading-tight">
            {trainName || trainId}
          </p>
          {currentStation && (
            <p className="text-xs text-gray-500 mt-0.5">{currentStation}</p>
          )}
        </div>
        <div className="text-right">
          <span className={`text-3xl font-black leading-none ${color}`}>
            {sign}{pred.predicted_delay_min}
          </span>
          <span className="text-xs text-gray-400 ml-0.5">min</span>
          <p className="text-xs text-gray-500 mt-0.5">predicted delay</p>
        </div>
      </div>

      {/* Quantile labels */}
      <div className="bg-gray-900 rounded p-2 text-xs font-mono">
        <div className="flex justify-between text-gray-500 mb-1">
          <span>P10 (optimistic)</span>
          <span>P50 (median)</span>
          <span>P90 (pessimistic)</span>
        </div>
        <div className="flex justify-between font-bold">
          <span className="text-green-400">+{pred.confidence_low_min}m</span>
          <span className={color}>+{pred.predicted_delay_min}m</span>
          <span className="text-red-400">+{pred.confidence_high_min}m</span>
        </div>
        <ConfidenceBar low={pred.confidence_low_min} high={pred.confidence_high_min} />
        <p className="text-gray-600 mt-1.5">
          {pred.confidence_pct}% confidence interval · LightGBM quantile regression
        </p>
      </div>
    </div>
  );
}

const ETAPanel = ({ state }: Props) => {
  const eta = state.eta;
  const trains = state.trains?.trains;

  const etaEntries = Object.entries(eta);
  if (etaEntries.length === 0) return null;

  return (
    <div className="mt-6 bg-railPanel p-4 rounded-lg border border-gray-700">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-bold text-gray-300">ETA Delay Predictions</h3>
        <span className="text-xs font-mono text-blue-400 bg-blue-900/30 px-2 py-1 rounded border border-blue-800">
          ML MODEL LIVE
        </span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {etaEntries.map(([trainId, pred]) => (
          <TrainETACard
            key={trainId}
            trainId={trainId}
            pred={pred}
            trainName={trains?.[trainId]?.trainName}
            currentStation={trains?.[trainId]?.currentStation}
          />
        ))}
      </div>
    </div>
  );
};

export default ETAPanel;
