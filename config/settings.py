"""
Django settings for config project.

Local development, Vercel, Render, Docker, and Hostinger VPS via environment variables.
"""

import hashlib
import ipaddress
import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env for local development (no-op if the file is absent)
load_dotenv(BASE_DIR / ".env")

try:
    import MySQLdb  # noqa: F401
except ImportError:
    try:
        import pymysql

        pymysql.version_info = (2, 2, 1, "final", 0)
        pymysql.install_as_MySQLdb()
    except ImportError:
        pass


def _env(name, default=""):
    """Vercel often defines env vars as empty strings; treat those as unset."""
    value = os.environ.get(name)
    if value is None:
        return default
    value = str(value).strip()
    return value if value else default


def _env_int(name, default):
    raw = _env(name, "")
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_bool(name, default=False):
    raw = _env(name, "")
    if not raw:
        return default
    return raw.lower() in ("1", "true", "yes", "on")


def _csv_env(name, default=""):
    return [item.strip() for item in _env(name, default).split(",") if item.strip()]


def _hostname(value):
    """Strip scheme, path, and port from a domain or URL."""
    if not value:
        return ""
    host = value.strip()
    host = host.replace("https://", "").replace("http://", "")
    return host.split("/")[0].split(":")[0].strip()


def _is_ip_address(value):
    if not value:
        return False
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def _add_unique(seq, item):
    if item and item not in seq:
        seq.append(item)


def _origin(scheme, host, port=""):
    """Build a CSRF origin, keeping a non-default port (needed for IP:8080)."""
    if not scheme or not host:
        return ""
    port = str(port or "").strip()
    if port and not (
        (scheme == "http" and port in ("80",))
        or (scheme == "https" and port in ("443",))
    ):
        return f"{scheme}://{host}:{port}"
    return f"{scheme}://{host}"


def _parse_public_url():
    """Hostinger VPS is often IP-only: SITE_URL=http://x.x.x.x:8080."""
    site_url = _env("SITE_URL", "")
    host = _hostname(_env("PUBLIC_HOST", "") or _env("VPS_IP", ""))
    port = _env("PUBLIC_PORT", "")
    scheme = _env("PUBLIC_SCHEME", "").lower()
    if site_url:
        parsed = urlparse(site_url if "://" in site_url else f"http://{site_url}")
        host = host or (parsed.hostname or "")
        if parsed.port and not port:
            port = str(parsed.port)
        if parsed.scheme and not scheme:
            scheme = parsed.scheme.lower()
    if not scheme:
        scheme = "http" if _is_ip_address(host) else ""
    return host, port, scheme


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

def _fallback_secret_key():
    """Never fail settings import (Vercel reads this file during build)."""
    seed = "|".join(
        [
            os.environ.get("SECRET_KEY", ""),
            os.environ.get("VERCEL_PROJECT_ID", ""),
            os.environ.get("VERCEL_GIT_REPO_SLUG", "learning-banyan"),
            "learning-banyan-fallback",
        ]
    )
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = _env("SECRET_KEY", "")
if (
    not SECRET_KEY
    or SECRET_KEY.startswith("django-insecure-")
    or SECRET_KEY.lower()
    in (
        "your-secret-key-change-this-in-production",
        "changeme",
        "secret",
        "secret_key",
    )
):
    SECRET_KEY = _fallback_secret_key()

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = _env_bool("DEBUG", True)

# Local + Vercel by default. Optional SITE_DOMAIN for a custom domain.
_default_hosts = "127.0.0.1,localhost,.vercel.app"
ALLOWED_HOSTS = _csv_env("ALLOWED_HOSTS", _default_hosts)
if ".vercel.app" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(".vercel.app")
if os.environ.get("RENDER") or os.environ.get("RENDER_EXTERNAL_HOSTNAME"):
    if ".onrender.com" not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(".onrender.com")
    render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
    if render_host and render_host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(render_host)

_site_domain = _hostname(os.environ.get("SITE_DOMAIN", ""))
if _site_domain:
    _add_unique(ALLOWED_HOSTS, _site_domain)
    if _site_domain.startswith("www."):
        _add_unique(ALLOWED_HOSTS, _site_domain[4:])
    else:
        _add_unique(ALLOWED_HOSTS, f"www.{_site_domain}")

# Hostinger VPS / IP-only deploy (no domain required)
_public_host, _public_port, _public_scheme = _parse_public_url()
if _public_host:
    _add_unique(ALLOWED_HOSTS, _public_host)

if os.environ.get("VERCEL"):
    vercel_url = _hostname(os.environ.get("VERCEL_URL", ""))
    if vercel_url and vercel_url not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(vercel_url)
    vercel_branch = _hostname(os.environ.get("VERCEL_BRANCH_URL", ""))
    if vercel_branch and vercel_branch not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(vercel_branch)
    vercel_project = _hostname(os.environ.get("VERCEL_PROJECT_PRODUCTION_URL", ""))
    if vercel_project and vercel_project not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(vercel_project)

# Allow "*" only when explicitly requested (never default).
if _env("ALLOWED_HOSTS", "") == "*":
    ALLOWED_HOSTS = ["*"]

CSRF_TRUSTED_ORIGINS = _csv_env("CSRF_TRUSTED_ORIGINS")
_render_hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if _render_hostname:
    _origin = f"https://{_render_hostname}"
    if _origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(_origin)
if "https://*.vercel.app" not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.append("https://*.vercel.app")

for host in ALLOWED_HOSTS:
    if host in ("*", "localhost", "127.0.0.1") or host.startswith("."):
        continue
    for scheme in ("https", "http"):
        _add_unique(CSRF_TRUSTED_ORIGINS, _origin(scheme, host))

if _public_host:
    schemes = [_public_scheme] if _public_scheme else ["http", "https"]
    for scheme in schemes:
        _add_unique(
            CSRF_TRUSTED_ORIGINS,
            _origin(scheme, _public_host, _public_port),
        )


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "courses",
    "api",
    "admin_panel",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "courses.middleware.InlineMediaMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "courses.context_processors.user_roles",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database: DATABASE_URL if set, otherwise SQLite (copied to /tmp on Vercel).


def _build_databases():
    database_url = _env("DATABASE_URL", "")
    if database_url:
        try:
            import dj_database_url

            ssl_require = bool(os.environ.get("RENDER")) or _env_bool(
                "DATABASE_SSL_REQUIRE", False
            )
            return {
                "default": dj_database_url.config(
                    default=database_url,
                    conn_max_age=600,
                    conn_health_checks=True,
                    ssl_require=ssl_require,
                )
            }
        except Exception:
            pass

    engine = _env("DATABASE_ENGINE", "")
    if engine and ("postgresql" in engine or "postgres" in engine):
        return {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": os.environ.get("DATABASE_NAME", "learningbanyan"),
                "USER": os.environ.get("DATABASE_USER", "postgres"),
                "PASSWORD": os.environ.get("DATABASE_PASSWORD", "postgres"),
                "HOST": os.environ.get("DATABASE_HOST", "localhost"),
                "PORT": os.environ.get("DATABASE_PORT", "5432"),
            }
        }

    if engine and "mysql" in engine.lower():
        return {
            "default": {
                "ENGINE": "django.db.backends.mysql",
                "NAME": os.environ.get("DATABASE_NAME", "learningbanyan"),
                "USER": os.environ.get("DATABASE_USER", "root"),
                "PASSWORD": os.environ.get("DATABASE_PASSWORD", ""),
                "HOST": os.environ.get("DATABASE_HOST", "127.0.0.1"),
                "PORT": os.environ.get("DATABASE_PORT", "3306"),
                "OPTIONS": {
                    "charset": "utf8mb4",
                    "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
                },
            }
        }

    sqlite_name = BASE_DIR / "db.sqlite3"
    # Vercel’s function filesystem is read-only except /tmp.
    if os.environ.get("VERCEL"):
        import shutil

        tmp_db = Path("/tmp/learning_banyan.sqlite3")
        if sqlite_name.exists() and not tmp_db.exists():
            shutil.copy2(sqlite_name, tmp_db)
        sqlite_name = tmp_db
    return {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": sqlite_name,
        }
    }


DATABASES = _build_databases()

# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = "/static/"
STATIC_ROOT = Path(_env("STATIC_ROOT", str(BASE_DIR / "staticfiles")))
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []

# WhiteNoise compressed static files (Manifest optional; CompressedStaticFilesStorage
# avoids hard failures if a referenced file is missing during collectstatic)
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

MEDIA_URL = "/media/"
MEDIA_ROOT = Path(_env("MEDIA_ROOT", str(BASE_DIR / "media")))

# Question import preview can post many fields (one bank of 80+ questions
# with options/metadata). Django's default 1000 limit raises TooManyFieldsSent.
# The preview form also sends a single JSON payload; this is a safety net.
DATA_UPLOAD_MAX_NUMBER_FIELDS = _env_int("DATA_UPLOAD_MAX_NUMBER_FIELDS", 20000)
DATA_UPLOAD_MAX_MEMORY_SIZE = _env_int(
    "DATA_UPLOAD_MAX_MEMORY_SIZE", 100 * 1024 * 1024
)
FILE_UPLOAD_MAX_MEMORY_SIZE = _env_int(
    "FILE_UPLOAD_MAX_MEMORY_SIZE", 10 * 1024 * 1024
)

CORS_ALLOW_ALL_ORIGINS = _env_bool("CORS_ALLOW_ALL_ORIGINS", DEBUG)

# REST Framework Configuration
REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

# Default auto field
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = _env_bool("USE_X_FORWARDED_HOST", True)
USE_X_FORWARDED_PORT = True

if not DEBUG:
    # IP-only Hostinger VPS has no Let's Encrypt cert. Do not force HTTPS.
    _ssl_default = True
    if _public_scheme == "http" or _is_ip_address(_public_host):
        _ssl_default = False
    SECURE_SSL_REDIRECT = _env_bool("SECURE_SSL_REDIRECT", _ssl_default)
    SECURE_REDIRECT_EXEMPT = [r"^healthz/?$"]
    _secure_cookie_default = True if SECURE_SSL_REDIRECT else False
    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", _secure_cookie_default)
    CSRF_COOKIE_SECURE = _env_bool("CSRF_COOKIE_SECURE", _secure_cookie_default)
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    # SAMEORIGIN (not DENY): past papers / resource viewers embed PDFs from
    # the same host; DENY can cause blank viewers and odd client errors.
    X_FRAME_OPTIONS = _env("X_FRAME_OPTIONS", "SAMEORIGIN")
    if SECURE_SSL_REDIRECT:
        SECURE_HSTS_SECONDS = _env_int("SECURE_HSTS_SECONDS", 31536000)
        SECURE_HSTS_INCLUDE_SUBDOMAINS = True
        SECURE_HSTS_PRELOAD = True
    else:
        SECURE_HSTS_SECONDS = 0
        SECURE_HSTS_INCLUDE_SUBDOMAINS = False
        SECURE_HSTS_PRELOAD = False

_log_level = _env("LOG_LEVEL", "INFO").upper()
if _log_level not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
    _log_level = "INFO"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": _log_level,
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "courses": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "admin_panel": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
