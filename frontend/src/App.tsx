import { useState } from 'react';
import { useWebSockets } from './hooks/useWebSockets';
import Dashboard from './components/Dashboard';
import StationMasterVDU from './components/StationMasterVDU';

function App() {
  const { state, connected } = useWebSockets();
  const [view, setView] = useState<'dashboard' | 'vdu'>('dashboard');

  return (
    <div className="min-h-screen bg-railDark text-white">
      {/* Navigation Header */}
      <nav className="bg-gray-900 border-b border-gray-800 p-4 flex justify-between items-center">
        <div className="flex items-center space-x-4">
          <div className={`w-3 h-3 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`}></div>
          <span className="font-mono text-sm text-gray-400">
            {connected ? 'WS CONNECTED' : 'WS DISCONNECTED'}
          </span>
        </div>
        <div className="space-x-4">
          <button 
            onClick={() => setView('dashboard')}
            className={`px-4 py-2 rounded font-bold ${view === 'dashboard' ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400'}`}
          >
            Main Dashboard
          </button>
          <button 
            onClick={() => setView('vdu')}
            className={`px-4 py-2 rounded font-bold ${view === 'vdu' ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400'}`}
          >
            Station Master VDU
          </button>
        </div>
      </nav>

      {/* Main Content */}
      {view === 'dashboard' ? (
        <Dashboard state={state} />
      ) : (
        <StationMasterVDU state={state} />
      )}
    </div>
  );
}

export default App;
