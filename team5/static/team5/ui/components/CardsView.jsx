window.Team5UI = window.Team5UI || {};

const Team5UI = window.Team5UI;

Team5UI.CardsView = function CardsView({
  payload,
  lastAction,
  placesById,
  citiesById,
  shineCards,
  dislikeFlashCards,
  expandedCommentsByMediaId,
  commentsByMediaId,
  commentsLoadingByMediaId,
  commentsErrorByMediaId,
  onToggleComments,
}) {
  const sections = [];
  if (Array.isArray(payload)) {
    sections.push({ title: Team5UI.ACTION_LABELS[lastAction] || "Items", items: payload });
  } else if (payload && typeof payload === "object") {
    if (payload.data && typeof payload.data === "object" && Array.isArray(payload.data.items)) {
      sections.push({ title: Team5UI.ACTION_LABELS[lastAction] || "Items", items: payload.data.items });
    }
    if (Array.isArray(payload.sections)) {
      for (const section of payload.sections) {
        sections.push({
          title: section.title || "Items",
          subtitle: section.subtitle || "",
          items: Array.isArray(section.items) ? section.items : [],
        });
      }
    }
    if (Array.isArray(payload.highRatedItems)) sections.push({ title: "Personalized", items: payload.highRatedItems });
    if (Array.isArray(payload.similarItems)) sections.push({ title: "Similars", items: payload.similarItems });
    if (Array.isArray(payload.ratedHigh)) sections.push({ title: "Rated High", items: payload.ratedHigh });
    if (Array.isArray(payload.ratedLow)) sections.push({ title: "Rated Low", items: payload.ratedLow });
    if (Array.isArray(payload.items) && !sections.length) sections.push({ title: Team5UI.ACTION_LABELS[lastAction] || "Items", items: payload.items });
  }

  const hasAny = sections.some((sec) => sec.items && sec.items.length);
  if (!hasAny) return <p className="empty">داده‌ای برای نمایش کارت وجود ندارد.</p>;

  return (
    <>
      {sections.map((section) => (
        <React.Fragment key={section.title}>
          <h3 className="section-title">{section.title}</h3>
          {section.subtitle ? <p className="reason">{section.subtitle}</p> : null}
          <div className="cards">
            {section.items.map((item, index) => {
              const mediaId = Team5UI.getMediaIdFromItem(item);
              return (
                <Team5UI.MediaCard
                  key={`${item.mediaId || item.placeId || "item"}-${index}`}
                  item={item}
                  place={placesById[item.placeId || item.media?.placeId]}
                  citiesById={citiesById}
                  shineCards={shineCards}
                  dislikeFlashCards={dislikeFlashCards}
                  comments={commentsByMediaId[mediaId] || []}
                  isCommentsOpen={Boolean(expandedCommentsByMediaId[mediaId])}
                  isCommentsLoading={Boolean(commentsLoadingByMediaId[mediaId])}
                  commentsError={commentsErrorByMediaId[mediaId] || ""}
                  onToggleComments={() => onToggleComments(mediaId)}
                />
              );
            })}
          </div>
        </React.Fragment>
      ))}
    </>
  );
};
