import { useState, useEffect } from 'react';

export interface Alert {
  id: string;
  condition_id: string;
  layer: string;
  description: string;
  status: string;
  detected_at: number;
  acknowledged_by?: string;
  acknowledged_at?: number;
  escalated_at?: number;
  escalated_to?: string;
}

export interface TrainData {
  trainNumber: string;
  trainName: string;
  status: string;
  isLive: boolean;
  delayMinutes: number;
  currentStation: string;
  avgSpeed: number;
  source: string;
  destination: string;
  distanceFromOriginKm: number;
  totalDistanceKm: number;
  previousHalt: string;
  nextHalt: string;
  lat?: number;
  lng?: number;
}

export interface ETAPrediction {
  predicted_delay_min: number;
  confidence_low_min: number;
  confidence_high_min: number;
  confidence_pct: number;
}

export interface CoachPosition {
  coach_id: string;
  lat: number;
  long: number;
  speed: number | null;
  calculated_speed: number | null;
  timestamp: string;
  matched_lat: number | null;
  matched_long: number | null;
  match_distance_meters: number | null;
  route_segment_id: string | null;
  matched: boolean | null;
}

export interface RiskScore {
  risk_level: 'none' | 'low' | 'moderate' | 'severe';
  source: string;
  last_updated: string;
}

export interface AppState {
  scada: {
    tracks: Record<string, boolean>;
    points: Record<string, string>;
    signals: Record<string, string>;
    fault_active: boolean;
  } | null;
  trains: {
    trains: Record<string, TrainData>;
    ghost_trains?: Record<string, TrainData>;
    railradar_active: boolean;
  } | null;
  alerts: Alert[];
  eta: Record<string, ETAPrediction>;
  coach_positions: CoachPosition[];
  risk_scores: Record<string, RiskScore>;
}

export function useWebSockets() {
  const [state, setState] = useState<AppState>({
    scada: null,
    trains: null,
    alerts: [],
    eta: {},
    coach_positions: [],
    risk_scores: {},
  });
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8000/ws');

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setState((prevState) => ({
          ...prevState,
          scada: data.scada || prevState.scada,
          trains: data.trains || prevState.trains,
          alerts: data.alerts || prevState.alerts,
          eta: data.eta || prevState.eta,
          coach_positions: data.coach_positions ?? prevState.coach_positions,
          risk_scores: data.risk_scores ?? prevState.risk_scores,
        }));
      } catch (err) {
        console.error('Error parsing WS message', err);
      }
    };

    return () => {
      ws.close();
    };
  }, []);

  return { state, connected };
}
