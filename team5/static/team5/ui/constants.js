window.Team5UI = window.Team5UI || {};

const Team5UI = window.Team5UI;

Team5UI.API_BASE = "";

Team5UI.FEEDBACK_ACTIONS = new Set(["popular", "personalized", "nearest", "weather", "occasions", "random"]);

Team5UI.ACTION_LABELS = {
  users: "Users",
  cities: "Cities",
  places: "Places",
  media: "Media",
  popular: "Popular",
  nearest: "Your Nearest",
  weather: "Weather",
  occasions: "Occasions",
  random: "Random",
  personalized: "Personalized",
  interests: "Interests",
  "user-ratings": "User Ratings",
  "ab-recommendations": "AB Recommendations",
  "ab-summary": "AB Summary",
};

Team5UI.REASON_LABELS = {
  high_user_rating: "به خاطر امتیاز بالای کاربر",
  your_nearest: "نزدیک‌ترین پیشنهاد براساس موقعیت شما",
  ml_personalized: "پیشنهاد شخصی‌سازی‌شده با مدل ML",
  similar_topic: "پیشنهاد مشابه موضوعی",
  same_city: "پیشنهاد مشابه در همان شهر",
  similar: "پیشنهاد مشابه",
  weather_now: "پیشنهاد متناسب با فصل فعلی",
  weather_snow: "پیشنهاد برای هوای سرد و برفی",
  weather_summer: "پیشنهاد برای روزهای گرم تابستان",
  occasion_bahman22: "پیشنهاد ویژه 22 بهمن",
  occasion_nowruz: "پیشنهاد ویژه نوروز",
  occasion_yalda: "پیشنهاد ویژه شب یلدا",
  occasion_christmas: "پیشنهاد ویژه کریسمس",
  occasion_imammahdi: "پیشنهاد ویژه نیمه‌شعبان",
  occasion_chaharshanbe_soori: "پیشنهاد ویژه چهارشنبه‌سوری",
  occasion_sizdah_bedar: "پیشنهاد ویژه سیزده‌بدر",
  occasion_mehregan: "پیشنهاد ویژه مهرگان",
  random_explore: "پیشنهاد رندوم برای کاربر کنجکاو",
  comment_positive_signal: "پیشنهاد شده مبنی بر نظر شما",
};
