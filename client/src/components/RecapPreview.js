import React from 'react';

function RecapPreview({ recap, weekData, onDownloadPdf, loading }) {
  return (
    <div className="recap-preview">
      <div className="recap-header">
        <h2>Week {weekData?.week} Newsletter Preview</h2>
        <button
          className="btn btn-success"
          onClick={onDownloadPdf}
          disabled={!!loading}
        >
          Download PDF
        </button>
      </div>

      <div className="recap-body">
        {recap.headline && (
          <div className="recap-section">
            <div className="recap-section-title">Week {weekData?.week} Recap</div>
            <div className="recap-section-body">{recap.headline}</div>
          </div>
        )}

        {recap.matchupStorylines && (
          <div className="recap-section">
            <div className="recap-section-title">Matchup Storylines</div>
            <div className="recap-section-body">{recap.matchupStorylines}</div>
          </div>
        )}

        {recap.weeklyMvp && (
          <div className="recap-section">
            <div className="recap-section-title">Weekly MVP</div>
            <div className="recap-section-body">{recap.weeklyMvp}</div>
          </div>
        )}

        {recap.powerRankings && (
          <div className="recap-section">
            <div className="recap-section-title">Power Rankings</div>
            <div className="recap-section-body">{recap.powerRankings}</div>
          </div>
        )}

        {recap.hotTakes && (
          <div className="recap-section">
            <div className="recap-section-title">Hot Takes & Predictions</div>
            <div className="recap-section-body">{recap.hotTakes}</div>
          </div>
        )}
      </div>
    </div>
  );
}

export default RecapPreview;
