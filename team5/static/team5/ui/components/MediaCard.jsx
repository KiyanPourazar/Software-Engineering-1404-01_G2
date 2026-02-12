window.Team5UI = window.Team5UI || {};

const Team5UI = window.Team5UI;

Team5UI.MediaCard = function MediaCard({
  item,
  place,
  citiesById,
  shineCards,
  dislikeFlashCards,
  comments,
  isCommentsOpen,
  isCommentsLoading,
  commentsError,
  onToggleComments,
}) {
  const mediaSource = item.media && typeof item.media === "object" ? item.media : item;
  const mediaId = Team5UI.getMediaIdFromItem(item);
  const cityName = place ? citiesById[place.cityId] || place.cityId : "-";
  const placeName = place?.placeName || mediaSource.placeName || mediaSource.title || mediaSource.mediaId || item.mediaId || "Content";
  const authorName = (mediaSource.authorDisplayName || "Team5 Traveler").trim();
  const userName = `@${authorName.replace(/\s+/g, "").toLowerCase() || "team5user"}`;
  const locationText = `${placeName} • ${cityName}`;
  const captionText = (mediaSource.caption || "").trim() || "این پست بدون کپشن ثبت شده است.";
  const avgRate = Number(item.overallRate ?? mediaSource.overallRate);
  const userRate = Number(item.userRate ?? item.rate);
  const hasUserRate = Number.isFinite(userRate);
  const avgText = Number.isFinite(avgRate) ? avgRate.toFixed(2) : "-";
  const userText = hasUserRate ? userRate.toFixed(1) : "ثبت نشده";
  const reason = item.matchReason ? Team5UI.REASON_LABELS[item.matchReason] || item.matchReason : "";
  const triggerComment = (item.triggerComment || "").trim();
  const image = (mediaSource.mediaImageUrl || "").trim();
  const createdAt = (mediaSource.createdAt || item.createdAt || "").trim();
  const hasImage = Boolean(image);
  const initials = authorName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join("") || "TU";

  return (
    <article className={`card card-modern ${shineCards ? "shine" : ""} ${dislikeFlashCards ? "dislike-flash" : ""} ${!hasImage ? "text-only" : ""}`}>
      {mediaId ? (
        <button type="button" className="comment-toggle-btn" onClick={onToggleComments} aria-expanded={isCommentsOpen}>
          💬 {isCommentsOpen ? "بستن" : "نظرات"}
        </button>
      ) : null}
      <div className="post-header">
        <div className="author-avatar">{initials}</div>
        <div className="author-meta">
          <p className="author-name">{authorName}</p>
          <p className="author-username">{userName}</p>
          <p className="author-location">{locationText}</p>
          {createdAt ? <p className="author-date">📅 {createdAt}</p> : null}
        </div>
      </div>
      {hasImage ? (
        <div className="card-image-wrap">
          <img className="card-image" src={image} alt={placeName} loading="lazy" />
          {reason ? <span className="chip">{reason}</span> : null}
        </div>
      ) : reason ? (
        <span className="chip chip-inline">{reason}</span>
      ) : null}
      <p className="caption-text">{captionText}</p>
      {triggerComment ? (
        <p className="reason trigger-comment">💬 نظر شما: {triggerComment}</p>
      ) : null}
      {isCommentsOpen ? (
        <div className="comments-panel">
          <p className="comments-title">نظرات کاربران</p>
          {isCommentsLoading ? <p className="comments-hint">در حال دریافت نظرات...</p> : null}
          {!isCommentsLoading && commentsError ? <p className="comments-error">{commentsError}</p> : null}
          {!isCommentsLoading && !commentsError && comments.length === 0 ? (
            <p className="comments-hint">برای این مدیا نظری ثبت نشده است.</p>
          ) : null}
          {!isCommentsLoading && !commentsError && comments.length > 0 ? (
            <ul className="comments-list">
              {comments.map((comment, idx) => (
                <li key={`${comment.userId || "u"}-${idx}`} className={`comment-item ${comment.sentimentLabel || "neutral"}`}>
                  <span className="comment-head">{comment.userDisplayName || (comment.userEmail || "anonymous").split("@")[0]} • {comment.sentimentLabel || "neutral"}</span>
                  <p>{comment.body || ""}</p>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
      <div className="stats">
        <div className="stat">
          <span className="label">میانگین</span>
          <span className="value">{avgText}</span>
          <Team5UI.StarRating value={avgRate} />
        </div>
        <div className="stat">
          <span className="label">امتیاز کاربر</span>
          <span className="value user">{userText}</span>
          <Team5UI.StarRating value={userRate} muted={!hasUserRate} />
        </div>
      </div>
    </article>
  );
};
