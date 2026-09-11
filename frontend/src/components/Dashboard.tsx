import { useState, useEffect } from 'react';
import type { AppState } from '../hooks/useWebSockets';
import TrackMap from './TrackMap';
import AlertBanner from './AlertBanner';
import TrackSchematic from './TrackSchematic';
import AlertLog from './AlertLog';
import ETAPanel from './ETAPanel';
import RiskPanel from './RiskPanel';

interface Props {
  state: AppState;
}

interface EscalationConfig {
  timeout_seconds: number;
  phone_number: string;
}

const Dashboard = ({ state }: Props) => {
  // removed loading state
  const [escalationConfig, setEscalationConfig] = useState<EscalationConfig>({
    timeout_seconds: 15,
    phone_number: '',
  });
  const [configSaved, setConfigSaved] = useState(false);

  useEffect(() => {
    // Fetch current escalation config on mount
    fetch('http://localhost:8000/api/escalation_config')
      .then(res => res.json())
      .then(data => {
        if (data.timeout_seconds != null) {
          setEscalationConfig({
            timeout_seconds: data.timeout_seconds,
            phone_number: data.phone_number || '',
          });
        }
      })
      .catch(() => {});
  }, []);

  const injectFault = async (endpoint: string) => {
    try {
      await fetch(`http://localhost:8000/api/${endpoint}`, { method: 'POST' });
    } catch (e) {
      console.error(e);
    }
  };

  const saveEscalationConfig = async () => {
    try {
      await fetch('http://localhost:8000/api/escalation_config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(escalationConfig),
      });
      setConfigSaved(true);
      setTimeout(() => setConfigSaved(false), 2000);
    } catch (e) {
      console.error('Failed to save escalation config', e);
    }
  };

  const resolveAll = async () => {
    try {
      await fetch('http://localhost:8000/api/resolve_signal_mismatch', { method: 'POST' });
      await fetch('http://localhost:8000/api/resolve_converging_trains', { method: 'POST' });
    } catch (e) {
      console.error(e);
    }
  };

  const escalatedAlerts = state.alerts.filter(a => a.status === 'Escalated' || a.escalated_at);

  const [train1, setTrain1] = useState('12952');
  const [train2, setTrain2] = useState('12841');

  const updateTrains = async () => {
    try {
      await fetch(`http://localhost:8000/api/set_trains`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ trains: [train1, train2] })
      });
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-black text-white tracking-widest">MAIN CONTROL ROOM</h1>
          <p className="text-gray-400">Independent Signal &amp; Position Integrity Verification</p>
        </div>
        <div className="flex flex-col gap-2">
          <div className="flex gap-2 items-center bg-[#0f172a] p-2 rounded border border-gray-700">
            <input value={train1} onChange={e => setTrain1(e.target.value)} placeholder="Train 1 No." className="bg-[#1e293b] text-white p-1 rounded w-24 text-sm" />
            <input value={train2} onChange={e => setTrain2(e.target.value)} placeholder="Train 2 No." className="bg-[#1e293b] text-white p-1 rounded w-24 text-sm" />
            <button onClick={updateTrains} className="bg-blue-600 hover:bg-blue-500 text-white px-3 py-1 rounded text-sm font-bold">Track</button>
          </div>
          <div className="flex gap-2">
            <button 
              onClick={() => injectFault('inject_signal_mismatch')}
              className="px-4 py-2 bg-red-900/50 text-red-100 border border-red-800 rounded font-bold hover:bg-red-800 transition-colors"
            >
              Signal Mismatch
            </button>
            <button 
              onClick={() => injectFault('inject_converging_trains')}
              className="px-4 py-2 bg-orange-900/50 text-orange-100 border border-orange-800 rounded font-bold hover:bg-orange-800 transition-colors"
            >
              Simulate Collision
            </button>
            <button 
              onClick={resolveAll}
              className="px-4 py-2 bg-green-900/50 text-green-100 border border-green-800 rounded font-bold hover:bg-green-800 transition-colors"
            >
              Resolve
            </button>
          </div>
        </div>
      </div>

      <AlertBanner alerts={state.alerts} />
      <TrackMap state={state} />
      <div className="mt-8">
        <TrackSchematic state={state} />
      </div>
      <ETAPanel state={state} />
      <RiskPanel state={state} />
      <AlertLog alerts={state.alerts} />

      {/* Escalation Status Panel */}
      <div className="mt-6 bg-railPanel p-4 rounded-lg border border-gray-700">
        <h3 className="text-lg font-bold mb-4 text-gray-300">Escalation Status</h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Config Form */}
          <div className="bg-gray-800 p-4 rounded-lg border border-gray-700">
            <h4 className="text-sm font-bold text-gray-400 mb-3">ESCALATION SETTINGS</h4>
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Timeout (seconds)</label>
                <input
                  type="number"
                  value={escalationConfig.timeout_seconds}
                  onChange={e => setEscalationConfig(prev => ({ ...prev, timeout_seconds: parseInt(e.target.value) || 15 }))}
                  className="w-full bg-gray-900 text-white px-3 py-2 rounded border border-gray-600 focus:border-blue-500 focus:outline-none text-sm"
                  min={5}
                  max={300}
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Phone Number</label>
                <input
                  type="text"
                  value={escalationConfig.phone_number}
                  onChange={e => setEscalationConfig(prev => ({ ...prev, phone_number: e.target.value }))}
                  placeholder="+91XXXXXXXXXX"
                  className="w-full bg-gray-900 text-white px-3 py-2 rounded border border-gray-600 focus:border-blue-500 focus:outline-none text-sm"
                />
              </div>
              <button
                onClick={saveEscalationConfig}
                className="w-full bg-blue-700 hover:bg-blue-600 text-white py-2 rounded font-bold text-sm transition"
              >
                {configSaved ? '✓ Saved!' : 'Save Config'}
              </button>
            </div>
          </div>

          {/* Escalated Alerts List */}
          <div className="bg-gray-800 p-4 rounded-lg border border-gray-700">
            <h4 className="text-sm font-bold text-gray-400 mb-3">ESCALATED ALERTS</h4>
            {escalatedAlerts.length === 0 ? (
              <p className="text-gray-500 italic text-sm">No escalated alerts.</p>
            ) : (
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {escalatedAlerts.map(alert => (
                  <div key={alert.id} className="bg-purple-900/30 border border-purple-700 rounded p-3 text-sm">
                    <div className="flex justify-between items-start">
                      <div>
                        <span className="font-mono text-xs text-purple-300">{alert.id}</span>
                        <p className="text-gray-300 mt-1">{alert.description}</p>
                        {alert.escalated_to && (
                          <p className="text-purple-400 text-xs mt-1">Escalated to: {alert.escalated_to}</p>
                        )}
                      </div>
                      <div className="text-right text-xs text-gray-500">
                        {alert.escalated_at
                          ? new Date(alert.escalated_at * 1000).toLocaleTimeString()
                          : '—'}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
