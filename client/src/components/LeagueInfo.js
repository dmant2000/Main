import React from 'react';

function LeagueInfo({ league, weekData, onGenerateRecap, hasRecap }) {
  return (
    <div className="league-info">
      <div className="league-header">
        <div>
          <div className="league-name">{league.leagueName}</div>
          <div className="league-meta">
            {league.season} Season &middot; {league.totalRosters} Teams &middot; Week {league.currentWeek}
          </div>
        </div>
        <span className="league-badge">{league.status}</span>
      </div>

      {weekData && weekData.matchups && weekData.matchups.length > 0 && (
        <div className="matchups-grid">
          {weekData.matchups.map((m, i) => (
            <div key={i} className="matchup-card">
              <div className={`matchup-team ${m.team1.points > m.team2.points ? 'winner' : ''}`}>
                <span className="matchup-team-name">{m.team1.teamName}</span>
                <span className="matchup-score">{m.team1.points}</span>
              </div>
              <div className="matchup-vs">VS</div>
              <div className={`matchup-team ${m.team2.points > m.team1.points ? 'winner' : ''}`}>
                <span className="matchup-team-name">{m.team2.teamName}</span>
                <span className="matchup-score">{m.team2.points}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="generate-section">
        <button className="btn btn-accent" onClick={onGenerateRecap} disabled={hasRecap}>
          {hasRecap ? 'Recap Generated' : 'Generate Recap'}
        </button>
      </div>
    </div>
  );
}

export default LeagueInfo;
