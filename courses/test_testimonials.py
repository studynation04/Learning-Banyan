import io

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from admin_panel.models import AdminUser
from courses.models import Testimonial
from courses.testimonials import upload_error

QUOTE = (
    "Learning Banyan helped me practise past papers every week and my confidence improved."
)


def png_file(name="portrait.png"):
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), (16, 120, 176)).save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


def share_payload(**overrides):
    data = {
        "role": "student",
        "name": "Aman Singh",
        "email": "aman@example.com",
        "phone": "9988776655",
        "student_name": "",
        "class_or_course": "Class 10",
        "rating": "5",
        "message": QUOTE,
        "consent": "yes",
        "company": "",
    }
    data.update(overrides)
    return data


class TestimonialSubmissionTests(TestCase):
    def test_share_page_is_public(self):
        response = self.client.get(reverse("courses:testimonial_share"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Share your testimonial")
        self.assertContains(response, 'name="consent"')

    def test_valid_submission_stays_pending_and_off_the_website(self):
        response = self.client.post(
            reverse("courses:testimonial_share"),
            share_payload(),
            follow=False,
        )
        self.assertRedirects(response, reverse("courses:testimonial_share"))
        item = Testimonial.objects.get()
        self.assertEqual(item.status, Testimonial.STATUS_PENDING)
        self.assertEqual(item.role, Testimonial.ROLE_STUDENT)
        self.assertEqual(item.student_name, "")
        self.assertTrue(item.consent_to_publish)
        self.assertEqual(item.rating, 5)

        public = self.client.get(reverse("courses:testimonials"))
        self.assertNotContains(public, "Aman Singh")
        self.assertNotContains(public, "aman@example.com")
        home = self.client.get(reverse("courses:home"))
        self.assertNotContains(home, "Aman Singh")

    def test_parent_name_is_stored(self):
        self.client.post(
            reverse("courses:testimonial_share"),
            share_payload(
                role="parent",
                name="Priya Singh",
                email="priya@example.com",
                student_name="Aman Singh",
            ),
        )
        item = Testimonial.objects.get()
        self.assertEqual(item.role, Testimonial.ROLE_PARENT)
        self.assertEqual(item.student_name, "Aman Singh")

    def test_photo_upload_is_saved_on_a_pending_testimonial(self):
        response = self.client.post(
            reverse("courses:testimonial_share"),
            {**share_payload(), "photo": png_file()},
        )
        self.assertEqual(response.status_code, 302)
        item = Testimonial.objects.get()
        self.assertTrue(item.photo.name.startswith("testimonials/photos/"))

    def test_short_message_and_missing_consent_are_rejected(self):
        response = self.client.post(
            reverse("courses:testimonial_share"),
            share_payload(message="Too short", consent=""),
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Testimonial.objects.count(), 0)
        self.assertContains(response, "at least 20 characters", status_code=400)
        self.assertContains(response, "allow Learning Banyan", status_code=400)

    def test_bad_file_type_is_rejected(self):
        bad = SimpleUploadedFile("notes.txt", b"not a photo", content_type="text/plain")
        response = self.client.post(
            reverse("courses:testimonial_share"),
            {**share_payload(), "photo": bad},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Testimonial.objects.count(), 0)

    def test_honeypot_is_dropped(self):
        response = self.client.post(
            reverse("courses:testimonial_share"),
            share_payload(company="https://spam.example"),
        )
        self.assertRedirects(response, reverse("courses:testimonial_share"))
        self.assertEqual(Testimonial.objects.count(), 0)

    def test_oversized_photo_is_rejected_by_the_helper(self):
        uploaded = SimpleUploadedFile(
            "big.png",
            b"x" * 32,
            content_type="image/png",
        )
        uploaded.size = 6 * 1024 * 1024
        self.assertIn("5 MB", upload_error(uploaded, kind="photo"))

    def tearDown(self):
        for item in Testimonial.objects.all():
            item.delete()


class TestimonialReviewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="admin123",
        )
        AdminUser.objects.create(user=self.admin)
        self.student = User.objects.create_user(
            username="student1",
            email="student1@example.com",
            password="LearningBanyanPass123",
        )
        self.item = Testimonial.objects.create(
            role=Testimonial.ROLE_STUDENT,
            name="Aman Singh",
            email="aman@example.com",
            phone="9988776655",
            class_or_course="Class 10",
            rating=5,
            message=QUOTE,
            consent_to_publish=True,
            photo=png_file("aman-review.png"),
        )

    def review_data(self, **overrides):
        data = {
            "action": "approve",
            "name": "Aman Singh",
            "role": "student",
            "student_name": "",
            "class_or_course": "Class 10",
            "rating": "5",
            "message": "Learning Banyan made weekly past-paper practice much easier for me.",
            "display_order": "1",
            "is_featured": "on",
            "admin_note": "Checked with the family.",
        }
        data.update(overrides)
        return data

    def test_student_cannot_open_the_review_queue(self):
        self.client.login(username="student1", password="LearningBanyanPass123")
        response = self.client.get(reverse("admin_panel:manage_testimonials"), follow=True)
        self.assertNotEqual(response.request["PATH_INFO"], "/admin-panel/testimonials/")

    def _status(self, url):
        response = self.client.get(url)
        try:
            return response.status_code
        finally:
            response.close()

    def test_pending_file_is_private_until_approval(self):
        photo_url = self.item.photo.url
        self.assertEqual(self._status(photo_url), 403)

        self.client.login(username="admin", password="admin123")
        self.assertEqual(self._status(photo_url), 200)
        self.client.logout()

        self.client.login(username="student1", password="LearningBanyanPass123")
        self.assertEqual(self._status(photo_url), 403)

    def test_admin_publishes_an_edited_testimonial(self):
        self.client.login(username="admin", password="admin123")
        queue = self.client.get(reverse("admin_panel:manage_testimonials"))
        self.assertContains(queue, "Link to share")
        self.assertContains(queue, reverse("courses:testimonial_share"))
        self.assertContains(queue, "aman@example.com")

        response = self.client.post(
            reverse("admin_panel:review_testimonial", args=[self.item.pk]),
            self.review_data(),
        )
        self.assertRedirects(response, reverse("admin_panel:manage_testimonials"))
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, Testimonial.STATUS_APPROVED)
        self.assertTrue(self.item.is_featured)
        self.assertIsNotNone(self.item.published_at)
        self.assertEqual(self.item.reviewed_by, self.admin)

        self.client.logout()
        public = self.client.get(reverse("courses:testimonials"))
        self.assertContains(public, "weekly past-paper practice")
        self.assertContains(public, "Aman Singh")
        self.assertNotContains(public, "aman@example.com")
        self.assertNotContains(public, "9988776655")
        home = self.client.get(reverse("courses:home"))
        self.assertContains(home, "weekly past-paper practice")
        self.assertEqual(self._status(self.item.photo.url), 200)

    def test_rejected_testimonial_stays_off_the_website(self):
        self.client.login(username="admin", password="admin123")
        self.client.post(
            reverse("admin_panel:review_testimonial", args=[self.item.pk]),
            self.review_data(action="reject", is_featured=""),
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, Testimonial.STATUS_REJECTED)
        self.client.logout()
        public = self.client.get(reverse("courses:testimonials"))
        self.assertNotContains(public, "Aman Singh")

    def test_dashboard_counts_pending_testimonials(self):
        self.client.login(username="admin", password="admin123")
        response = self.client.get(reverse("admin_panel:dashboard"))
        self.assertEqual(response.context["pending_testimonials"], 1)
        self.assertContains(response, "Testimonials to review")

    def test_delete_removes_the_submission(self):
        self.client.login(username="admin", password="admin123")
        response = self.client.post(
            reverse("admin_panel:review_testimonial", args=[self.item.pk]),
            self.review_data(action="delete"),
        )
        self.assertRedirects(response, reverse("admin_panel:manage_testimonials"))
        self.assertFalse(Testimonial.objects.filter(pk=self.item.pk).exists())

    def tearDown(self):
        for item in list(Testimonial.objects.all()):
            item.delete()
