window.Team5UI = window.Team5UI || {};

const Team5UI = window.Team5UI;
const { useEffect, useMemo, useRef, useState } = React;

Team5UI.App = function App() {
  const [userId, setUserId] = useState("");
  const [loggedInUser, setLoggedInUser] = useState(null);
  const [cityId, setCityId] = useState("tehran");
  const [limit, setLimit] = useState(5);
  const [users, setUsers] = useState([]);
  const [jsonOutput, setJsonOutput] = useState("در حال بارگذاری...");
  const [cardsPayload, setCardsPayload] = useState(null); // primary cards
  const [auxCardsPayload, setAuxCardsPayload] = useState(null); // tools/AB cards
  const [mainAction, setMainAction] = useState("popular");
  const [lastAuxAction, setLastAuxAction] = useState("");
  const [placesById, setPlacesById] = useState({});
  const [citiesById, setCitiesById] = useState({});
  const [isTraining, setIsTraining] = useState(false);
  const [trainingMessage, setTrainingMessage] = useState("");
  const [showNearestModal, setShowNearestModal] = useState(false);
  const [pendingNearestCityId, setPendingNearestCityId] = useState("tehran");
  const [showFeedbackPrompt, setShowFeedbackPrompt] = useState(false);
  const [isFeedbackMounted, setIsFeedbackMounted] = useState(false);
  const [isFeedbackExiting, setIsFeedbackExiting] = useState(false);
  const [feedbackMessage, setFeedbackMessage] = useState("");
  const [shineCards, setShineCards] = useState(false);
  const [dislikeFlashCards, setDislikeFlashCards] = useState(false);
  const [isSubmittingFeedback, setIsSubmittingFeedback] = useState(false);
  const [isFeedbackLocked, setIsFeedbackLocked] = useState(false);
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);
  const [expandedCommentsByMediaId, setExpandedCommentsByMediaId] = useState({});
  const [commentsByMediaId, setCommentsByMediaId] = useState({});
  const [commentsLoadingByMediaId, setCommentsLoadingByMediaId] = useState({});
  const [commentsErrorByMediaId, setCommentsErrorByMediaId] = useState({});
  const [abVersion, setAbVersion] = useState("AUTO");
  const [abStrategy, setAbStrategy] = useState("personalized");
  const feedbackHideTimerRef = useRef(null);

  const safeLimit = useMemo(() => {
    const parsed = Number(limit);
    if (!Number.isFinite(parsed)) return 5;
    return Math.min(100, Math.max(1, Math.floor(parsed)));
  }, [limit]);

  const shownMediaIds = useMemo(() => Team5UI.extractShownMediaIds(cardsPayload), [cardsPayload]);
  const canShowFeedback = Team5UI.FEEDBACK_ACTIONS.has(mainAction) && shownMediaIds.length > 0 && !feedbackSubmitted;
  const activeAbGroup = useMemo(() => {
    const group = auxCardsPayload?.metadata?.ab_test_group;
    if (group === "A" || group === "B") return group;
    return abVersion === "AUTO" ? "A" : abVersion;
  }, [auxCardsPayload, abVersion]);

  const profileData = useMemo(() => {
    const fn = (loggedInUser?.first_name || "").trim();
    const ln = (loggedInUser?.last_name || "").trim();
    const email = (loggedInUser?.email || "").trim();
    const initials = `${fn[0] || ""}${ln[0] || ""}`.toUpperCase() || (email[0] || "G").toUpperCase();
    return {
      initials,
      fullName: `${fn} ${ln}`.trim() || "Guest User",
      username: email ? `@${email.split("@")[0]}` : "@guest",
      email: email || "not signed in",
    };
  }, [loggedInUser]);

  const utilityActions = useMemo(
    () => ["users", "cities", "places", "media", "interests", "user-ratings", "ab-recommendations", "ab-summary", "ping"],
    []
  );
  const noUtilityCardsActions = useMemo(() => new Set(["users", "cities", "places"]), []);

  useEffect(() => {
    async function initializeApp() {
      await loadReferenceData();
      const currentUser = await loadCurrentUser();
      const resolvedUserId = await loadUsers(currentUser?.email);
      const initialUserId = resolvedUserId || "";
      if (initialUserId) {
        setUserId(initialUserId);
      }
      const initialAction = initialUserId ? "personalized" : "popular";
      setMainAction(initialAction);
      await callPrimaryAction(initialAction, initialUserId, cityId);
    }
    initializeApp();
  }, []);

  useEffect(() => {
    return () => {
      if (feedbackHideTimerRef.current) {
        window.clearTimeout(feedbackHideTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    setFeedbackMessage("");
    let timerId;
    let unmountId;

    if (canShowFeedback) {
      setIsFeedbackMounted(true);
      setIsFeedbackExiting(false);
      setShowFeedbackPrompt(false);
      timerId = window.setTimeout(() => setShowFeedbackPrompt(true), 3000);
    } else if (isFeedbackMounted) {
      setShowFeedbackPrompt(false);
      setIsFeedbackExiting(true);
      unmountId = window.setTimeout(() => {
        setIsFeedbackMounted(false);
        setIsFeedbackExiting(false);
      }, 360);
    }

    return () => {
      if (timerId) window.clearTimeout(timerId);
      if (unmountId) window.clearTimeout(unmountId);
    };
  }, [canShowFeedback, mainAction, jsonOutput]);

  async function loadReferenceData() {
    try {
      const res = await fetch(Team5UI.api("/team5/api/cities/"), { credentials: "same-origin" });
      const cities = await res.json();
      if (!Array.isArray(cities)) return;

      const cityMap = {};
      for (const city of cities) {
        cityMap[city.cityId] = city.cityName;
      }
      setCitiesById(cityMap);

      const placeMap = {};
      await Promise.all(
        cities.map(async (city) => {
          try {
            const placesRes = await fetch(
              Team5UI.api(`/team5/api/places/city/${encodeURIComponent(city.cityId)}/`),
              { credentials: "same-origin" }
            );
            const places = await placesRes.json();
            if (Array.isArray(places)) {
              for (const place of places) placeMap[place.placeId] = place;
            }
          } catch (_) {}
        })
      );
      setPlacesById(placeMap);
    } catch (_) {}
  }

  async function loadCurrentUser() {
    try {
      const endpoint = Team5UI.api("/api/auth/me/");
      const res = await fetch(endpoint, { credentials: "same-origin" });
      if (!res.ok) {
        setLoggedInUser(null);
        return null;
      }
      const payload = await res.json();
      const user = payload?.user || null;
      setLoggedInUser(user);
      return user;
    } catch (_) {
      setLoggedInUser(null);
      return null;
    }
  }

  async function loadUsers(preferredEmail) {
    const endpoint = Team5UI.api("/team5/api/users/");
    try {
      const res = await fetch(endpoint, { credentials: "same-origin" });
      const data = await res.json();
      const list = Array.isArray(data.items) ? data.items : [];
      setUsers(list);
      const wantedEmail = String(preferredEmail || "").trim().toLowerCase();
      const matched = wantedEmail
        ? list.find((item) => String(item.email || "").trim().toLowerCase() === wantedEmail)
        : null;
      const selected = matched?.userId || (userId || (list[0]?.userId || ""));
      if (selected) setUserId(selected);
      return selected;
    } catch (error) {
      setJsonOutput(JSON.stringify({ status: "network_error", endpoint, error: String(error) }, null, 2));
      return "";
    }
  }

  function endpointByAction(action, overrideUserId, cityOverride) {
    const effectiveUserId = String(overrideUserId ?? userId).trim();
    const encodedUser = encodeURIComponent(effectiveUserId);
    const encodedCity = encodeURIComponent(String(cityOverride ?? cityId).trim());
    switch (action) {
      case "rated-high":
      case "rated-low":
        return Team5UI.api(`/team5/api/media/?userId=${encodedUser}`);
      case "cities":
        return Team5UI.api("/team5/api/cities/");
      case "places":
        return Team5UI.api(`/team5/api/places/city/${encodedCity}/`);
      case "media":
        return Team5UI.api(`/team5/api/media/?userId=${encodedUser}`);
      case "users":
        return Team5UI.api("/team5/api/users/");
      case "user-ratings":
        return Team5UI.api(`/team5/api/users/${encodedUser}/ratings/`);
      case "popular":
        return Team5UI.api(`/team5/api/recommendations/popular/?limit=${safeLimit}&userId=${encodedUser}`);
      case "random":
        return Team5UI.api(`/team5/api/recommendations/random/?limit=${Math.max(10, safeLimit)}&userId=${encodedUser}`);
      case "nearest":
        return Team5UI.api(`/team5/api/recommendations/nearest/?limit=${safeLimit}&cityId=${encodedCity}&userId=${encodedUser}`);
      case "weather":
        return Team5UI.api(`/team5/api/recommendations/weather/?limit=${safeLimit}&userId=${encodedUser}`);
      case "occasions":
        return Team5UI.api(`/team5/api/recommendations/occasions/?limit=${safeLimit}&userId=${encodedUser}`);
      case "personalized":
        return Team5UI.api(`/team5/api/recommendations/personalized/?userId=${encodedUser}&limit=${safeLimit}`);
      case "interests":
        return Team5UI.api(`/team5/api/users/${encodedUser}/interests/`);
      case "ab-recommendations":
        return Team5UI.api(
          `/team5/api/recommendations/?userId=${encodedUser}&limit=${safeLimit}&strategy=${encodeURIComponent(abStrategy)}&version=${encodeURIComponent(abVersion)}`
        );
      case "ab-summary":
        return Team5UI.api("/team5/api/recommendations/ab/summary/?days=30");
      case "ping":
        return Team5UI.api("/team5/ping/");
      default:
        return null;
    }
  }

  async function fetchActionPayload(action, overrideUserId, cityOverride) {
    const endpoint = endpointByAction(action, overrideUserId, cityOverride);
    if (!endpoint) return;
    try {
      const res = await fetch(endpoint, { credentials: "same-origin" });
      const text = await res.text();
      let payload = text;
      try {
        payload = JSON.parse(text);
      } catch (_) {}
      return { status: res.status, endpoint, payload };
    } catch (error) {
      setJsonOutput(JSON.stringify({ status: "network_error", endpoint, error: String(error) }, null, 2));
      return null;
    }
  }

  async function callPrimaryAction(action, overrideUserId, cityOverride) {
    const result = await fetchActionPayload(action, overrideUserId, cityOverride);
    if (!result) return;
    if (feedbackHideTimerRef.current) {
      window.clearTimeout(feedbackHideTimerRef.current);
      feedbackHideTimerRef.current = null;
    }
    setMainAction(action);
    setIsFeedbackLocked(false);
    setFeedbackSubmitted(!Team5UI.FEEDBACK_ACTIONS.has(action));
    setShineCards(false);
    setDislikeFlashCards(false);
    let normalizedPayload = result.payload;
    if (action === "rated-high" && result.payload && typeof result.payload === "object") {
      normalizedPayload = { ratedHigh: Array.isArray(result.payload.ratedHigh) ? result.payload.ratedHigh : [] };
    } else if (action === "rated-low" && result.payload && typeof result.payload === "object") {
      normalizedPayload = { ratedLow: Array.isArray(result.payload.ratedLow) ? result.payload.ratedLow : [] };
    }
    setCardsPayload(normalizedPayload);
    setJsonOutput(JSON.stringify({ status: result.status, endpoint: result.endpoint, data: result.payload }, null, 2));
  }

  async function callUtilityAction(action) {
    const result = await fetchActionPayload(action);
    if (!result) return;
    setLastAuxAction(action);
    setAuxCardsPayload(result.payload);
    setJsonOutput(JSON.stringify({ status: result.status, endpoint: result.endpoint, data: result.payload }, null, 2));
  }

  function handlePrimaryTabClick(action) {
    if (action === "nearest") {
      setPendingNearestCityId(cityId);
      setShowNearestModal(true);
      return;
    }
    callPrimaryAction(action);
  }

  function confirmNearestSelection() {
    const selectedCity = String(pendingNearestCityId || cityId).trim() || cityId;
    setCityId(selectedCity);
    setShowNearestModal(false);
    callPrimaryAction("nearest", undefined, selectedCity);
  }

  function cancelNearestSelection() {
    setShowNearestModal(false);
  }

  async function trainModel() {
    setIsTraining(true);
    setTrainingMessage("Training started...");
    const endpoint = Team5UI.api("/team5/api/train");
    try {
      const res = await fetch(endpoint, { method: "POST", credentials: "same-origin" });
      const raw = await res.text();
      let payload;
      try {
        payload = JSON.parse(raw);
      } catch (_) {
        throw new Error(`Non-JSON response: ${raw.slice(0, 140)}`);
      }
      const statusRes = await fetch(Team5UI.api("/team5/api/ml/status"), { credentials: "same-origin" });
      const statusPayload = await statusRes.json();
      setTrainingMessage(
        `Train: ${payload.trained ? "OK" : "FAILED"} | modelsReady=${statusPayload.modelsReady} | mediaSamples=${statusPayload.mediaRatingsSamples}`
      );
      setJsonOutput(JSON.stringify({ status: res.status, endpoint, train: payload, mlStatus: statusPayload }, null, 2));
    } catch (error) {
      setTrainingMessage(`Train error: ${String(error)}`);
    } finally {
      setIsTraining(false);
    }
  }

  async function submitFeedback(liked) {
    if (!userId.trim()) {
      setFeedbackMessage("ابتدا یک کاربر انتخاب کن.");
      return;
    }
    if (!canShowFeedback) {
      setFeedbackMessage("فعلا آیتمی برای ثبت فیدبک وجود ندارد.");
      return;
    }
    setIsSubmittingFeedback(true);
    try {
      const endpoint = Team5UI.api("/team5/api/recommendations/feedback/");
      const res = await fetch(endpoint, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          userId: userId.trim(),
          action: mainAction,
          liked,
          version: activeAbGroup,
          shownMediaIds: shownMediaIds,
        }),
      });
      const payload = await res.json();
      if (!res.ok) {
        setFeedbackMessage(payload.detail || "ثبت فیدبک ناموفق بود.");
        return;
      }
      setFeedbackMessage(
        liked
          ? "ممنون از فیدبک مثبت، خوشحالیم خوشت اومده."
          : "برای دیدن پیشنهادهای جدید، مجدد وارد همین صفحه شوید."
      );
      if (liked) {
        setShineCards(true);
        window.setTimeout(() => setShineCards(false), 2500);
      } else {
        setDislikeFlashCards(true);
        window.setTimeout(() => setDislikeFlashCards(false), 1700);
      }
      setIsFeedbackLocked(true);
      if (feedbackHideTimerRef.current) {
        window.clearTimeout(feedbackHideTimerRef.current);
      }
      feedbackHideTimerRef.current = window.setTimeout(() => {
        setFeedbackSubmitted(true);
        setShowFeedbackPrompt(false);
        setIsFeedbackLocked(false);
        feedbackHideTimerRef.current = null;
      }, 2000);
    } catch (error) {
      setFeedbackMessage(`خطا در ثبت فیدبک: ${String(error)}`);
    } finally {
      setIsSubmittingFeedback(false);
    }
  }

  async function toggleComments(mediaId) {
    const key = String(mediaId || "").trim();
    if (!key) return;
    const isOpen = Boolean(expandedCommentsByMediaId[key]);
    if (isOpen) {
      setExpandedCommentsByMediaId((prev) => ({ ...prev, [key]: false }));
      return;
    }

    setExpandedCommentsByMediaId((prev) => ({ ...prev, [key]: true }));
    if (Array.isArray(commentsByMediaId[key])) return;

    setCommentsLoadingByMediaId((prev) => ({ ...prev, [key]: true }));
    setCommentsErrorByMediaId((prev) => ({ ...prev, [key]: "" }));
    try {
      const res = await fetch(Team5UI.api(`/team5/api/media/${encodeURIComponent(key)}/comments/`), {
        credentials: "same-origin",
      });
      const payload = await res.json();
      if (!res.ok) throw new Error(payload.detail || "خطا در دریافت کامنت‌ها");
      setCommentsByMediaId((prev) => ({ ...prev, [key]: Array.isArray(payload.items) ? payload.items : [] }));
    } catch (error) {
      setCommentsErrorByMediaId((prev) => ({ ...prev, [key]: String(error) }));
    } finally {
      setCommentsLoadingByMediaId((prev) => ({ ...prev, [key]: false }));
    }
  }

  return (
    <main className="container">
      <header className="top-navbar">
        <div className="brand-block">
          <div className="brand-logo">∞</div>
          <div className="brand-text">
            <h1>Infinity Recommendations</h1>
            <p>Smart personalized travel feed</p>
          </div>
        </div>
        <div className="profile-block">
          <div className="profile-avatar">{profileData.initials}</div>
          <div className="profile-meta">
            <p className="profile-name">{profileData.fullName}</p>
            <p className="profile-user">{profileData.username}</p>
            <p className="profile-email">{profileData.email}</p>
          </div>
        </div>
      </header>

      <section className="panel">
        <div className="recommendation-nav">
          <p className="recommendation-title">پیشنهادها</p>
          <div className="tabs-row">
            {Team5UI.PRIMARY_TABS.map((action) => (
              <button
                key={action}
                type="button"
                className={`tab-btn ${mainAction === action ? "active" : ""}`}
                onClick={() => handlePrimaryTabClick(action)}
              >
                {Team5UI.ACTION_LABELS[action] || action}
              </button>
            ))}
          </div>
        </div>
        <Team5UI.CardsView
          payload={cardsPayload}
          lastAction={mainAction}
          placesById={placesById}
          citiesById={citiesById}
          shineCards={shineCards}
          dislikeFlashCards={dislikeFlashCards}
          expandedCommentsByMediaId={expandedCommentsByMediaId}
          commentsByMediaId={commentsByMediaId}
          commentsLoadingByMediaId={commentsLoadingByMediaId}
          commentsErrorByMediaId={commentsErrorByMediaId}
          onToggleComments={toggleComments}
        />
      </section>

      {showNearestModal ? (
        <div className="modal-backdrop">
          <div className="modal-card">
            <h3>کدام شهر زندگی می‌کنید؟</h3>
            <p>برای نمایش نزدیک‌ترین پیشنهادها، شهر خود را انتخاب کنید.</p>
            <select value={pendingNearestCityId} onChange={(e) => setPendingNearestCityId(e.target.value)}>
              {Object.entries(citiesById).map(([id, name]) => (
                <option key={id} value={id}>{name}</option>
              ))}
            </select>
            <div className="modal-actions">
              <button type="button" onClick={confirmNearestSelection}>تایید</button>
              <button type="button" className="secondary" onClick={cancelNearestSelection}>انصراف</button>
            </div>
          </div>
        </div>
      ) : null}

      {isFeedbackMounted ? (
        <section className={`feedback-widget ${showFeedbackPrompt ? "show" : ""} ${isFeedbackExiting ? "hide" : ""}`}>
          <p className="feedback-title">این پیشنهادها برات مفید بود؟</p>
          <div className="feedback-actions">
            <button type="button" className="feedback-btn like" disabled={isSubmittingFeedback || isFeedbackLocked} onClick={() => submitFeedback(true)}>
              👍 پسندیدم
            </button>
            <button type="button" className="feedback-btn dislike" disabled={isSubmittingFeedback || isFeedbackLocked} onClick={() => submitFeedback(false)}>
              👎 نپسندیدم
            </button>
          </div>
          {feedbackMessage ? <p className="feedback-message">{feedbackMessage}</p> : null}
        </section>
      ) : null}

      <section className="panel">
        <h2>ابزارها و A/B</h2>
        <div className="form-grid compact">
          <label>
            Limit
            <input type="number" min="1" max="100" value={limit} onChange={(e) => setLimit(e.target.value)} />
          </label>
          <label>
            AB Version
            <select value={abVersion} onChange={(e) => setAbVersion((e.target.value || "AUTO").toUpperCase())}>
              <option value="AUTO">AUTO</option>
              <option value="A">A</option>
              <option value="B">B</option>
            </select>
          </label>
          <label>
            AB Strategy
            <select value={abStrategy} onChange={(e) => setAbStrategy(e.target.value)}>
              <option value="personalized">personalized</option>
              <option value="popular">popular</option>
              <option value="nearest">nearest</option>
              <option value="weather">weather</option>
              <option value="occasions">occasions</option>
              <option value="random">random</option>
            </select>
          </label>
        </div>
        <div className="actions utility-actions">
          <button type="button" onClick={trainModel} disabled={isTraining}>
            {isTraining ? "Training..." : "Train Model"}
          </button>
          {utilityActions.map((action) => (
            <button key={action} type="button" onClick={() => callUtilityAction(action)}>
              {Team5UI.ACTION_LABELS[action] || action}
            </button>
          ))}
        </div>
        {trainingMessage ? <p className="reason">{trainingMessage}</p> : null}
        <h3 className="section-title">خروجی JSON</h3>
        <pre>{jsonOutput}</pre>
        {auxCardsPayload && !noUtilityCardsActions.has(lastAuxAction) ? (
          <>
            <p className="reason">نمایش کارت‌های ابزار/AB: {Team5UI.ACTION_LABELS[lastAuxAction] || lastAuxAction}</p>
            <Team5UI.CardsView
              payload={auxCardsPayload}
              lastAction={lastAuxAction}
              placesById={placesById}
              citiesById={citiesById}
              shineCards={false}
              dislikeFlashCards={false}
              expandedCommentsByMediaId={expandedCommentsByMediaId}
              commentsByMediaId={commentsByMediaId}
              commentsLoadingByMediaId={commentsLoadingByMediaId}
              commentsErrorByMediaId={commentsErrorByMediaId}
              onToggleComments={toggleComments}
            />
          </>
        ) : null}
      </section>

      <div className="footer">
        <a href="/" className="back-btn">بازگشت به داشبورد اصلی</a>
      </div>
    </main>
  );
};
