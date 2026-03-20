const axios = require('axios');

const BASE_URL = 'https://api.sleeper.app/v1';

async function getLeague(leagueId) {
  const { data } = await axios.get(`${BASE_URL}/league/${leagueId}`);
  return data;
}

async function getLeagueUsers(leagueId) {
  const { data } = await axios.get(`${BASE_URL}/league/${leagueId}/users`);
  return data;
}

async function getLeagueRosters(leagueId) {
  const { data } = await axios.get(`${BASE_URL}/league/${leagueId}/rosters`);
  return data;
}

async function getMatchups(leagueId, week) {
  const { data } = await axios.get(`${BASE_URL}/league/${leagueId}/matchups/${week}`);
  return data;
}

async function getNflState() {
  const { data } = await axios.get(`${BASE_URL}/state/nfl`);
  return data;
}

async function getPlayers() {
  const { data } = await axios.get(`${BASE_URL}/players/nfl`);
  return data;
}

/**
 * Fetches all league data needed for a weekly recap.
 * Returns structured data with matchups, standings, and roster info.
 */
async function getWeeklyRecapData(leagueId, week) {
  const [league, users, rosters, matchups, nflState] = await Promise.all([
    getLeague(leagueId),
    getLeagueUsers(leagueId),
    getLeagueRosters(leagueId),
    getMatchups(leagueId, week),
    getNflState(),
  ]);

  // Map user_id -> display_name
  const userMap = {};
  for (const user of users) {
    userMap[user.user_id] = {
      displayName: user.display_name,
      teamName: user.metadata?.team_name || user.display_name,
      avatar: user.avatar,
    };
  }

  // Map roster_id -> owner info and record
  const rosterMap = {};
  for (const roster of rosters) {
    const owner = userMap[roster.owner_id] || {
      displayName: 'Unknown',
      teamName: 'Unknown',
    };
    rosterMap[roster.roster_id] = {
      rosterId: roster.roster_id,
      ownerId: roster.owner_id,
      displayName: owner.displayName,
      teamName: owner.teamName,
      wins: roster.settings?.wins || 0,
      losses: roster.settings?.losses || 0,
      ties: roster.settings?.ties || 0,
      pointsFor: (roster.settings?.fpts || 0) + (roster.settings?.fpts_decimal || 0) / 100,
      pointsAgainst: (roster.settings?.fpts_against || 0) + (roster.settings?.fpts_against_decimal || 0) / 100,
      players: roster.players || [],
      starters: roster.starters || [],
    };
  }

  // Pair matchups by matchup_id
  const matchupPairs = {};
  for (const m of matchups) {
    if (!m.matchup_id) continue;
    if (!matchupPairs[m.matchup_id]) {
      matchupPairs[m.matchup_id] = [];
    }
    matchupPairs[m.matchup_id].push({
      rosterId: m.roster_id,
      points: m.points || 0,
      starters: m.starters || [],
      starterPoints: m.starters_points || [],
      players: m.players || [],
      playersPoints: m.players_points || {},
    });
  }

  // Build structured matchup results
  const matchupResults = Object.values(matchupPairs).map((pair) => {
    const [team1, team2] = pair;
    const roster1 = rosterMap[team1.rosterId] || {};
    const roster2 = rosterMap[team2.rosterId] || {};
    return {
      team1: {
        teamName: roster1.teamName,
        displayName: roster1.displayName,
        points: team1.points,
        starters: team1.starters,
        starterPoints: team1.starterPoints,
      },
      team2: {
        teamName: roster2.teamName,
        displayName: roster2.displayName,
        points: team2.points,
        starters: team2.starters,
        starterPoints: team2.starterPoints,
      },
      winner: team1.points > team2.points ? roster1.teamName : roster2.teamName,
      margin: Math.abs(team1.points - team2.points).toFixed(2),
    };
  });

  // Build standings sorted by wins desc, then points for desc
  const standings = Object.values(rosterMap)
    .sort((a, b) => {
      if (b.wins !== a.wins) return b.wins - a.wins;
      return b.pointsFor - a.pointsFor;
    })
    .map((r, index) => ({
      rank: index + 1,
      teamName: r.teamName,
      displayName: r.displayName,
      wins: r.wins,
      losses: r.losses,
      ties: r.ties,
      pointsFor: r.pointsFor.toFixed(2),
      pointsAgainst: r.pointsAgainst.toFixed(2),
    }));

  // Find top scorer of the week across all matchups
  let topScorer = { teamName: '', points: 0 };
  for (const m of matchups) {
    const roster = rosterMap[m.roster_id];
    if (roster && (m.points || 0) > topScorer.points) {
      topScorer = { teamName: roster.teamName, displayName: roster.displayName, points: m.points };
    }
  }

  return {
    leagueName: league.name,
    season: league.season,
    week,
    totalWeeks: league.settings?.playoff_week_start
      ? league.settings.playoff_week_start - 1
      : 14,
    scoringType: league.scoring_settings ? 'custom' : 'standard',
    matchups: matchupResults,
    standings,
    topScorer,
    nflState,
  };
}

module.exports = {
  getLeague,
  getLeagueUsers,
  getLeagueRosters,
  getMatchups,
  getNflState,
  getWeeklyRecapData,
};
