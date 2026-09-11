import { useState, useEffect } from 'react';
import type { AppState } from '../hooks/useWebSockets';

interface Props {
  state: AppState;
}

const ESCALATION_TIMEOUT_SECONDS = 15;

const StationMasterVDU = ({ state }: Props) => {
  const activeAlerts = state.alerts.filter(a => a.status === 'Detected' || a.status === 'Displayed');
  const [now, setNow] = useState(() => Date.now() / 1000);

  // Tick the countdown every second
  useEffect(() => {
    const interval = setInterval(() => {
      setNow(Date.now() / 1000);
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  const acknowledgeAlert = async (id: string) => {
    try {
      await fetch(`http://localhost:8000/api/acknowledge_alert/${id}`, { method: 'POST' });
    } catch (e) {
      console.error(e);
    }
  };

  const getCountdown = (detectedAt: number): number => {
    const elapsed = now - detectedAt;
    const remaining = ESCALATION_TIMEOUT_SECONDS - elapsed;
    return Math.max(0, Math.ceil(remaining));
  };

  const [routineCheck, setRoutineCheck] = useState<string | null>(null);

  useEffect(() => {
    // Continously ask for information every 20 seconds
    const questions = [
      "Confirm signals S1 and S2 are operating normally?",
      "Verify Route Relay Interlocking block logic is secure.",
      "Acknowledge Point P1 physical padlocks are secured.",
      "Check platform 2 tracks are clear of obstructions."
    ];
    let i = 0;
    const interval = setInterval(() => {
      if (!routineCheck) {
        setRoutineCheck(questions[i % questions.length]);
        i++;
      }
    }, 20000);
    return () => clearInterval(interval);
  }, [routineCheck]);

  return (
    <div className="p-8 max-w-4xl mx-auto min-h-screen bg-black">
      <div className="border-b-4 border-gray-700 pb-4 mb-8">
        <h1 className="text-4xl font-mono font-bold text-gray-300">STATION MASTER VDU</h1>
        <div className="text-gray-500 font-mono mt-2">USER: SM_01 | STATUS: ONLINE</div>
      </div>

      {routineCheck && (
        <div className="mb-8 border-2 border-blue-600 bg-blue-900/30 p-6 rounded shadow-[0_0_15px_rgba(37,99,235,0.3)]">
          <h2 className="text-xl font-bold text-blue-400 mb-2">ROUTINE CHECK REQUIRED</h2>
          <p className="text-gray-200 mb-4">{routineCheck}</p>
          <div className="flex gap-4">
            <button 
              onClick={() => setRoutineCheck(null)}
              className="bg-blue-600 hover:bg-blue-500 text-white font-bold py-2 px-6 rounded"
            >
              CONFIRM ALL CLEAR
            </button>
            <button 
              onClick={() => setRoutineCheck(null)}
              className="bg-gray-700 hover:bg-gray-600 text-gray-300 font-bold py-2 px-6 rounded"
            >
              REPORT ISSUE
            </button>
          </div>
        </div>
      )}

      <div className="space-y-6">
        {activeAlerts.length === 0 ? (
          <div className="text-green-500 font-mono text-xl border border-green-900 p-8 text-center bg-green-900/20">
            ALL SYSTEMS NORMAL
          </div>
        ) : (
          activeAlerts.map(alert => {
            const countdown = getCountdown(alert.detected_at);
            const isUrgent = countdown <= 5 && countdown > 0;
            const isExpired = countdown === 0;

            return (
              <div key={alert.id} className="border-2 border-red-600 bg-red-950 p-6 shadow-[0_0_15px_rgba(220,38,38,0.5)]">
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <h2 className="text-2xl font-bold text-red-500 mb-2">⚠ {alert.layer} ALERT</h2>
                    <p className="text-gray-300 text-lg">{alert.description}</p>
                  </div>
                  <div className="text-right">
                    <div className="text-red-400 font-mono text-xl mb-1">{alert.id}</div>
                    <div className="text-gray-400 font-mono text-sm">{new Date(alert.detected_at * 1000).toLocaleTimeString()}</div>
                  </div>
                </div>

                {/* Escalation Countdown */}
                <div className={`mb-4 p-3 rounded-lg border ${
                  isExpired
                    ? 'bg-purple-900/40 border-purple-600'
                    : isUrgent
                      ? 'bg-yellow-900/40 border-yellow-600 animate-pulse'
                      : 'bg-gray-800 border-gray-700'
                }`}>
                  <div className="flex justify-between items-center">
                    <span className="text-sm font-mono text-gray-400">ESCALATION TIMER</span>
                    {isExpired ? (
                      <span className="text-purple-400 font-mono font-bold text-lg">ESCALATED</span>
                    ) : (
                      <span className={`font-mono font-bold text-lg ${isUrgent ? 'text-yellow-400' : 'text-white'}`}>
                        Escalation in: {countdown}s
                      </span>
                    )}
                  </div>
                  {/* Progress bar */}
                  {!isExpired && (
                    <div className="mt-2 w-full bg-gray-700 rounded-full h-2">
                      <div
                        className={`h-2 rounded-full transition-all duration-1000 ${
                          isUrgent ? 'bg-yellow-500' : 'bg-blue-500'
                        }`}
                        style={{ width: `${(countdown / ESCALATION_TIMEOUT_SECONDS) * 100}%` }}
                      ></div>
                    </div>
                  )}
                </div>
                
                <div className="flex space-x-4">
                  <button 
                    onClick={() => acknowledgeAlert(alert.id)}
                    className="flex-1 bg-blue-700 hover:bg-blue-600 text-white py-4 text-xl font-bold rounded shadow-lg transition"
                  >
                    ACKNOWLEDGE
                  </button>
                  <button 
                    onClick={() => acknowledgeAlert(alert.id)}
                    className="flex-1 bg-gray-700 hover:bg-gray-600 text-gray-300 py-4 text-xl font-bold rounded shadow-lg transition"
                  >
                    DISMISS (FALSE POSITIVE)
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>

      <div className="mt-12">
        <h3 className="text-gray-500 font-mono mb-4">RECENT ACTIVITY</h3>
        <div className="bg-gray-900 p-4 font-mono text-sm text-gray-400 space-y-2 max-h-64 overflow-y-auto">
          {[...state.alerts].reverse().slice(0, 10).map(alert => (
            <div key={alert.id} className="border-b border-gray-800 pb-2">
              <span className="text-gray-500">[{new Date(alert.detected_at * 1000).toLocaleTimeString()}]</span>{' '}
              <span className="text-gray-300">{alert.id}</span>{' '}
              <span>- Status: <span className="text-white">{alert.status}</span></span>
              {alert.acknowledged_by && <span className="text-blue-400"> (by {alert.acknowledged_by})</span>}
              {alert.escalated_to && <span className="text-purple-400"> (escalated to {alert.escalated_to})</span>}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default StationMasterVDU;
