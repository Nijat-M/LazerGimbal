import React, { useState } from 'react';
import { Terminal, ChevronDown, ChevronUp } from 'lucide-react';


interface TacticalLogProps {
  logs: string[];
}

export const TacticalLog: React.FC<TacticalLogProps> = ({ logs }) => {
  const [isExpanded, setIsExpanded] = useState<boolean>(true);

  return (
    <div className="hud-panel rounded-xl tactical-corners overflow-hidden flex flex-col w-full">
      {/* Log Header */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-cyan-950/40 border-b border-cyan-500/20">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-cyan-400" />
          <span className="font-mono text-xs font-bold tracking-wider text-cyan-300">
            SYSTEM MISSION LOGS // EVENT STREAM
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-1 hover:bg-cyan-950 rounded text-cyan-400 transition-colors"
          >
            {isExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronUp className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {/* Log Content */}
      {isExpanded && (
        <div className="p-3 bg-black/60 font-mono text-xs max-h-36 overflow-y-auto flex flex-col gap-1 text-cyan-400/90 selection:bg-cyan-500 selection:text-black">
          {logs.length > 0 ? (
            logs.map((log, i) => (
              <div key={i} className="leading-relaxed hover:bg-cyan-950/20 px-1 rounded flex items-start gap-2">
                <span className="text-cyan-600 select-none">&gt;</span>
                <span className={log.includes('LOST') || log.includes('ERROR') ? 'text-red-400' : log.includes('ESTABLISHED') ? 'text-green-400' : 'text-cyan-200'}>
                  {log}
                </span>
              </div>
            ))
          ) : (
            <div className="text-cyan-700 italic">No events logged yet. System ready.</div>
          )}
        </div>
      )}
    </div>
  );
};
