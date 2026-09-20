#!/usr/bin/env python
"""
Create the default admin user for the Learning Banyan platform.
Usage: python create_admin_user.py
"""

import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth.models import User

from admin_panel.models import AdminUser

DEFAULT_USERNAME = "admin"
DEFAULT_EMAIL = "admin@learningbanyan.com"
DEFAULT_PASSWORD = "admin123"


def create_admin():
    user, created = User.objects.get_or_create(
        username=DEFAULT_USERNAME,
        defaults={
            "email": DEFAULT_EMAIL,
            "first_name": "Admin",
            "last_name": "User",
        },
    )
    user.email = DEFAULT_EMAIL
    user.first_name = user.first_name or "Admin"
    user.last_name = user.last_name or "User"
    user.is_staff = True
    user.is_superuser = True
    user.set_password(DEFAULT_PASSWORD)
    user.save()

    AdminUser.objects.get_or_create(
        user=user,
        defaults={
            "is_admin": True,
            "can_upload_csv": True,
            "can_manage_questions": True,
        },
    )

    action = "created" if created else "updated"
    print(f"Admin user {action} successfully.")
    print(f"   Username: {DEFAULT_USERNAME}")
    print(f"   Password: {DEFAULT_PASSWORD}")
    print(f"   Email: {DEFAULT_EMAIL}")
    print("\nLogin at: http://127.0.0.1:8000/login/")
    print("Admins are sent to the Admin Panel; Django admin is at /admin/.")


if __name__ == "__main__":
    create_admin()
