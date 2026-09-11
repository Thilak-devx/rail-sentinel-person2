import { useEffect, useRef } from 'react';
import type { Alert } from '../hooks/useWebSockets';

interface Props {
  alerts: Alert[];
}

const AlertBanner = ({ alerts }: Props) => {
  const activeAlerts = alerts.filter(a => a.status === 'Detected' || a.status === 'Displayed');
  const prevAlertCount = useRef(0);

  useEffect(() => {
    if (activeAlerts.length > prevAlertCount.current) {
      // Play beep using Web Audio API
      try {
        const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
        const osc = ctx.createOscillator();
        osc.type = 'square';
        osc.frequency.setValueAtTime(880, ctx.currentTime); // A5
        osc.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 0.2); // 200ms beep
        
        setTimeout(() => {
          const osc2 = ctx.createOscillator();
          osc2.type = 'square';
          osc2.frequency.setValueAtTime(880, ctx.currentTime);
          osc2.connect(ctx.destination);
          osc2.start();
          osc2.stop(ctx.currentTime + 0.2);
        }, 300);
      } catch (e) {
        console.error("Audio playback failed", e);
      }
    }
    prevAlertCount.current = activeAlerts.length;
  }, [activeAlerts.length]);

  if (activeAlerts.length === 0) return null;

  return (
    <div className="mb-6 space-y-2">
      {activeAlerts.map(alert => (
        <div key={alert.id} className="bg-red-900 border-2 border-red-500 text-white p-4 rounded-lg flex justify-between items-center animate-pulse">
          <div>
            <h3 className="font-bold text-lg">CRITICAL ALERT: {alert.layer}</h3>
            <p className="text-red-200">{alert.description}</p>
          </div>
          <div className="text-right">
            <span className="bg-red-600 px-3 py-1 rounded text-sm font-mono">ID: {alert.id}</span>
          </div>
        </div>
      ))}
    </div>
  );
};

export default AlertBanner;
