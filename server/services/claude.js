const Anthropic = require('@anthropic-ai/sdk');

const client = new Anthropic();

/**
 * Generates a narrative weekly recap using Claude.
 */
async function generateRecap(leagueData) {
  const prompt = buildPrompt(leagueData);

  const message = await client.messages.create({
    model: 'claude-sonnet-4-20250514',
    max_tokens: 4096,
    messages: [
      {
        role: 'user',
        content: prompt,
      },
    ],
  });

  const text = message.content
    .filter((block) => block.type === 'text')
    .map((block) => block.text)
    .join('\n');

  return parseRecapSections(text);
}

function buildPrompt(data) {
  const matchupSummaries = data.matchups
    .map(
      (m) =>
        `${m.team1.teamName} (${m.team1.points} pts) vs ${m.team2.teamName} (${m.team2.points} pts) — Winner: ${m.winner} by ${m.margin}`
    )
    .join('\n');

  const standingsTable = data.standings
    .map(
      (s) =>
        `${s.rank}. ${s.teamName} (${s.wins}-${s.losses}${s.ties > 0 ? `-${s.ties}` : ''}) — PF: ${s.pointsFor} | PA: ${s.pointsAgainst}`
    )
    .join('\n');

  return `You are a witty, entertaining fantasy football newsletter writer. Generate a weekly recap newsletter for a fantasy football league.

League: ${data.leagueName}
Season: ${data.season}
Week: ${data.week}

MATCHUP RESULTS:
${matchupSummaries}

CURRENT STANDINGS:
${standingsTable}

TOP SCORER THIS WEEK: ${data.topScorer.teamName} with ${data.topScorer.points} points

Write the newsletter with these exact sections, using the exact headers shown (including the emoji):

1. "🏈 Week ${data.week} Recap: ${data.leagueName}" — A catchy opening paragraph summarizing the week's action.

2. "⚔️ Matchup Storylines" — A narrative breakdown of each matchup. Highlight blowouts, close games, and upsets. Be entertaining and use sports metaphors.

3. "🏆 Weekly MVP" — Celebrate the top-scoring team this week with flair.

4. "📊 Power Rankings" — Your subjective power rankings of all teams based on record, points, and recent performance. Number them 1 through ${data.standings.length}. Include a brief hot take for each team.

5. "🔥 Hot Takes & Predictions" — 3-4 bold, fun predictions or hot takes about the league going forward.

Keep the tone fun, energetic, and engaging — like a real sports columnist. Use team names throughout. Do not use markdown formatting like ** or ## — write in plain text with the section headers exactly as specified above.`;
}

function parseRecapSections(text) {
  const sections = {
    headline: '',
    matchupStorylines: '',
    weeklyMvp: '',
    powerRankings: '',
    hotTakes: '',
    fullText: text,
  };

  const sectionPatterns = [
    { key: 'headline', pattern: /🏈[^\n]*\n([\s\S]*?)(?=⚔️|$)/ },
    { key: 'matchupStorylines', pattern: /⚔️[^\n]*\n([\s\S]*?)(?=🏆|$)/ },
    { key: 'weeklyMvp', pattern: /🏆[^\n]*\n([\s\S]*?)(?=📊|$)/ },
    { key: 'powerRankings', pattern: /📊[^\n]*\n([\s\S]*?)(?=🔥|$)/ },
    { key: 'hotTakes', pattern: /🔥[^\n]*\n([\s\S]*?)$/ },
  ];

  for (const { key, pattern } of sectionPatterns) {
    const match = text.match(pattern);
    if (match) {
      sections[key] = match[1].trim();
    }
  }

  return sections;
}

module.exports = { generateRecap };
