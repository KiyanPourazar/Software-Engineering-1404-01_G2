from __future__ import annotations

from dataclasses import dataclass

from team5.models import Team5City, Team5Media, Team5Place


@dataclass(frozen=True)
class OccasionSeedMedia:
    media_id: str
    place_id: str
    place_name: str
    city_id: str
    city_name: str
    latitude: float
    longitude: float
    title: str
    caption: str
    image_url: str


OCCASION_SEED_MEDIA: list[OccasionSeedMedia] = [
    OccasionSeedMedia(
        media_id="occasion-22bahman-azadi",
        place_id="tehran-azadi-tower",
        place_name="برج آزادی",
        city_id="tehran",
        city_name="Tehran",
        latitude=35.6997,
        longitude=51.3376,
        title="۲۲ بهمن در برج آزادی",
        caption="امروز کنار برج آزادی، حال‌وهوای همدلی و غرور ملی واقعاً خاص بود 🇮🇷✨",
        image_url="/static/team5/styles/imgs/azadi.jpg",
    ),
    OccasionSeedMedia(
        media_id="occasion-22bahman-milad",
        place_id="tehran-milad-tower",
        place_name="برج میلاد",
        city_id="tehran",
        city_name="Tehran",
        latitude=35.7446,
        longitude=51.3756,
        title="۲۲ بهمن در برج میلاد",
        caption="از بالای برج میلاد، تهران امروز یه حس وحدت و انرژی قشنگ داشت 🤍🇮🇷",
        image_url="/static/team5/styles/imgs/milad.jpg",
    ),
    OccasionSeedMedia(
        media_id="occasion-22bahman-imam-khomeini",
        place_id="tehran-imam-khomeini-mausoleum",
        place_name="آرامگاه امام خمینی",
        city_id="tehran",
        city_name="Tehran",
        latitude=35.5554,
        longitude=51.4059,
        title="۲۲ بهمن در آرامگاه امام خمینی",
        caption="حضور در این فضا توی روزهای دهه فجر، حس احترام و همبستگی عجیبی می‌ده 🇮🇷🕊️",
        image_url="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQU30ClHQmlWtWSPReMCnM2MyOuTvq0zN1n8g&s",
    ),
    OccasionSeedMedia(
        media_id="occasion-nowruz-hafezieh",
        place_id="shiraz-hafezieh",
        place_name="حافظیه",
        city_id="shiraz",
        city_name="Shiraz",
        latitude=29.6223,
        longitude=52.5570,
        title="نوروز در حافظیه",
        caption="اینجا بودن در لحظه سال نو در کنار هموطنان عزیزم از بهترین تجارب زندگیم بود 🌸🇮🇷✨",
        image_url="https://images.khabaronline.ir/images/2017/3/17-3-31-2055161.jpg",
    ),
    OccasionSeedMedia(
        media_id="occasion-nowruz-cyrus",
        place_id="shiraz-pasargadae",
        place_name="مقبره کوروش",
        city_id="shiraz",
        city_name="Shiraz",
        latitude=30.1956,
        longitude=53.1789,
        title="نوروز در مقبره کوروش",
        caption="شروع سال نو کنار آرامگاه کوروش، یه حس عمیق از ریشه و هویت به آدم می‌ده 🌱🏛️",
        image_url="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSWFq83oC4NrrgIOdLduVBjxfdRVfwT6pRipg&s",
    ),
    OccasionSeedMedia(
        media_id="occasion-christmas-mirzaye-shirazi",
        place_id="tehran-mirzaye-shirazi-street",
        place_name="خیابان میرزای شیرازی",
        city_id="tehran",
        city_name="Tehran",
        latitude=35.7213,
        longitude=51.4153,
        title="کریسمس در خیابان میرزای شیرازی",
        caption="حال‌وهوای چراغ‌ها و ویترین‌ها توی این خیابون توی روزهای کریسمس واقعاً دلنشینه 🎄✨❤️",
        image_url="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTeMKy1yekQjlcgYf30E8GtXdoGjBt-z9MWEA&s",
    ),
    OccasionSeedMedia(
        media_id="occasion-christmas-vank",
        place_id="isfahan-vank-cathedral",
        place_name="کلیسای وانک",
        city_id="isfahan",
        city_name="Isfahan",
        latitude=32.6440,
        longitude=51.6488,
        title="کریسمس در کلیسای وانک",
        caption="هوای کریسمس در کلیسای وانک پر از آرامش، نور و حس خوب کنار آدم‌هاست 🎄🕯️",
        image_url="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQOCDfFauppLvuM3yD5rDnDlQgIbEL_6i7kkA&s",
    ),
    OccasionSeedMedia(
        media_id="occasion-christmas-saint-mary",
        place_id="tehran-saint-mary-church",
        place_name="کلیسای مریم مقدس",
        city_id="tehran",
        city_name="Tehran",
        latitude=35.7098,
        longitude=51.4337,
        title="کریسمس در کلیسای مریم مقدس",
        caption="فضای گرم و صمیمی کلیسای مریم مقدس توی کریسمس واقعاً فراموش‌نشدنیه 🎄🤍",
        image_url="https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTFkFKDNYghbs8BGqYJJVvMxsBq_0ywMvOx_Q&s",
    ),
    OccasionSeedMedia(
        media_id="occasion-yalda-golestan",
        place_id="tehran-golestan-palace",
        place_name="کاخ گلستان",
        city_id="tehran",
        city_name="Tehran",
        latitude=35.6780,
        longitude=51.4214,
        title="شب یلدا در کاخ گلستان",
        caption="یلدای امسال با حافظ‌خوانی و حس خوب کنار خانواده، کنار حال‌وهوای تاریخی گلستان قشنگ‌تر شد 🍉📚",
        image_url="/static/team5/styles/imgs/golestan.jpg",
    ),
    OccasionSeedMedia(
        media_id="occasion-imammahdi-mashhad",
        place_id="mashhad-haram",
        place_name="حرم امام رضا",
        city_id="mashhad",
        city_name="Mashhad",
        latitude=36.2878,
        longitude=59.6156,
        title="جشن نیمه‌شعبان",
        caption="فضای جشن تولد امام زمان(عج) با نور و شادی و دعا، واقعاً روح آدم رو تازه می‌کنه ✨💚",
        image_url="/static/team5/styles/imgs/haram.jpg",
    ),
    OccasionSeedMedia(
        media_id="occasion-chaharshanbe-soori-naqsh",
        place_id="isfahan-naqsh-jahan",
        place_name="میدان نقش جهان",
        city_id="isfahan",
        city_name="Isfahan",
        latitude=32.6572,
        longitude=51.6776,
        title="چهارشنبه‌سوری در نقش جهان",
        caption="شور و هیجان شب‌های نزدیک نوروز اینجا واقعاً دیدنیه 🔥🎉",
        image_url="/static/team5/styles/imgs/naqhshe.jpg",
    ),
]


OCCASION_MEDIA_IDS_BY_OCCASION: dict[str, list[str]] = {
    "bahman22": [
        "occasion-22bahman-azadi",
        "occasion-22bahman-milad",
        "occasion-22bahman-imam-khomeini",
    ],
    "nowruz": [
        "occasion-nowruz-hafezieh",
        "occasion-nowruz-cyrus",
    ],
    "yalda": [
        "occasion-yalda-golestan",
    ],
    "christmas": [
        "occasion-christmas-mirzaye-shirazi",
        "occasion-christmas-vank",
        "occasion-christmas-saint-mary",
    ],
    "imammahdi": [
        "occasion-imammahdi-mashhad",
    ],
    "chaharshanbe_soori": [
        "occasion-chaharshanbe-soori-naqsh",
    ],
}


def ensure_occasion_media_seeded() -> None:
    for seed in OCCASION_SEED_MEDIA:
        Team5City.objects.update_or_create(
            city_id=seed.city_id,
            defaults={
                "city_name": seed.city_name,
                "latitude": seed.latitude,
                "longitude": seed.longitude,
            },
        )
        Team5Place.objects.update_or_create(
            place_id=seed.place_id,
            defaults={
                "city_id": seed.city_id,
                "place_name": seed.place_name,
                "latitude": seed.latitude,
                "longitude": seed.longitude,
            },
        )
        Team5Media.objects.update_or_create(
            media_id=seed.media_id,
            defaults={
                "place_id": seed.place_id,
                "title": seed.title,
                "caption": seed.caption,
                "media_image_url": seed.image_url,
            },
        )
