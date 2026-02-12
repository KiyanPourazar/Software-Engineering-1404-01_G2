window.Team5UI = window.Team5UI || {};

const Team5UI = window.Team5UI;

Team5UI.api = function api(path) {
  return `${Team5UI.API_BASE}${path}`;
};

Team5UI.extractShownMediaIds = function extractShownMediaIds(payload) {
  if (!payload || typeof payload !== "object") return [];
  const ids = [];
  const pushId = (value) => {
    const text = String(value || "").trim();
    if (text) ids.push(text);
  };

  if (Array.isArray(payload.items)) payload.items.forEach((item) => pushId(item?.mediaId));
  if (Array.isArray(payload.highRatedItems)) payload.highRatedItems.forEach((item) => pushId(item?.mediaId));
  if (Array.isArray(payload.similarItems)) payload.similarItems.forEach((item) => pushId(item?.mediaId));
  if (Array.isArray(payload.ratedHigh)) payload.ratedHigh.forEach((item) => pushId(item?.mediaId));
  if (Array.isArray(payload.ratedLow)) payload.ratedLow.forEach((item) => pushId(item?.mediaId));
  if (Array.isArray(payload.sections)) {
    payload.sections.forEach((section) => {
      if (!Array.isArray(section?.items)) return;
      section.items.forEach((item) => pushId(item?.mediaId));
    });
  }

  return [...new Set(ids)];
};

Team5UI.getMediaIdFromItem = function getMediaIdFromItem(item) {
  if (!item || typeof item !== "object") return "";
  const media = item.media && typeof item.media === "object" ? item.media : null;
  const mediaId = String(item.mediaId || media?.mediaId || "").trim();
  return mediaId;
};
