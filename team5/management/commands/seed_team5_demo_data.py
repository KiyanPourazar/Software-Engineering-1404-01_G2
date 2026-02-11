import random
from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from team5.models import Team5City, Team5Media, Team5MediaRating, Team5Place
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

        self._seed_catalog(provider)
        self._seed_synthetic_media(per_place=synthetic_media_per_place)
        media_ids = list(Team5Media.objects.values_list("media_id", flat=True))
        if not media_ids:
            self.stdout.write(self.style.ERROR("No media items found after seeding."))
            return

        created_users = 0
        total_ratings = 0
        all_profiles = list(DEMO_USERS) + self._build_synthetic_profiles(extra_users)

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

            sample_size = random.randint(min_ratings_per_user, min(max_ratings_per_user, len(media_ids)))
            selected_media_ids = random.sample(media_ids, sample_size)

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
                total_ratings += 1

        self._assign_media_authors_and_content()

        total_users = User.objects.count()
        total_media = Team5Media.objects.count()
        total_places = Team5Place.objects.count()
        total_ratings_db = Team5MediaRating.objects.count()

        self.stdout.write(self.style.SUCCESS(f"Users created: {created_users}"))
        self.stdout.write(self.style.SUCCESS(f"Ratings upserted: {total_ratings}"))
        self.stdout.write(
            self.style.SUCCESS(
                f"Current dataset size => users:{total_users}, cities:{Team5City.objects.count()}, places:{total_places}, media:{total_media}, ratings:{total_ratings_db}"
            )
        )
        self.stdout.write("Demo users are now available in core.User (default DB).")
        self.stdout.write("Team5 catalog+ratings are now stored in team5 database.")

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

    def _assign_media_authors_and_content(self):
        users = list(User.objects.filter(is_active=True).order_by("date_joined", "id"))
        if not users:
            self.stdout.write(self.style.WARNING("No active users found to assign as media authors."))
            return

        media_rows = list(Team5Media.objects.select_related("place__city").all())
        updated = 0
        for media in media_rows:
            user = random.choice(users)
            media.author_user_id = user.id
            media.author_display_name = self._english_display_name(user)
            media.caption = self._build_persian_caption(media.place.place_name)
            media.media_image_url = self._pick_media_image_url(media.place.place_id)
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

    def _build_persian_caption(self, place_name: str) -> str:
        templates = [
            f"امروز به {place_name} رفتم؛ فضا خیلی دلنشین بود و حس خوبی گرفتم.",
            f"نمای این بخش از {place_name} واقعاً دیدنی بود و ارزش بازدید داشت.",
            f"اگر دنبال یک تجربه متفاوت هستید، {place_name} انتخاب خیلی خوبی است.",
            f"این عکس رو از {place_name} گرفتم؛ معماری و حال و هوای اینجا فوق العاده بود.",
            f"به نظرم {place_name} از اون جاهاییه که باید حداقل یک بار از نزدیک دید.",
        ]
        return random.choice(templates)

    def _pick_media_image_url(self, place_id: str) -> str:
        # About one-third of posts are text-only and intentionally have no image.
        if random.random() < 0.34:
            return ""

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
