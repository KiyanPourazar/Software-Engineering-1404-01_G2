import random
import hashlib
from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from team5.models import Team5City, Team5Media, Team5MediaComment, Team5MediaRating, Team5Place
from team5.services.ml.text_sentiment import TextSentiment
from team5.services.mock_provider import MockProvider


User = get_user_model()


@dataclass(frozen=True)
class DemoProfile:
    first_name: str
    last_name: str
    email: str
    age: int


DEMO_USERS = [
    DemoProfile("Ali", "Rahimi", "ali.rahimi@gmail.com", 24),
    DemoProfile("Sara", "Mohammadi", "sara.mohammadi@yahoo.com", 27),
    DemoProfile("Reza", "Karimi", "reza.karimi@gmail.com", 31),
    DemoProfile("Neda", "Ahmadi", "neda.ahmadi@gmail.com", 23),
    DemoProfile("Hamed", "Jafari", "hamed.jafari@yahoo.com", 29),
    DemoProfile("Maryam", "Nazari", "maryam.nazari@gmail.com", 26),
    DemoProfile("Pouya", "Taghavi", "pouya.taghavi@gmail.com", 33),
    DemoProfile("Zahra", "Ebrahimi", "zahra.ebrahimi@yahoo.com", 22),
    DemoProfile("Arman", "Soleimani", "arman.soleimani@gmail.com", 28),
    DemoProfile("Shiva", "Kiani", "shiva.kiani@gmail.com", 30),
    DemoProfile("Milad", "Hosseini", "milad.hosseini@yahoo.com", 25),
    DemoProfile("Yasmin", "Darvishi", "yasmin.darvishi@gmail.com", 24),
    DemoProfile("Kian", "Shahbazi", "kian.shahbazi@gmail.com", 21),
    DemoProfile("Parisa", "Farhadi", "parisa.farhadi@yahoo.com", 32),
    DemoProfile("Amin", "Rostami", "amin.rostami@gmail.com", 27),
]


class Command(BaseCommand):
    help = "Seed catalog data and realistic demo users/ratings in Team5 databases."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default="Pass1234!Strong",
            help="Password used for users created by this seed command.",
        )
        parser.add_argument(
            "--clear-ratings",
            action="store_true",
            help="Delete existing Team5 ratings before seeding.",
        )
        parser.add_argument(
            "--clear-catalog",
            action="store_true",
            help="Delete city/place/media catalog and recreate it from mock files.",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=1404,
            help="Random seed for deterministic rating generation.",
        )
        parser.add_argument(
            "--extra-users",
            type=int,
            default=120,
            help="Additional synthetic users to create on top of predefined demo users.",
        )
        parser.add_argument(
            "--synthetic-media-per-place",
            type=int,
            default=8,
            help="How many extra media items should be created per place.",
        )
        parser.add_argument(
            "--min-ratings-per-user",
            type=int,
            default=25,
            help="Minimum ratings to generate for each user.",
        )
        parser.add_argument(
            "--max-ratings-per-user",
            type=int,
            default=60,
            help="Maximum ratings to generate for each user.",
        )
        parser.add_argument(
            "--clear-comments",
            action="store_true",
            help="Delete existing Team5 comments before seeding.",
        )

    def handle(self, *args, **options):
        password = options["password"]
        random.seed(options["seed"])
        provider = MockProvider()
        extra_users = max(0, int(options["extra_users"]))
        synthetic_media_per_place = max(0, int(options["synthetic_media_per_place"]))
        min_ratings_per_user = max(1, int(options["min_ratings_per_user"]))
        max_ratings_per_user = max(min_ratings_per_user, int(options["max_ratings_per_user"]))
        if options["clear_catalog"]:
            Team5Media.objects.all().delete()
            Team5Place.objects.all().delete()
            Team5City.objects.all().delete()
            self.stdout.write(self.style.WARNING("Deleted existing Team5 catalog records."))

        if options["clear_ratings"]:
            deleted_count, _ = Team5MediaRating.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Deleted existing ratings: {deleted_count}"))
        if options["clear_comments"]:
            deleted_comments, _ = Team5MediaComment.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Deleted existing comments: {deleted_comments}"))

        self._seed_catalog(provider)
        self._seed_synthetic_media(per_place=synthetic_media_per_place)
        media_ids = list(Team5Media.objects.values_list("media_id", flat=True))
        if not media_ids:
            self.stdout.write(self.style.ERROR("No media items found after seeding."))
            return

        created_users = 0
        total_ratings = 0
        all_profiles = list(DEMO_USERS) + self._build_synthetic_profiles(extra_users)
        seeded_user_ids: set[str] = set()

        for profile in all_profiles:
            user, created = User.objects.get_or_create(
                email=profile.email,
                defaults={
                    "first_name": profile.first_name,
                    "last_name": profile.last_name,
                    "age": profile.age,
                    "is_active": True,
                },
            )

            if created:
                user.set_password(password)
                user.save()
                created_users += 1

            seeded_user_ids.add(str(user.id))
            total_ratings += self._upsert_random_ratings_for_user(
                user=user,
                media_ids=media_ids,
                min_ratings_per_user=min_ratings_per_user,
                max_ratings_per_user=max_ratings_per_user,
            )

        # Ensure every active user in the system has enough ratings.
        # This prevents users outside the demo/synthetic profile list from staying unrated.
        active_users = User.objects.filter(is_active=True).only("id", "email")
        for user in active_users:
            if str(user.id) in seeded_user_ids:
                continue
            total_ratings += self._upsert_random_ratings_for_user(
                user=user,
                media_ids=media_ids,
                min_ratings_per_user=min_ratings_per_user,
                max_ratings_per_user=max_ratings_per_user,
            )

        self._assign_media_authors_and_content()
        comments_upserted = self._seed_media_comments()

        total_users = User.objects.count()
        total_media = Team5Media.objects.count()
        total_places = Team5Place.objects.count()
        total_ratings_db = Team5MediaRating.objects.count()
        total_comments_db = Team5MediaComment.objects.count()

        self.stdout.write(self.style.SUCCESS(f"Users created: {created_users}"))
        self.stdout.write(self.style.SUCCESS(f"Ratings upserted: {total_ratings}"))
        self.stdout.write(self.style.SUCCESS(f"Comments upserted: {comments_upserted}"))
        self.stdout.write(
            self.style.SUCCESS(
                f"Current dataset size => users:{total_users}, cities:{Team5City.objects.count()}, places:{total_places}, media:{total_media}, ratings:{total_ratings_db}, comments:{total_comments_db}"
            )
        )
        self.stdout.write("Demo users are now available in core.User (default DB).")
        self.stdout.write("Team5 catalog+ratings are now stored in team5 database.")

    def _upsert_random_ratings_for_user(
        self,
        *,
        user,
        media_ids: list[str],
        min_ratings_per_user: int,
        max_ratings_per_user: int,
    ) -> int:
        if not media_ids:
            return 0
        sample_size = random.randint(min_ratings_per_user, min(max_ratings_per_user, len(media_ids)))
        selected_media_ids = random.sample(media_ids, sample_size)
        upserted = 0
        for media_id in selected_media_ids:
            rate = random.choice([2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0])
            Team5MediaRating.objects.update_or_create(
                user_id=user.id,
                media_id=media_id,
                defaults={
                    "user_email": user.email,
                    "rate": rate,
                    "liked": rate >= 4.0,
                },
            )
            upserted += 1
        return upserted

    def _seed_catalog(self, provider: MockProvider):
        for city in provider.get_cities():
            Team5City.objects.update_or_create(
                city_id=city["cityId"],
                defaults={
                    "city_name": city["cityName"],
                    "latitude": float(city["coordinates"][0]),
                    "longitude": float(city["coordinates"][1]),
                },
            )

        for place in provider.get_all_places():
            Team5Place.objects.update_or_create(
                place_id=place["placeId"],
                defaults={
                    "city_id": place["cityId"],
                    "place_name": place["placeName"],
                    "latitude": float(place["coordinates"][0]),
                    "longitude": float(place["coordinates"][1]),
                },
            )

        for media in provider.get_media():
            Team5Media.objects.update_or_create(
                media_id=media["mediaId"],
                defaults={
                    "place_id": media["placeId"],
                    "title": media["title"],
                    "caption": media["caption"],
                },
            )

    def _seed_synthetic_media(self, *, per_place: int):
        if per_place <= 0:
            return
        adjectives = ["Golden", "Night", "Aerial", "Hidden", "Historic", "Local", "Peaceful", "Vibrant"]
        themes = ["walkthrough", "view", "moments", "stories", "journey", "highlights", "experience"]

        created = 0
        for place in Team5Place.objects.all():
            base_slug = place.place_id.replace("_", "-")
            for idx in range(1, per_place + 1):
                media_id = f"{base_slug}-syn-{idx:03d}"
                adjective = random.choice(adjectives)
                theme = random.choice(themes)
                title = f"{adjective} {place.place_name} {theme} #{idx}"
                caption = f"Synthetic sample generated for scalable recommendation testing at {place.place_name}."
                _, was_created = Team5Media.objects.update_or_create(
                    media_id=media_id,
                    defaults={
                        "place_id": place.place_id,
                        "title": title,
                        "caption": caption,
                    },
                )
                created += 1 if was_created else 0
        self.stdout.write(self.style.NOTICE(f"Synthetic media created: {created}"))

    def _seed_media_comments(self) -> int:
        users = list(User.objects.filter(is_active=True).only("id", "email"))
        media_rows = list(Team5Media.objects.select_related("place").all().only("media_id", "place_id"))
        if not users or not media_rows:
            return 0

        sentiment = TextSentiment()
        comment_targets = self._build_comment_targets(len(media_rows))
        random.shuffle(media_rows)

        upserted = 0
        for idx, media in enumerate(media_rows):
            target_comments = comment_targets[idx] if idx < len(comment_targets) else 0
            if target_comments <= 0:
                continue
            media_id = media.media_id
            place_id = str(media.place_id)
            selected_users = random.sample(users, min(target_comments, len(users)))
            positive_count = target_comments // 2
            negative_count = target_comments - positive_count
            sentiment_plan = ["positive"] * positive_count + ["negative"] * negative_count
            random.shuffle(sentiment_plan)

            for commenter, sentiment_label in zip(selected_users, sentiment_plan):
                body = self._build_realistic_comment(
                    place_id=place_id,
                    sentiment_label=sentiment_label,
                )
                score = float(sentiment.sentiment(body))
                final_label = "neutral"
                if score > 0.05:
                    final_label = "positive"
                elif score < -0.05:
                    final_label = "negative"
                else:
                    # Keep intended distribution even when model returns near-zero.
                    final_label = sentiment_label
                    score = 0.4 if sentiment_label == "positive" else -0.4

                Team5MediaComment.objects.update_or_create(
                    user_id=commenter.id,
                    media_id=media_id,
                    defaults={
                        "user_email": commenter.email,
                        "body": body,
                        "sentiment_score": score,
                        "sentiment_label": final_label,
                    },
                )
                upserted += 1
        return upserted

    def _build_realistic_comment(self, *, place_id: str, sentiment_label: str) -> str:
        comments_by_place = {
            "tonkabon-abbas-abad-complex": {
                "positive": [
                    "فضای جنگلی و هوای مرطوبش واقعا حال‌وهوای شمال اصیل رو داره. وقتی مه میاد پایین، منظره قلعه روی آب افسانه‌ای میشه 🌿🌫️",
                    "این نقطه از عباس‌آباد حس سفر واقعی به دل طبیعت میده؛ سکوت و مهش فوق‌العاده بود.",
                ],
                "negative": [
                    "مسیر دسترسی یه‌کم نامشخصه و وقتی بارون بیاد زمین خیلی گلی میشه.",
                    "مکان قشنگه ولی راه رسیدنش مخصوصا تو هوای بد سخت و خسته‌کننده میشه.",
                ],
            },
            "tabriz-arg": {
                "positive": [
                    "عظمت دیوارهای ارگ تبریز واقعا آدمو می‌بره تو دل تاریخ؛ نور عصر برای عکاسی عالیه 📸",
                    "این بنا حس تاریخی قوی‌ای داره و از نزدیک خیلی تاثیرگذارتره.",
                ],
                "negative": [
                    "اطرافش امکانات و توضیح تاریخی زیادی نداره؛ بدون راهنما بعضی چیزها نامفهومه.",
                    "خود بنا جذابه ولی اطلاعات بازدید برای درک بهتر کم بود.",
                ],
            },
            "tehran-azadi-tower": {
                "positive": [
                    "برج آزادی از نزدیک حس خاصی داره، مخصوصا شب‌ها که نورپردازی میشه ✨",
                    "واقعا نماد تهرانه و دیدنش برای اولین بار خیلی جذابه.",
                ],
                "negative": [
                    "اطراف برج خیلی شلوغه و بعضی وقتا فضای سبزش اون تمیزی که انتظار داری رو نداره.",
                    "ترافیک اطرافش تجربه بازدید رو کمی ضعیف می‌کنه.",
                ],
            },
            "tonkabon-dohezar-road": {
                "positive": [
                    "جاده دوهزار از اون مسیرهاییه که خود راه از مقصد قشنگ‌تره؛ هر پیچش یه قاب عکسه.",
                    "منظره مسیر عالیه و حس سفر واقعی میده 🚗🌲",
                ],
                "negative": [
                    "پیچ‌های تندش برای راننده کم‌تجربه می‌تونه استرس‌زا باشه.",
                    "راه خیلی قشنگه ولی رانندگی تو بعضی قسمت‌ها واقعا احتیاط می‌خواد.",
                ],
            },
            "tehran-golestan-palace": {
                "positive": [
                    "ترکیب معماری ایرانی و اروپایی توی کاخ گلستان خیلی چشم‌نوازه؛ کاشی‌کاری‌ها واقعا فوق‌العاده‌ست.",
                    "برای علاقه‌مندان تاریخ و هنر یکی از بهترین انتخاب‌هاست.",
                ],
                "negative": [
                    "بلیت بخش‌های مختلف جداست و برای بازدید کامل هزینه بالا میره.",
                    "بازدید کاملش نسبت به چیزی که فکر می‌کردم گرون‌تر دراومد.",
                ],
            },
            "gorgan-gonbad-qabus": {
                "positive": [
                    "سادگی بنا در عین عظمتش خیلی تاثیرگذاره؛ حس می‌کنی وسط تاریخ ایستادی.",
                    "گنبد قابوس از اون جاهاییه که بدون شلوغی هم عمیق اثر می‌ذاره.",
                ],
                "negative": [
                    "اطرافش خیلی خلوت و ساده‌ست و جذابیت جانبی زیادی نداره.",
                    "مکان خود بنا عالیه ولی امکانات اطرافش محدود بود.",
                ],
            },
            "kish-greek-ship": {
                "positive": [
                    "غروب کنار کشتی یونانی واقعا دیدنیه؛ آسمون نارنجی پشت کشتی خیلی خاصه 🌅",
                    "برای عکاسی هنگام غروب یکی از بهترین لوکیشن‌های کیشه.",
                ],
                "negative": [
                    "خود کشتی قابل بازدید نیست و بعد از یک بار دیدن شاید جذابیتش کمتر بشه.",
                    "فقط از بیرون میشه دید و تنوع تجربه‌اش کمه.",
                ],
            },
            "shiraz-hafezieh": {
                "positive": [
                    "حال‌وهوای شاعرانه حافظیه واقعا آرامش‌بخشه؛ شب‌ها با نور ملایم دلنشین‌تر هم میشه.",
                    "فضای فرهنگی و آرام حافظیه حس خیلی خوبی میده 💙",
                ],
                "negative": [
                    "بعضی وقتا خیلی شلوغ میشه و اون حس خلوت شاعرانه از بین میره.",
                    "توی ساعات اوج بازدید، ازدحام لذت فضا رو کم می‌کنه.",
                ],
            },
            "kish-harireh-city": {
                "positive": [
                    "قدم زدن بین بقایای شهر حریره حس کشف کردن داره و جذابه.",
                    "برای دوست‌داران تاریخ باستانی تجربه خوبی بود.",
                ],
                "negative": [
                    "تابلوهای توضیحی کم هست و بدون اطلاعات قبلی بعضی بخش‌ها مبهم می‌مونه.",
                    "به نظرم نیاز به راهنمای بهتر برای درک جزئیات تاریخی داره.",
                ],
            },
            "astara-heyran-pass": {
                "positive": [
                    "مه و کوه و جاده پیچ‌درپیچ حیران فوق‌العاده‌ست؛ یکی از زیباترین مسیرهای شماله 🌫️⛰️",
                    "منظره‌های مسیر حیران واقعا چشم‌نواز و فراموش‌نشدنیه.",
                ],
                "negative": [
                    "آخر هفته‌ها ترافیکش خیلی سنگینه و اعصاب‌خوره.",
                    "شلوغی جاده تو تعطیلات لذت مسیر رو کم می‌کنه.",
                ],
            },
            "bandarabbas-hindu-temple": {
                "positive": [
                    "یه معماری متفاوت وسط جنوب ایران؛ واقعا خاص و غیرمنتظره بود.",
                    "ترکیب فرهنگی این بنا جذابه و ارزش دیدن داره.",
                ],
                "negative": [
                    "نگهداری بنا می‌تونست بهتر باشه.",
                    "بعضی جزئیات نیاز به مرمت و رسیدگی بیشتری داره.",
                ],
            },
            "mashhad-haram": {
                "positive": [
                    "عظمت و نظم مجموعه چشمگیره و فضای معنوی خیلی قویه.",
                    "هم از نظر معماری هم حس معنوی، تجربه خیلی خوبی بود.",
                ],
                "negative": [
                    "تو مناسبت‌های شلوغ پیدا کردن جای خلوت تقریبا غیرممکن میشه.",
                    "تراکم جمعیت در زمان‌های خاص زیاد و خسته‌کننده‌ست.",
                ],
            },
            "gorgan-khalid-nabi": {
                "positive": [
                    "فضای رازآلود و منظره تپه‌ها خیلی خاصه، مخصوصا نزدیک طلوع 🌄",
                    "لوکیشن متفاوتیه و حس متفاوتی نسبت به بقیه جاها میده.",
                ],
                "negative": [
                    "مسیر دسترسی خاکیه و تو هوای بد سخت میشه رفت.",
                    "تو شرایط جوی بد مسیرش واقعا اذیت‌کننده میشه.",
                ],
            },
            "bandarabbas-kolah-farangi": {
                "positive": [
                    "معماری ساده ولی ظریفه و کنار دریا حال‌وهوای خوبی داره.",
                    "برای یک بازدید کوتاه و آرامش‌بخش گزینه خوبیه.",
                ],
                "negative": [
                    "بنا کوچیکه و بازدیدش خیلی طول نمی‌کشه.",
                    "تنوع بازدیدی محدوده و سریع تموم میشه.",
                ],
            },
            "qeshm-laft-historical-port": {
                "positive": [
                    "بادگیرها و کوچه‌های قدیمی لافت حس جنوب اصیل رو منتقل می‌کنن 😍",
                    "هویت تاریخی محله خیلی خوب حفظ شده و دیدنش لذت‌بخشه.",
                ],
                "negative": [
                    "تو گرمای شدید بازدیدش واقعا سخت میشه.",
                    "شرایط آب‌وهوایی گرم ممکنه تجربه بازدید رو خسته‌کننده کنه.",
                ],
            },
            "tehran-milad-tower": {
                "positive": [
                    "چشم‌انداز ۳۶۰ درجه تهران خیلی جذابه، مخصوصا شب‌ها.",
                    "از بالای برج میلاد منظره شهر واقعا تماشاییه 🌃",
                ],
                "negative": [
                    "قیمت بلیت طبقات بالا برای بعضی‌ها گرونه.",
                    "هزینه تجربه کامل بازدید نسبتاً بالاست.",
                ],
            },
            "isfahan-naqsh-jahan": {
                "positive": [
                    "میدان نقش جهان شاهکاره؛ هر طرفش یک اثر تاریخی ارزشمنده.",
                    "از نظر معماری و فضای شهری یکی از بهترین تجربه‌های سفرم بود.",
                ],
                "negative": [
                    "فروشنده‌های اطراف بعضی وقتا بیش از حد اصرار می‌کنن.",
                    "شلوغی اطراف میدان در ساعات پیک کمی آزاردهنده‌ست.",
                ],
            },
            "shiraz-pasargadae": {
                "positive": [
                    "سادگی آرامگاه کوروش خیلی تاثیرگذاره و حس احترام ایجاد می‌کنه.",
                    "فضای پاسارگاد برای دوست‌داران تاریخ بسیار ارزشمنده.",
                ],
                "negative": [
                    "تو تابستون هوا واقعا طاقت‌فرسا و گرم میشه.",
                    "در ساعات گرم روز بازدید واقعا سخت میشه.",
                ],
            },
            "qeshm-portuguese-castle": {
                "positive": [
                    "رنگ سرخ دیوارها کنار آبی دریا تضاد خیلی زیبایی ایجاد می‌کنه.",
                    "لوکیشن بصری قوی‌ای داره و برای عکاسی خوبه.",
                ],
                "negative": [
                    "بعضی بخش‌ها تخریب شده و نیاز به مرمت جدی داره.",
                    "اگه مرمت بهتری انجام بشه تجربه بازدید خیلی بهتر میشه.",
                ],
            },
            "ardabil-sheikh-safi": {
                "positive": [
                    "کاشی‌کاری‌ها و فضای عرفانی مجموعه واقعا تاثیرگذاره.",
                    "از نظر هنری و معنوی یکی از جذاب‌ترین مکان‌های اردبیله.",
                ],
                "negative": [
                    "بعضی بخش‌ها توضیح تاریخی کافی ندارن.",
                    "برای فهم بهتر مجموعه، اطلاعات راهنما می‌تونه کامل‌تر باشه.",
                ],
            },
            "isfahan-si-o-se-pol": {
                "positive": [
                    "شب‌ها وقتی مردم زیر طاق‌ها آواز می‌خونن حس زنده بودن میده 🎶",
                    "فضای پل به‌خصوص عصر و شب خیلی دلنشین و خاطره‌سازه.",
                ],
                "negative": [
                    "وقتی زاینده‌رود خشکه جذابیت پل تقریبا نصف میشه.",
                    "بی‌آبی رود واقعاً روی تجربه بازدید تاثیر منفی می‌ذاره.",
                ],
            },
            "tehran-imam-khomeini-mausoleum": {
                "positive": [
                    "وسعت و معماری مجموعه خیلی بزرگ و چشمگیره.",
                    "برای بازدید رسمی و مناسبتی، فضا بسیار منظم و تاثیرگذاره.",
                ],
                "negative": [
                    "فاصله‌اش از مرکز شهر زیاده و زمان رفت‌وآمد می‌بره.",
                    "برای دسترسی بدون ماشین شخصی کمی زمان‌بره.",
                ],
            },
            "tehran-mirzaye-shirazi-street": {
                "positive": [
                    "دسترسی خوب به مراکز اداری و تجاری داره و موقعیتش کاربردیه.",
                    "برای کارهای روزمره و اداری خیابون نسبتا کار راه‌اندازه.",
                ],
                "negative": [
                    "تو ساعات کاری خیلی شلوغ و پرترافیکه.",
                    "پارکینگ و ترافیک توی تایم اداری واقعا دردسر میشه.",
                ],
            },
            "tehran-saint-mary-church": {
                "positive": [
                    "فضای آرام و معماری داخلی ساده ولی دلنشینه 🤍",
                    "برای یک بازدید کوتاه فرهنگی جای خوبی و آرامیه.",
                ],
                "negative": [
                    "ساعات بازدیدش محدوده و باید هماهنگ رفت.",
                    "محدودیت زمانی بازدید باعث میشه نتونی هر موقع خواستی ببینی.",
                ],
            },
            "isfahan-vank-cathedral": {
                "positive": [
                    "نقاشی‌های دیواری داخل کلیسا شگفت‌انگیزه؛ تلفیق فرهنگی خیلی خاصی داره.",
                    "کلیسای وانک از نظر هنر داخلی واقعا چشم‌گیره ✨",
                ],
                "negative": [
                    "تو تعطیلات خیلی شلوغ میشه و باید تو صف وایسی.",
                    "در روزهای پیک، ازدحام جمعیت زیاد و زمان انتظار طولانیه.",
                ],
            },
        }

        fallback = {
            "positive": [
                "تجربه خیلی خوبی بود و این مکان حس مثبتی بهم داد.",
                "از این بازدید لذت بردم و ارزش یک بار دیدن رو داشت 😊",
            ],
            "negative": [
                "برای من خیلی رضایت‌بخش نبود و انتظار بیشتری داشتم.",
                "بد نبود ولی چالش‌هایی داشت که تجربه‌ام رو ضعیف کرد.",
            ],
        }

        place_templates = comments_by_place.get(place_id, fallback)
        templates = place_templates.get(sentiment_label, fallback[sentiment_label])
        base = random.choice(templates)

        # Add mild human-like variation so comments don't look template-generated.
        endings = {
            "positive": ["", " پیشنهاد می‌کنم حتما ببینید.", " اگه اهل سفرین، از دستش ندین."],
            "negative": ["", " بهتره با آمادگی بیشتری برید.", " امیدوارم رسیدگی بیشتری بهش بشه."],
        }
        return f"{base}{random.choice(endings[sentiment_label])}"

    def _build_comment_targets(self, media_count: int) -> list[int]:
        if media_count <= 0:
            return []

        # Requested distribution:
        # 10% -> 0 comment, 30% -> 8 comments, 20% -> 11 comments,
        # 30% -> 14 comments, 10% -> 20 comments.
        bucket0 = int(round(media_count * 0.10))
        bucket8 = int(round(media_count * 0.30))
        bucket11 = int(round(media_count * 0.20))
        bucket14 = int(round(media_count * 0.30))
        used = bucket0 + bucket8 + bucket11 + bucket14
        bucket20 = max(0, media_count - used)

        targets = (
            [0] * bucket0
            + [8] * bucket8
            + [11] * bucket11
            + [14] * bucket14
            + [20] * bucket20
        )
        # Adjust in case rounding drifted above total.
        return targets[:media_count]

    def _assign_media_authors_and_content(self):
        users = list(User.objects.filter(is_active=True).order_by("date_joined", "id"))
        if not users:
            self.stdout.write(self.style.WARNING("No active users found to assign as media authors."))
            return

        media_rows = list(Team5Media.objects.select_related("place__city").all())
        updated = 0
        for media in media_rows:
            user = random.choice(users)
            text_only = self._is_text_only_media(media.media_id)
            image_url = self._pick_media_image_url(
                media.place.place_id,
                existing_url=media.media_image_url,
                force_text_only=text_only,
            )
            media.author_user_id = user.id
            media.author_display_name = self._english_display_name(user)
            media.caption = self._build_persian_caption(
                place_name=media.place.place_name,
                city_id=media.place.city.city_id,
                has_image=bool(image_url),
            )
            media.media_image_url = image_url
            media.save(
                update_fields=[
                    "author_user_id",
                    "author_display_name",
                    "caption",
                    "media_image_url",
                ]
            )
            updated += 1
        self.stdout.write(self.style.SUCCESS(f"Media posts enriched with author/image/caption: {updated}"))

    def _english_display_name(self, user) -> str:
        first_name = (user.first_name or "").strip()
        last_name = (user.last_name or "").strip()
        full_name = f"{first_name} {last_name}".strip()
        if full_name:
            return full_name
        local_part = (user.email or "").split("@")[0].replace(".", " ").replace("_", " ").strip()
        return local_part.title() if local_part else "Team5 Traveler"

    def _build_persian_caption(self, *, place_name: str, city_id: str, has_image: bool) -> str:
        south_city_ids = {"kish", "qeshm", "bandarabbas"}
        north_city_ids = {"tonkabon", "astara", "gorgan"}
        cold_city_ids = {"ardabil", "tabriz", "astara"}

        generic_templates = [
            f"امروز یه سر به {place_name} زدم و واقعاً حال‌وهوای خاصی داشت 😍",
            f"{place_name} از اون جاهاییه که هر بار بری یه حس تازه می‌گیری ✨",
            f"این گوشه از {place_name} رو خیلی دوست داشتم؛ ترکیب تاریخ و حس سفرش فوق‌العاده‌ست 📍",
        ]
        south_templates = [
            f"{place_name} با این گرمای جنوبی واقعاً آتیشیه 🔥😅 ما که اینجا زندگی می‌کنیم بعضی روزها می‌گیم رسماً جهنمه، ولی بازم غروباش یه آرامش خاص داره 🌅",
            f"از سرمای شهر خودمون خسته شده بودیم، اومدیم {place_name} و الان داریم از هوای گرم و آفتابی‌اش لذت می‌بریم ☀️🌴",
            f"هوای {place_name} گرمه ولی حس دریا و حال‌وهوای جنوب یه چیز دیگه‌ست 🌊🔥",
        ]
        north_templates = [
            f"{place_name} با بارون‌های قشنگش واقعاً دل آدمو می‌بره ☔🌿 بوی نم و صدای بارون اینجا فوق‌العاده‌ست.",
            f"هوای {place_name} یه وقتایی رطوبتش اذیت می‌کنه، ولی منظره‌های سبز و حال خوبش نمی‌ذاره دل بکنی 🌧️🍃",
            f"{place_name} یعنی ترکیب دریا، مه، بارون و آرامش شمالی 🌊🌫️",
        ]
        cold_templates = [
            f"هوای {place_name} واقعاً سرده ❄️🧣 ولی برای عاشقای سرما یه بهشته.",
            f"اینجا تو {place_name} حتی تابستونم هوا اونقدر خوبه که خیلی وقتا کولر روشن نمی‌کنن 🌬️😎",
            f"{place_name} برای فرار از گرما عالیه؛ خنک، آروم و پر از حال خوب 🍃",
        ]

        if city_id in south_city_ids:
            selected = random.choice(south_templates)
        elif city_id in north_city_ids:
            selected = random.choice(north_templates)
        elif city_id in cold_city_ids:
            selected = random.choice(cold_templates)
        else:
            selected = random.choice(generic_templates)

        if has_image:
            return selected

        # Longer text for text-only posts to compensate missing image.
        extensions = [
            f"بدون عکس گذاشتم چون بعضی حس‌ها واقعاً توی قاب جا نمی‌شن؛ باید از نزدیک تجربه‌شون کرد 📝",
            f"اگه قصد سفر داری، برای {place_name} وقت کافی بذار؛ هم مسیرش دیدنیه هم حال‌وهوای خود مکان.",
            f"من این پست رو متنی گذاشتم تا جزئیات بیشتری بنویسم؛ از حس فضا تا هوای همون لحظه، همه‌چیز متفاوت بود.",
        ]
        return f"{selected} {random.choice(extensions)}"

    def _pick_media_image_url(self, place_id: str, *, existing_url: str = "", force_text_only: bool = False) -> str:
        if force_text_only:
            return ""

        if (existing_url or "").strip():
            return existing_url.strip()

        image_map = {
            "tehran-milad-tower": "/static/team5/styles/imgs/milad.jpg",
            "tehran-azadi-tower": "/static/team5/styles/imgs/azadi.jpg",
            "tehran-golestan-palace": "/static/team5/styles/imgs/golestan.jpg",
            "isfahan-naqsh-jahan": "/static/team5/styles/imgs/naqhshe.jpg",
            "isfahan-si-o-se-pol": "/static/team5/styles/imgs/siosepol.jpg",
            "shiraz-hafezieh": "/static/team5/styles/imgs/hafez.jpg",
            "shiraz-pasargadae": "/static/team5/styles/imgs/pasargad.jpg",
            "tabriz-arg": "/static/team5/styles/imgs/elgoli.jpg",
            "mashhad-haram": "/static/team5/styles/imgs/haram.jpg",
        }
        return image_map.get(place_id, "")

    def _is_text_only_media(self, media_id: str) -> bool:
        # Keep a deterministic subset (~20%) text-only.
        digest = hashlib.md5(str(media_id).encode("utf-8")).hexdigest()
        return int(digest[-2:], 16) % 5 == 0

    def _build_synthetic_profiles(self, count: int) -> list[DemoProfile]:
        if count <= 0:
            return []
        first_names = [
            "Aria",
            "Nima",
            "Mina",
            "Sina",
            "Parya",
            "Raha",
            "Taha",
            "Sahar",
            "Ava",
            "Navid",
        ]
        last_names = [
            "Jalali",
            "Karimi",
            "Ahmadi",
            "Etemadi",
            "Shirazi",
            "Ansari",
            "Khosravi",
            "Mehrabi",
            "Yeganeh",
            "Ranjbar",
        ]
        profiles: list[DemoProfile] = []
        for idx in range(1, count + 1):
            first_name = random.choice(first_names)
            last_name = random.choice(last_names)
            email = f"team5.synthetic{idx:04d}@example.com"
            age = random.randint(18, 55)
            profiles.append(DemoProfile(first_name, last_name, email, age))
        return profiles
