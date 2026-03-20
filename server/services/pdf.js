const puppeteer = require('puppeteer-core');

/**
 * Generates a PDF from the recap data and league info.
 * Returns a Buffer containing the PDF.
 */
async function generatePdf(leagueData, recap) {
  const html = buildHtml(leagueData, recap);

  const browser = await puppeteer.launch({
    headless: true,
    executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium-browser',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu'],
  });

  try {
    const page = await browser.newPage();
    await page.setContent(html, { waitUntil: 'networkidle0' });
    const pdf = await page.pdf({
      format: 'A4',
      printBackground: true,
      margin: { top: '0.5in', bottom: '0.5in', left: '0.5in', right: '0.5in' },
    });
    return pdf;
  } finally {
    await browser.close();
  }
}

function buildHtml(leagueData, recap) {
  const matchupRows = leagueData.matchups
    .map(
      (m) => `
      <div class="matchup-card">
        <div class="matchup-teams">
          <div class="team ${m.team1.points > m.team2.points ? 'winner' : ''}">
            <span class="team-name">${escapeHtml(m.team1.teamName)}</span>
            <span class="team-score">${m.team1.points}</span>
          </div>
          <div class="vs">VS</div>
          <div class="team ${m.team2.points > m.team1.points ? 'winner' : ''}">
            <span class="team-name">${escapeHtml(m.team2.teamName)}</span>
            <span class="team-score">${m.team2.points}</span>
          </div>
        </div>
      </div>`
    )
    .join('');

  const standingsRows = leagueData.standings
    .map(
      (s) => `
      <tr>
        <td class="rank">${s.rank}</td>
        <td class="team-cell">${escapeHtml(s.teamName)}</td>
        <td>${s.wins}-${s.losses}${s.ties > 0 ? `-${s.ties}` : ''}</td>
        <td>${s.pointsFor}</td>
        <td>${s.pointsAgainst}</td>
      </tr>`
    )
    .join('');

  return `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap');

  * { margin: 0; padding: 0; box-sizing: border-box; }

  body {
    font-family: 'Inter', -apple-system, sans-serif;
    color: #1a1a2e;
    background: #ffffff;
    line-height: 1.6;
  }

  .header {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    color: white;
    padding: 40px 30px;
    text-align: center;
    border-bottom: 4px solid #e94560;
  }

  .header h1 {
    font-size: 28px;
    font-weight: 900;
    text-transform: uppercase;
    letter-spacing: 2px;
    margin-bottom: 5px;
  }

  .header .subtitle {
    font-size: 14px;
    opacity: 0.8;
    text-transform: uppercase;
    letter-spacing: 3px;
  }

  .content {
    max-width: 100%;
    padding: 30px;
  }

  .section {
    margin-bottom: 30px;
    page-break-inside: avoid;
  }

  .section-title {
    font-size: 20px;
    font-weight: 800;
    color: #1a1a2e;
    border-bottom: 3px solid #e94560;
    padding-bottom: 8px;
    margin-bottom: 15px;
    text-transform: uppercase;
    letter-spacing: 1px;
  }

  .section-body {
    font-size: 13px;
    line-height: 1.8;
    color: #333;
    white-space: pre-wrap;
  }

  .scoreboard {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin-bottom: 10px;
  }

  .matchup-card {
    background: #f8f9fa;
    border-radius: 8px;
    padding: 15px;
    border-left: 4px solid #0f3460;
  }

  .matchup-teams {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
  }

  .matchup-teams .team {
    flex: 1;
    text-align: center;
  }

  .matchup-teams .team.winner .team-score {
    color: #e94560;
    font-weight: 800;
  }

  .matchup-teams .team.winner .team-name {
    font-weight: 700;
  }

  .team-name {
    display: block;
    font-size: 11px;
    font-weight: 600;
    margin-bottom: 4px;
  }

  .team-score {
    display: block;
    font-size: 22px;
    font-weight: 700;
    color: #1a1a2e;
  }

  .vs {
    font-size: 11px;
    font-weight: 800;
    color: #999;
    flex-shrink: 0;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
  }

  thead {
    background: #1a1a2e;
    color: white;
  }

  th {
    padding: 10px 12px;
    text-align: left;
    font-weight: 700;
    text-transform: uppercase;
    font-size: 11px;
    letter-spacing: 1px;
  }

  td {
    padding: 8px 12px;
    border-bottom: 1px solid #eee;
  }

  tr:nth-child(even) {
    background: #f8f9fa;
  }

  .rank {
    font-weight: 800;
    color: #e94560;
    width: 30px;
  }

  .team-cell {
    font-weight: 600;
  }

  .mvp-banner {
    background: linear-gradient(135deg, #e94560, #ff6b6b);
    color: white;
    padding: 20px;
    border-radius: 8px;
    text-align: center;
  }

  .mvp-banner .mvp-label {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 3px;
    opacity: 0.9;
  }

  .mvp-banner .mvp-name {
    font-size: 22px;
    font-weight: 900;
    margin: 5px 0;
  }

  .mvp-banner .mvp-points {
    font-size: 16px;
    font-weight: 600;
  }

  .footer {
    text-align: center;
    padding: 20px;
    font-size: 11px;
    color: #999;
    border-top: 1px solid #eee;
  }
</style>
</head>
<body>
  <div class="header">
    <div class="subtitle">${escapeHtml(leagueData.season)} Season — Week ${leagueData.week}</div>
    <h1>${escapeHtml(leagueData.leagueName)}</h1>
    <div class="subtitle">Weekly Recap Newsletter</div>
  </div>

  <div class="content">
    <div class="section">
      <div class="section-title">🏈 Week ${leagueData.week} Recap</div>
      <div class="section-body">${escapeHtml(recap.headline)}</div>
    </div>

    <div class="section">
      <div class="section-title">📋 Scoreboard</div>
      <div class="scoreboard">
        ${matchupRows}
      </div>
    </div>

    <div class="section">
      <div class="section-title">⚔️ Matchup Storylines</div>
      <div class="section-body">${escapeHtml(recap.matchupStorylines)}</div>
    </div>

    <div class="section">
      <div class="mvp-banner">
        <div class="mvp-label">🏆 Weekly MVP</div>
        <div class="mvp-name">${escapeHtml(leagueData.topScorer.teamName)}</div>
        <div class="mvp-points">${leagueData.topScorer.points} Points</div>
      </div>
      <div class="section-body" style="margin-top: 12px;">${escapeHtml(recap.weeklyMvp)}</div>
    </div>

    <div class="section">
      <div class="section-title">📊 Standings</div>
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Team</th>
            <th>Record</th>
            <th>PF</th>
            <th>PA</th>
          </tr>
        </thead>
        <tbody>
          ${standingsRows}
        </tbody>
      </table>
    </div>

    <div class="section">
      <div class="section-title">📊 Power Rankings</div>
      <div class="section-body">${escapeHtml(recap.powerRankings)}</div>
    </div>

    <div class="section">
      <div class="section-title">🔥 Hot Takes & Predictions</div>
      <div class="section-body">${escapeHtml(recap.hotTakes)}</div>
    </div>
  </div>

  <div class="footer">
    Generated by Fantasy Football Newsletter Generator — Powered by Claude AI
  </div>
</body>
</html>`;
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

module.exports = { generatePdf };
