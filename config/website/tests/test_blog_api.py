from datetime import timedelta
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITestCase

from website.models import BlogPost


class PublicBlogAPITests(APITestCase):

    @classmethod
    def setUpTestData(cls):
        now = timezone.now()

        cls.old_post = BlogPost.objects.create(
            title="First Teamboard article",
            slug="first-teamboard-article",
            excerpt="Our first article.",
            content="# First article\n\nWelcome to Teamboard.",
            status=BlogPost.Status.PUBLISHED,
            published_at=now - timedelta(days=3),
        )

        cls.new_post = BlogPost.objects.create(
            title="Latest Teamboard update",
            slug="latest-teamboard-update",
            excerpt="Recent product improvements.",
            content="# Latest update\n\nNew features.",
            status=BlogPost.Status.PUBLISHED,
            published_at=now - timedelta(days=1),
        )

        cls.draft_post = BlogPost.objects.create(
            title="Internal draft",
            slug="internal-draft",
            content="Private unpublished content.",
            status=BlogPost.Status.DRAFT,
        )

        cls.future_post = BlogPost.objects.create(
            title="Scheduled release",
            slug="scheduled-release",
            content="Not available yet.",
            status=BlogPost.Status.PUBLISHED,
            published_at=now + timedelta(days=10),
        )

        cls.list_url = reverse(
            "website_api_v1:blog_list"
        )

    def detail_url(self, slug):
        return reverse(
            "website_api_v1:blog_detail",
            kwargs={"slug": slug},
        )

    def test_anonymous_visitor_can_list_published_posts(self):
        response = self.client.get(self.list_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(response.data["count"], 2)

        posts = response.data["results"]

        self.assertEqual(
            [post["slug"] for post in posts],
            [
                self.new_post.slug,
                self.old_post.slug,
            ],
        )

        self.assertNotIn("content", posts[0])
        self.assertNotIn("status", posts[0])

    def test_published_article_detail_contains_content(self):
        response = self.client.get(
            self.detail_url(self.new_post.slug)
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["title"],
            self.new_post.title,
        )

        self.assertEqual(
            response.data["content"],
            self.new_post.content,
        )

        self.assertNotIn("status", response.data)

    def test_persian_listing_only_returns_published_translations(self):
        for post in (self.new_post, self.draft_post, self.future_post):
            BlogPost.objects.filter(pk=post.pk).update(
                title_fa="کار تیمی بهتر",
                excerpt_fa="ایده‌هایی برای همکاری بهتر.",
                content_fa="## روالی روشن‌تر",
            )
        BlogPost.objects.filter(pk=self.old_post.pk).update(title_fa="ترجمه ناتمام")

        listing = self.client.get(self.list_url, {"lang": "fa"})
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual(listing.data["count"], 1)
        article = listing.data["results"][0]
        self.assertEqual(article["slug"], self.new_post.slug)
        self.assertEqual(article["title"], "کار تیمی بهتر")
        self.assertEqual(article["excerpt"], "ایده‌هایی برای همکاری بهتر.")
        self.assertTrue(article["has_persian_translation"])
        self.assertNotIn("content", article)

        detail = self.client.get(self.detail_url(self.new_post.slug), {"lang": "fa"})
        self.assertEqual(detail.data["content"], "## روالی روشن‌تر")
        original = self.client.get(self.detail_url(self.new_post.slug))
        self.assertEqual(original.data["title"], self.new_post.title)
        self.assertTrue(original.data["has_persian_translation"])
        fallback = self.client.get(self.detail_url(self.old_post.slug), {"lang": "fa"})
        self.assertEqual(fallback.data["title"], self.old_post.title)
        self.assertFalse(fallback.data["has_persian_translation"])
        for post in (self.draft_post, self.future_post):
            self.assertEqual(self.client.get(self.detail_url(post.slug), {"lang": "fa"}).status_code, status.HTTP_404_NOT_FOUND)

    def test_drafts_and_future_posts_are_never_public(self):
        list_response = self.client.get(self.list_url)

        self.assertEqual(
            list_response.status_code,
            status.HTTP_200_OK,
        )

        listed_slugs = {
            post["slug"]
            for post in list_response.data["results"]
        }

        self.assertNotIn(
            self.draft_post.slug,
            listed_slugs,
        )

        self.assertNotIn(
            self.future_post.slug,
            listed_slugs,
        )

        for post in (self.draft_post, self.future_post):
            with self.subTest(slug=post.slug):
                response = self.client.get(
                    self.detail_url(post.slug)
                )

                self.assertEqual(
                    response.status_code,
                    status.HTTP_404_NOT_FOUND,
                )

    def test_blog_is_accessible_without_authentication(self):
        self.client.credentials()

        list_response = self.client.get(self.list_url)

        detail_response = self.client.get(
            self.detail_url(self.old_post.slug)
        )

        self.assertEqual(
            list_response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            detail_response.status_code,
            status.HTTP_200_OK,
        )

    def test_blog_list_is_paginated_and_capped(self):
        now = timezone.now()

        BlogPost.objects.bulk_create(
            [
                BlogPost(
                    title=f"Article {index}",
                    slug=f"article-{index}",
                    excerpt="An example article.",
                    content="Article content.",
                    status=BlogPost.Status.PUBLISHED,
                    published_at=now - timedelta(minutes=index + 1),
                )
                for index in range(55)
            ]
        )

        response = self.client.get(
            self.list_url,
            {"page_size": 2},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(response.data["count"], 57)

        self.assertEqual(
            len(response.data["results"]),
            2,
        )

        self.assertIsNotNone(response.data["next"])

        capped_response = self.client.get(
            self.list_url,
            {"page_size": 500},
        )

        self.assertEqual(
            capped_response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            len(capped_response.data["results"]),
            50,
        )

    def test_blog_read_queries_are_constant_for_each_language(self):
        BlogPost.objects.filter(status=BlogPost.Status.PUBLISHED).update(
            title_fa="عنوان فارسی", content_fa="متن فارسی " * 1000,
        )
        for lang in ("en", "fa"):
            with self.subTest(lang=lang):
                with self.assertNumQueries(2) as listing_queries:
                    listing = self.client.get(self.list_url, {"lang": lang})
                self.assertEqual(len(listing.data["results"]), 2)
                query = listing_queries.captured_queries[-1]["sql"]
                self.assertIn('AS "translation_available"', query)
                self.assertNotIn('AS "public_content"', query)

                with self.assertNumQueries(1):
                    detail = self.client.get(self.detail_url(self.new_post.slug), {"lang": lang})
                self.assertEqual(detail.status_code, 200)
                self.assertIn("content", detail.data)

    def test_sitemap_reads_only_public_metadata_and_traverses_tied_dates(self):
        now = timezone.now() - timedelta(minutes=1)
        BlogPost.objects.bulk_create([
            BlogPost(
                title=f"Article {index}", slug=f"sitemap-{index}", content="Body",
                title_fa="عنوان فارسی", content_fa="متن فارسی",
                status=BlogPost.Status.PUBLISHED, published_at=now,
            )
            for index in range(251)
        ])
        url = reverse("website_api_v1:blog_sitemap")
        with self.assertNumQueries(1):
            first = self.client.get(url).data
        self.assertEqual(len(first["results"]), 250)
        cursor = parse_qs(urlsplit(first["next"]).query)["cursor"][0]
        with self.assertNumQueries(1):
            second = self.client.get(url, {"cursor": cursor}).data
        self.assertIsNone(second["next"])
        entries = first["results"] + second["results"]
        self.assertEqual(len({post["slug"] for post in entries}), 253)
        self.assertTrue(all(set(post) == {"slug", "published_at", "updated_at", "has_persian_translation"} for post in entries))
        translated_slugs = {post["slug"] for post in entries if post["has_persian_translation"]}
        self.assertEqual(translated_slugs, {f"sitemap-{index}" for index in range(251)})

    @override_settings(WEBSITE_CONTACT_RETENTION_DAYS=45)
    def test_public_policy_reads_only_configured_retention(self):
        url = reverse("website_api_v1:policy")
        with self.assertNumQueries(0):
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"contact_retention_days": 45})

    def test_unicode_slug_is_supported(self):
        post = BlogPost.objects.create(
            title="مقاله فارسی تیم‌برد",
            slug="مقاله-فارسی",
            content="# خوش آمدید",
            status=BlogPost.Status.PUBLISHED,
            published_at=timezone.now() - timedelta(hours=1),
        )

        response = self.client.get(
            self.detail_url(post.slug)
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["slug"],
            post.slug,
        )

    def test_public_blog_api_is_read_only(self):
        original_count = BlogPost.objects.count()

        create_response = self.client.post(
            self.list_url,
            {
                "title": "Unauthorized post",
                "slug": "unauthorized-post",
                "content": "Should never be created.",
            },
            format="json",
        )

        update_response = self.client.patch(
            self.detail_url(self.old_post.slug),
            {"title": "Changed title"},
            format="json",
        )

        delete_response = self.client.delete(
            self.detail_url(self.old_post.slug)
        )

        for response in (
            create_response,
            update_response,
            delete_response,
        ):
            self.assertEqual(
                response.status_code,
                status.HTTP_405_METHOD_NOT_ALLOWED,
            )

        self.assertEqual(
            BlogPost.objects.count(),
            original_count,
        )

        self.old_post.refresh_from_db()

        self.assertEqual(
            self.old_post.title,
            "First Teamboard article",
        )

    def test_unknown_article_returns_404(self):
        response = self.client.get(
            self.detail_url("does-not-exist")
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_invalid_pagination_page_returns_404(self):
        response = self.client.get(
            self.list_url,
            {"page": 9999},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_draft_with_past_publication_date_is_hidden(self):
        post = BlogPost.objects.create(
            title="Still a draft",
            slug="still-a-draft",
            content="This must remain private.",
            status=BlogPost.Status.DRAFT,
            published_at=(
                timezone.now() - timedelta(days=2)
            ),
        )

        list_response = self.client.get(self.list_url)

        self.assertNotIn(
            post.slug,
            {
                item["slug"]
                for item in list_response.data["results"]
            },
        )

        detail_response = self.client.get(
            self.detail_url(post.slug)
        )

        self.assertEqual(
            detail_response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_publication_boundary_is_inclusive(self):
        publication_time = timezone.now()

        post = BlogPost.objects.create(
            title="Publication boundary",
            slug="publication-boundary",
            content="Published at an exact moment.",
            status=BlogPost.Status.PUBLISHED,
            published_at=publication_time,
        )

        with patch(
            "website.services.timezone.now",
            return_value=(
                publication_time -
                timedelta(microseconds=1)
            ),
        ):
            before_response = self.client.get(
                self.detail_url(post.slug)
            )

        with patch(
            "website.services.timezone.now",
            return_value=publication_time,
        ):
            at_response = self.client.get(
                self.detail_url(post.slug)
            )

        self.assertEqual(
            before_response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

        self.assertEqual(
            at_response.status_code,
            status.HTTP_200_OK,
        )
