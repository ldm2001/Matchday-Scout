'use client';

import { useState, useEffect } from 'react';
import { Team } from '@/types';
import { getTeams } from '@/lib/api';

interface TeamSelectorProps {
    selectedTeam: Team | null;
    onTeamSelect: (team: Team) => void;
}

export default function TeamSelector({ selectedTeam, onTeamSelect }: TeamSelectorProps) {
    const [teams, setTeams] = useState<Team[]>([]);
    const [isOpen, setIsOpen] = useState(false);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        async function loadTeams() {
            try {
                const data = await getTeams();
                setTeams(data.teams);
            } catch (error) {
                console.error('Failed to load teams:', error);
            } finally {
                setLoading(false);
            }
        }
        loadTeams();
    }, []);

    if (loading) {
        return (
            <div className="h-12 w-64 bg-slate-700 rounded-lg animate-pulse" />
        );
    }

    return (
        <div className="relative">
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="flex items-center justify-between w-64 px-4 py-3 bg-slate-800 border border-slate-600 rounded-lg hover:border-blue-500 transition-colors"
            >
                <span className={selectedTeam ? 'text-white' : 'text-slate-400'}>
                    {selectedTeam?.team_name || '상대팀 선택'}
                </span>
                <svg
                    className={`w-5 h-5 text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''}`}
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
            </button>

            {isOpen && (
                <div className="absolute z-50 w-64 mt-2 bg-slate-800 border border-slate-600 rounded-lg shadow-xl max-h-80 overflow-y-auto">
                    {teams.map((team) => (
                        <button
                            key={team.team_id}
                            onClick={() => {
                                onTeamSelect(team);
                                setIsOpen(false);
                            }}
                            className={`w-full px-4 py-3 text-left hover:bg-slate-700 transition-colors first:rounded-t-lg last:rounded-b-lg ${selectedTeam?.team_id === team.team_id ? 'bg-blue-600/20 text-blue-400' : 'text-white'
                                }`}
                        >
                            {team.team_name}
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
}
