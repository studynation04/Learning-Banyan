"""Session cart for visitors and a saved cart for signed-in students."""

from decimal import Decimal

from django.db.models import F

from .models import CartItem, Course, CourseEnrollment, CourseOrder, CourseOrderItem

SESSION_KEY = "cart_course_ids"


def _session_ids(request):
    raw = request.session.get(SESSION_KEY) or []
    seen = []
    for value in raw:
        try:
            course_id = int(value)
        except (TypeError, ValueError):
            continue
        if course_id not in seen:
            seen.append(course_id)
    return seen


def _write_session_ids(request, course_ids):
    request.session[SESSION_KEY] = list(course_ids)
    request.session.modified = True


def absorb_session_cart(request):
    """Move a visitor cart onto the signed-in user. Already-enrolled courses are dropped."""
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return
    course_ids = _session_ids(request)
    if not course_ids:
        return
    valid_ids = set(Course.objects.filter(id__in=course_ids).values_list("id", flat=True))
    enrolled_ids = set(
        CourseEnrollment.objects.filter(user=user, course_id__in=valid_ids).values_list(
            "course_id", flat=True
        )
    )
    existing_ids = set(
        CartItem.objects.filter(user=user, course_id__in=valid_ids).values_list(
            "course_id", flat=True
        )
    )
    CartItem.objects.bulk_create(
        [
            CartItem(user=user, course_id=course_id)
            for course_id in course_ids
            if course_id in valid_ids
            and course_id not in enrolled_ids
            and course_id not in existing_ids
        ]
    )
    _write_session_ids(request, [])


def cart_count(request):
    try:
        absorb_session_cart(request)
        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            return CartItem.objects.filter(user=user).count()
        return len(_session_ids(request))
    except Exception:
        return 0


def cart_course_ids(request):
    absorb_session_cart(request)
    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False):
        return list(
            CartItem.objects.filter(user=user)
            .order_by("-added_at", "-id")
            .values_list("course_id", flat=True)
        )
    return _session_ids(request)


def get_cart_courses(request):
    ids = cart_course_ids(request)
    if not ids:
        return []
    courses = {course.id: course for course in Course.objects.filter(id__in=ids)}
    return [courses[course_id] for course_id in ids if course_id in courses]


def enrolled_course_ids(request):
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return set()
    return set(
        CourseEnrollment.objects.filter(user=user).values_list("course_id", flat=True)
    )


def enroll_user(user, course):
    """Create an enrollment once. Returns True when this call created it."""
    _enrollment, created = CourseEnrollment.objects.get_or_create(user=user, course=course)
    if created:
        Course.objects.filter(pk=course.pk).update(students_enrolled=F("students_enrolled") + 1)
    return created


def add_course_to_cart(request, course):
    """Return 'enrolled', 'exists', or 'added'."""
    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False):
        absorb_session_cart(request)
        if CourseEnrollment.objects.filter(user=user, course=course).exists():
            CartItem.objects.filter(user=user, course=course).delete()
            return "enrolled"
        _item, created = CartItem.objects.get_or_create(user=user, course=course)
        return "added" if created else "exists"

    ids = _session_ids(request)
    if course.id in ids:
        return "exists"
    ids.append(course.id)
    _write_session_ids(request, ids)
    return "added"


def remove_course_from_cart(request, course_id):
    try:
        course_id = int(course_id)
    except (TypeError, ValueError):
        return
    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False):
        absorb_session_cart(request)
        CartItem.objects.filter(user=user, course_id=course_id).delete()
        return
    _write_session_ids(request, [item for item in _session_ids(request) if item != course_id])


def clear_cart(request):
    user = getattr(request, "user", None)
    if user and getattr(user, "is_authenticated", False):
        CartItem.objects.filter(user=user).delete()
    _write_session_ids(request, [])


def checkout_cart(request):
    """Enroll the signed-in user in every cart course and record the order.

    Returns the courses that were newly enrolled.
    """
    courses = get_cart_courses(request)
    if not courses or not request.user.is_authenticated:
        return []
    order = CourseOrder.objects.create(user=request.user, total=Decimal("0"))
    total = Decimal("0")
    newly_enrolled = []
    for course in courses:
        price = course.sale_price or Decimal("0")
        CourseOrderItem.objects.create(
            order=order,
            course=course,
            course_title=course.title[:200],
            price=price,
        )
        total += price
        if enroll_user(request.user, course):
            newly_enrolled.append(course)
    order.total = total
    order.save(update_fields=["total"])
    clear_cart(request)
    return newly_enrolled
