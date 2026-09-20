from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from admin_panel.models import AdminUser
from courses.forms import StudentSignupForm
from courses.models import StudentProfile


class StudentSignupMobileTests(TestCase):
    def _valid_data(self, **overrides):
        data = {
            "full_name": "Riya Sharma",
            "username": "riya_s",
            "email": "riya@example.com",
            "country_code": "91",
            "mobile_number": "9876543210",
            "password": "LearningBanyanPass123",
        }
        data.update(overrides)
        return data

    def test_mobile_number_is_required(self):
        form = StudentSignupForm(self._valid_data(mobile_number=""))
        self.assertFalse(form.is_valid())
        self.assertIn("mobile_number", form.errors)

    def test_invalid_mobile_is_rejected(self):
        form = StudentSignupForm(self._valid_data(mobile_number="12345"))
        self.assertFalse(form.is_valid())
        self.assertIn("mobile_number", form.errors)

    def test_signup_saves_mobile_number(self):
        form = StudentSignupForm(self._valid_data())
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        profile = StudentProfile.objects.get(user=user)
        self.assertEqual(profile.mobile_number, "+919876543210")

    def test_signup_view_rejects_missing_mobile(self):
        response = self.client.post(
            reverse("courses:student_signup"), self._valid_data(mobile_number="")
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="riya_s").exists())
        self.assertContains(response, "Mobile number")

    def test_duplicate_mobile_is_rejected(self):
        existing = User.objects.create_user(
            username="existing",
            email="existing@example.com",
            password="LearningBanyanPass123",
        )
        StudentProfile.objects.create(user=existing, mobile_number="9876543210")
        form = StudentSignupForm(
            self._valid_data(username="other_user", email="other@example.com")
        )
        self.assertFalse(form.is_valid())
        self.assertIn("mobile_number", form.errors)

    def test_plus_91_mobile_matches_existing_ten_digit_number(self):
        existing = User.objects.create_user(
            username="existing",
            email="existing@example.com",
            password="LearningBanyanPass123",
        )
        StudentProfile.objects.create(user=existing, mobile_number="9876543210")
        form = StudentSignupForm(
            self._valid_data(
                username="other_user",
                email="other@example.com",
                mobile_number="+91 98765 43210",
            )
        )
        self.assertFalse(form.is_valid())
        self.assertIn("mobile_number", form.errors)

    def test_signup_view_creates_account_immediately(self):
        response = self.client.post(
            reverse("courses:student_signup"), self._valid_data()
        )
        self.assertRedirects(response, reverse("courses:student_exams"))
        user = User.objects.get(username="riya_s")
        profile = StudentProfile.objects.get(user=user)
        self.assertEqual(profile.mobile_number, "+919876543210")
        self.assertEqual(int(self.client.session.get("_auth_user_id")), user.pk)

    def test_signup_page_includes_country_code(self):
        response = self.client.get(reverse("courses:student_signup"))
        self.assertContains(response, "India (+91)")
        self.assertContains(response, 'name="country_code"')
        self.assertContains(response, "Create account")
        self.assertNotContains(response, "Send OTP")
        self.assertNotContains(response, "one-time password")

    def test_other_country_code_is_stored(self):
        form = StudentSignupForm(
            self._valid_data(country_code="971", mobile_number="501234567")
        )
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        profile = StudentProfile.objects.get(user=user)
        self.assertEqual(profile.mobile_number, "+971501234567")


class AdminRegisteredUsersTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="admin123",
            first_name="Admin",
        )
        AdminUser.objects.create(user=self.admin)
        student = User.objects.create_user(
            username="student1",
            email="student1@example.com",
            password="LearningBanyanPass123",
            first_name="Aman",
            last_name="Singh",
        )
        StudentProfile.objects.create(user=student, mobile_number="9988776655")

    def test_dashboard_shows_registered_user_count(self):
        self.client.login(username="admin", password="admin123")
        response = self.client.get(reverse("admin_panel:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Registered Users")
        self.assertContains(response, "1")
        self.assertEqual(response.context["total_registered_users"], 1)

    def test_manage_users_lists_students_and_mobile(self):
        self.client.login(username="admin", password="admin123")
        response = self.client.get(reverse("admin_panel:manage_users"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aman Singh")
        self.assertContains(response, "student1@example.com")
        self.assertContains(response, "9988776655")
        self.assertContains(response, "1 registered")
        self.assertEqual(response.context["total_registered_users"], 1)

    def test_manage_users_search_filters_results(self):
        other = User.objects.create_user(
            username="other",
            email="other@example.com",
            password="LearningBanyanPass123",
            first_name="Neha",
        )
        StudentProfile.objects.create(user=other, mobile_number="9111222333")
        self.client.login(username="admin", password="admin123")
        response = self.client.get(reverse("admin_panel:manage_users"), {"q": "9988776655"})
        self.assertContains(response, "Aman Singh")
        self.assertNotContains(response, "Neha")
        self.assertEqual(response.context["total_registered_users"], 2)
        self.assertEqual(response.context["filtered_count"], 1)

    def test_students_cannot_open_registered_users(self):
        self.client.login(username="student1", password="LearningBanyanPass123")
        response = self.client.get(reverse("admin_panel:manage_users"), follow=True)
        self.assertNotEqual(response.request["PATH_INFO"], "/admin-panel/registered-users/")

    def test_dashboard_shows_currently_logged_in_admin(self):
        self.client.login(username="admin", password="admin123")
        response = self.client.get(reverse("admin_panel:dashboard"))
        self.assertContains(response, "Currently logged in")
        self.assertContains(response, "@admin")

    def test_manage_users_shows_currently_logged_in_admin(self):
        self.client.login(username="admin", password="admin123")
        response = self.client.get(reverse("admin_panel:manage_users"))
        self.assertContains(response, "Currently logged in")
        self.assertContains(response, "@admin")


class CurrentLoginDisplayTests(TestCase):
    def test_header_shows_logged_in_student(self):
        student = User.objects.create_user(
            username="student1",
            email="student1@example.com",
            password="LearningBanyanPass123",
            first_name="Aman",
            last_name="Singh",
        )
        StudentProfile.objects.create(user=student, mobile_number="9988776655")
        self.client.login(username="student1", password="LearningBanyanPass123")
        response = self.client.get(reverse("courses:home"))
        self.assertContains(response, "Logged in as")
        self.assertContains(response, "Aman Singh")
        self.assertContains(response, "student1")

    def test_header_hides_login_label_when_anonymous(self):
        response = self.client.get(reverse("courses:home"))
        self.assertNotContains(response, "Logged in as")
