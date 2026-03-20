import React, { useState } from 'react';
import LeagueInput from './components/LeagueInput';
import LeagueInfo from './components/LeagueInfo';
import RecapPreview from './components/RecapPreview';
import './App.css';

function App() {
  const [league, setLeague] = useState(null);
  const [weekData, setWeekData] = useState(null);
  const [recap, setRecap] = useState(null);
  const [loading, setLoading] = useState('');
  const [error, setError] = useState('');

  const loadLeague = async (leagueId) => {
    setError('');
    setLeague(null);
    setWeekData(null);
    setRecap(null);
    setLoading('Loading league...');

    try {
      const res = await fetch(`/api/league/${leagueId}`);
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || 'Failed to load league');
      }
      const data = await res.json();
      setLeague(data);

      // Also fetch current week data
      setLoading('Fetching matchup data...');
      const weekRes = await fetch(`/api/league/${leagueId}/week/${data.currentWeek}`);
      if (weekRes.ok) {
        const wd = await weekRes.json();
        setWeekData(wd);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading('');
    }
  };

  const generateRecap = async () => {
    if (!league) return;
    setError('');
    setRecap(null);
    setLoading('Generating AI recap... This may take 15-30 seconds.');

    try {
      const res = await fetch(
        `/api/league/${league.leagueId}/week/${league.currentWeek}/recap`,
        { method: 'POST' }
      );
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || 'Failed to generate recap');
      }
      const data = await res.json();
      setRecap(data.recap);
      setWeekData(data.leagueData);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading('');
    }
  };

  const downloadPdf = async () => {
    if (!weekData || !recap) return;
    setLoading('Generating PDF...');
    setError('');

    try {
      const res = await fetch(
        `/api/league/${league.leagueId}/week/${league.currentWeek}/pdf`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ leagueData: weekData, recap }),
        }
      );
      if (!res.ok) throw new Error('Failed to generate PDF');

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${weekData.leagueName.replace(/[^a-zA-Z0-9]/g, '_')}_Week${weekData.week}_Recap.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading('');
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-content">
          <span className="header-icon">🏈</span>
          <div>
            <h1>Fantasy Football Newsletter</h1>
            <p className="tagline">AI-Powered Weekly Recaps</p>
          </div>
        </div>
      </header>

      <main className="app-main">
        <LeagueInput onLoad={loadLeague} disabled={!!loading} />

        {loading && (
          <div className="status-bar loading">
            <div className="spinner" />
            <span>{loading}</span>
          </div>
        )}

        {error && (
          <div className="status-bar error">
            <span>{error}</span>
          </div>
        )}

        {league && !loading && (
          <LeagueInfo
            league={league}
            weekData={weekData}
            onGenerateRecap={generateRecap}
            hasRecap={!!recap}
          />
        )}

        {recap && (
          <RecapPreview
            recap={recap}
            weekData={weekData}
            onDownloadPdf={downloadPdf}
            loading={loading}
          />
        )}
      </main>

      <footer className="app-footer">
        Powered by Sleeper API & Claude AI
      </footer>
    </div>
  );
}

export default App;
