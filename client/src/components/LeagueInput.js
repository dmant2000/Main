import React, { useState } from 'react';

function LeagueInput({ onLoad, disabled }) {
  const [leagueId, setLeagueId] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    const trimmed = leagueId.trim();
    if (trimmed) {
      onLoad(trimmed);
    }
  };

  return (
    <div className="league-input-section">
      <label htmlFor="league-id">Sleeper League ID</label>
      <form onSubmit={handleSubmit}>
        <div className="input-row">
          <input
            id="league-id"
            type="text"
            value={leagueId}
            onChange={(e) => setLeagueId(e.target.value)}
            placeholder="e.g. 924039165495783424"
            disabled={disabled}
          />
          <button type="submit" className="btn btn-primary" disabled={disabled || !leagueId.trim()}>
            Load League
          </button>
        </div>
      </form>
      <p className="help-text">
        Find your league ID in the Sleeper app: League Settings &gt; General &gt; League ID
      </p>
    </div>
  );
}

export default LeagueInput;
