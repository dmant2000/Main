const express = require('express');
const router = express.Router();
const sleeper = require('../services/sleeper');
const { generateRecap } = require('../services/claude');
const { generatePdf } = require('../services/pdf');

// GET /api/league/:leagueId — Fetch league info + current NFL week
router.get('/league/:leagueId', async (req, res) => {
  try {
    const { leagueId } = req.params;
    const [league, nflState] = await Promise.all([
      sleeper.getLeague(leagueId),
      sleeper.getNflState(),
    ]);

    if (!league) {
      return res.status(404).json({ error: 'League not found' });
    }

    // Determine the current/latest completed week
    const currentWeek = nflState.week || 1;

    res.json({
      leagueId,
      leagueName: league.name,
      season: league.season,
      currentWeek,
      totalRosters: league.total_rosters,
      status: league.status,
      nflSeason: nflState.season,
      nflSeasonType: nflState.season_type,
    });
  } catch (err) {
    if (err.response?.status === 404) {
      return res.status(404).json({ error: 'League not found. Check your league ID.' });
    }
    console.error('Error fetching league:', err.message);
    res.status(500).json({ error: 'Failed to fetch league data' });
  }
});

// GET /api/league/:leagueId/week/:week — Fetch weekly matchup data
router.get('/league/:leagueId/week/:week', async (req, res) => {
  try {
    const { leagueId, week } = req.params;
    const data = await sleeper.getWeeklyRecapData(leagueId, parseInt(week, 10));
    res.json(data);
  } catch (err) {
    console.error('Error fetching weekly data:', err.message);
    res.status(500).json({ error: 'Failed to fetch weekly data' });
  }
});

// POST /api/league/:leagueId/week/:week/recap — Generate AI recap
router.post('/league/:leagueId/week/:week/recap', async (req, res) => {
  try {
    const { leagueId, week } = req.params;
    const leagueData = await sleeper.getWeeklyRecapData(leagueId, parseInt(week, 10));
    const recap = await generateRecap(leagueData);

    res.json({ leagueData, recap });
  } catch (err) {
    console.error('Error generating recap:', err.message);
    res.status(500).json({ error: 'Failed to generate recap. Check your ANTHROPIC_API_KEY.' });
  }
});

// POST /api/league/:leagueId/week/:week/pdf — Generate and download PDF
router.post('/league/:leagueId/week/:week/pdf', async (req, res) => {
  try {
    const { leagueData, recap } = req.body;

    if (!leagueData || !recap) {
      return res.status(400).json({ error: 'Missing leagueData or recap in request body' });
    }

    const pdfBuffer = await generatePdf(leagueData, recap);

    const filename = `${leagueData.leagueName.replace(/[^a-zA-Z0-9]/g, '_')}_Week${leagueData.week}_Recap.pdf`;
    res.set({
      'Content-Type': 'application/pdf',
      'Content-Disposition': `attachment; filename="${filename}"`,
      'Content-Length': pdfBuffer.length,
    });
    res.send(pdfBuffer);
  } catch (err) {
    console.error('Error generating PDF:', err.message);
    res.status(500).json({ error: 'Failed to generate PDF' });
  }
});

module.exports = router;
