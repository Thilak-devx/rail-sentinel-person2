import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, GeoJSON, CircleMarker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import type { AppState } from '../hooks/useWebSockets';

interface Props {
  state: AppState;
}

const TrackMap: React.FC<Props> = ({ state }) => {
  const [routes, setRoutes] = useState<Record<string, any>>({});
  
  const fetchRoute = async (trainNumber: string) => {
    try {
      const res = await fetch(`http://localhost:8000/api/route/${trainNumber}`);
      if (res.ok) {
        const geojson = await res.json();
        setRoutes(prev => ({ ...prev, [trainNumber]: geojson }));
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    if (!state.trains?.trains) return;
    Object.keys(state.trains.trains).forEach(trainNum => {
      if (!routes[trainNum] && !trainNum.startsWith('GHOST')) {
        fetchRoute(trainNum);
      }
    });
  }, [state.trains]);

  if (!state.trains) return <div>Loading Map...</div>;
  const { trains } = state.trains as any;

  return (
    <div className="bg-[#0f172a] p-6 rounded-lg border border-gray-700 mb-6 shadow-inner h-[500px] flex flex-col">
      <h2 className="text-xl font-bold mb-2 text-gray-200 flex justify-between items-center">
        <span>Live GIS Map Tracking</span>
        <span className="text-xs font-normal text-green-400 flex items-center gap-1">
          <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></span>
          RailRadar LIVE
        </span>
      </h2>
      <div className="flex-1 rounded-xl overflow-hidden border border-gray-800">
        <MapContainer center={[22, 78]} zoom={5} style={{ height: '100%', width: '100%' }}>
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='&copy; OpenStreetMap'
            className="dark-map-tiles"
          />
          <style>
            {`.dark-map-tiles { filter: invert(100%) hue-rotate(180deg) brightness(95%) contrast(90%); }`}
          </style>
          
          {Object.entries(routes).map(([tid, geojson]) => (
            geojson && geojson.type ? (
               <GeoJSON 
                 key={`route-${tid}`} 
                 data={geojson} 
                 style={{ color: '#3b82f6', weight: 3, opacity: 0.5 }} 
               />
            ) : null
          ))}

          {Object.entries(trains).map(([id, t]: [string, any]) => {
            const isGhost = id.startsWith('GHOST');
            const color = isGhost ? '#ef4444' : '#3b82f6';
            if (!t.lat || !t.lng) return null;
            return (
              <CircleMarker 
                key={id} 
                center={[t.lat, t.lng]} 
                radius={8} 
                color={color} 
                fillColor={color} 
                fillOpacity={0.8}
              >
                <Popup>
                  <strong>{t.trainName || id}</strong><br/>
                  Station: {t.currentStation}<br/>
                  Delay: {t.delayMinutes} mins
                </Popup>
              </CircleMarker>
            );
          })}
        </MapContainer>
      </div>
    </div>
  );
};

export default TrackMap;
