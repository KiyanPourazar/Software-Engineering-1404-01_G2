window.Team5UI = window.Team5UI || {};

const Team5UI = window.Team5UI;

Team5UI.StarRating = function StarRating({ value, muted = false }) {
  const numericValue = Number.isFinite(value) ? Math.max(0, Math.min(5, value)) : 0;
  const filledCount = Math.round(numericValue);
  return (
    <div className={`stars ${muted ? "muted" : ""}`} aria-label={`rating ${numericValue} out of 5`}>
      {[0, 1, 2, 3, 4].map((idx) => (
        <span key={idx} className={idx < filledCount ? "star filled" : "star"}>
          {idx < filledCount ? "★" : "☆"}
        </span>
      ))}
    </div>
  );
};
