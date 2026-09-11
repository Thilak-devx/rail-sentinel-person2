import type { Alert } from '../hooks/useWebSockets';

interface Props {
  alerts: Alert[];
}

const AlertLog = ({ alerts }: Props) => {
  return (
    <div className="bg-railPanel p-4 rounded-lg border border-gray-700 h-64 overflow-y-auto">
      <h3 className="text-lg font-bold mb-4 text-gray-300 sticky top-0 bg-railPanel pb-2">Alert History</h3>
      {alerts.length === 0 ? (
        <p className="text-gray-500 italic">No alerts recorded.</p>
      ) : (
        <table className="w-full text-sm text-left">
          <thead className="text-gray-400 bg-gray-800 rounded">
            <tr>
              <th className="px-2 py-1">ID</th>
              <th className="px-2 py-1">Layer</th>
              <th className="px-2 py-1">Status</th>
              <th className="px-2 py-1">Description</th>
              <th className="px-2 py-1">Escalated To</th>
              <th className="px-2 py-1">Time</th>
            </tr>
          </thead>
          <tbody>
            {[...alerts].reverse().map(alert => (
              <tr key={alert.id} className="border-b border-gray-800 hover:bg-gray-800">
                <td className="px-2 py-2 font-mono text-xs">{alert.id}</td>
                <td className="px-2 py-2">{alert.layer}</td>
                <td className="px-2 py-2">
                  <span className={`px-2 py-1 rounded text-xs ${
                    alert.status === 'Resolved' ? 'bg-green-900 text-green-300' :
                    alert.status === 'Acknowledged' ? 'bg-blue-900 text-blue-300' :
                    alert.status === 'Escalated' ? 'bg-purple-900 text-purple-300' :
                    'bg-red-900 text-red-300'
                  }`}>
                    {alert.status}
                  </span>
                </td>
                <td className="px-2 py-2 text-gray-300 truncate max-w-xs" title={alert.description}>{alert.description}</td>
                <td className="px-2 py-2 text-purple-300 font-mono text-xs">
                  {alert.escalated_to || '—'}
                </td>
                <td className="px-2 py-2 text-gray-500">{new Date(alert.detected_at * 1000).toLocaleTimeString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};

export default AlertLog;
