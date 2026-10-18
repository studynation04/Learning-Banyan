"""Admin review queue for testimonials submitted by students and parents."""

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from admin_panel.views import admin_required
from courses.models import Testimonial
from courses.pagination_utils import paginate, pagination_context


def _share_url(request):
    return request.build_absolute_uri(reverse("courses:testimonial_share"))


def _apply_edits(item, request):
    """Copy review-form fields onto the testimonial. Returns a list of errors."""
    role = (request.POST.get("role") or "").strip().lower()
    name = (request.POST.get("name") or "").strip()
    student_name = (request.POST.get("student_name") or "").strip()
    class_or_course = (request.POST.get("class_or_course") or "").strip()
    message = (request.POST.get("message") or "").replace("\x00", "").strip()
    admin_note = (request.POST.get("admin_note") or "").strip()
    rating_raw = (request.POST.get("rating") or "").strip()
    order_raw = (request.POST.get("display_order") or "").strip()

    errors = []
    if role not in {Testimonial.ROLE_STUDENT, Testimonial.ROLE_PARENT}:
        errors.append("Choose Student or Parent.")
    if not name or len(name) > 150:
        errors.append("Name is required and must be 150 characters or fewer.")
    if len(student_name) > 150:
        errors.append("Student name is too long.")
    if len(class_or_course) > 200:
        errors.append("Class or course is too long.")
    if len(message) < 10:
        errors.append("Testimonial text must be at least 10 characters.")
    elif len(message) > 3000:
        errors.append("Testimonial text is too long.")

    rating = None
    if rating_raw:
        try:
            rating = int(rating_raw)
        except (TypeError, ValueError):
            rating = 0
        if rating not in {1, 2, 3, 4, 5}:
            errors.append("Rating must be from 1 to 5, or left blank.")
            rating = item.rating

    try:
        display_order = int(order_raw or "0")
    except (TypeError, ValueError):
        display_order = 0
    if display_order < 0:
        display_order = 0
    if display_order > 9999:
        display_order = 9999

    if errors:
        return errors

    if role != Testimonial.ROLE_PARENT:
        student_name = ""
    item.role = role
    item.name = name
    item.student_name = student_name
    item.class_or_course = class_or_course
    item.message = message
    item.rating = rating
    item.display_order = display_order
    item.is_featured = request.POST.get("is_featured") in {"on", "yes", "1", "true"}
    item.admin_note = admin_note

    if request.POST.get("remove_photo") and item.photo:
        item.photo.delete(save=False)
        item.photo = None
    if request.POST.get("remove_attachment") and item.attachment:
        item.attachment.delete(save=False)
        item.attachment = None
    return []


@admin_required
def manage_testimonials(request):
    status = (request.GET.get("status") or "").strip().lower()
    role = (request.GET.get("role") or "").strip().lower()
    query = (request.GET.get("q") or "").strip()
    items = Testimonial.objects.all()
    valid_status = {choice[0] for choice in Testimonial.STATUS_CHOICES}
    if status in valid_status:
        items = items.filter(status=status)
    else:
        status = ""
    if role in {Testimonial.ROLE_STUDENT, Testimonial.ROLE_PARENT}:
        items = items.filter(role=role)
    else:
        role = ""
    if query:
        items = items.filter(
            Q(name__icontains=query)
            | Q(email__icontains=query)
            | Q(message__icontains=query)
            | Q(student_name__icontains=query)
            | Q(class_or_course__icontains=query)
        )

    page_obj, per_page_label, choices = paginate(request, items)
    context = {
        "testimonials": page_obj.object_list,
        "status": status,
        "role": role,
        "query": query,
        "share_url": _share_url(request),
        "pending_count": Testimonial.objects.filter(
            status=Testimonial.STATUS_PENDING
        ).count(),
        "approved_count": Testimonial.objects.filter(
            status=Testimonial.STATUS_APPROVED
        ).count(),
        "rejected_count": Testimonial.objects.filter(
            status=Testimonial.STATUS_REJECTED
        ).count(),
        "total_count": Testimonial.objects.count(),
        "admin_user": request.user.admin_profile,
        **pagination_context(request, page_obj, per_page_label, choices),
    }
    return render(request, "admin_panel/manage_testimonials.html", context)


@admin_required
@require_http_methods(["GET", "POST"])
def review_testimonial(request, testimonial_id):
    item = get_object_or_404(Testimonial, pk=testimonial_id)
    if request.method == "POST":
        action = (request.POST.get("action") or "").strip().lower()
        if action == "delete":
            item.delete()
            messages.success(request, "Testimonial deleted.")
            return redirect("admin_panel:manage_testimonials")
        if action not in {"approve", "reject", "pending", "save"}:
            messages.error(request, "Unknown action.")
            return redirect("admin_panel:review_testimonial", testimonial_id=item.pk)
        if action == "approve" and not item.consent_to_publish:
            messages.error(
                request,
                "This testimonial cannot be published because consent was not given.",
            )
            return redirect("admin_panel:review_testimonial", testimonial_id=item.pk)

        errors = _apply_edits(item, request)
        if errors:
            for err in errors:
                messages.error(request, err)
            return render(
                request,
                "admin_panel/review_testimonial.html",
                {
                    "item": item,
                    "share_url": _share_url(request),
                    "admin_user": request.user.admin_profile,
                },
                status=400,
            )

        now = timezone.now()
        if action == "approve":
            item.status = Testimonial.STATUS_APPROVED
            item.reviewed_by = request.user
            item.reviewed_at = now
            if not item.published_at:
                item.published_at = now
            item.save()
            messages.success(request, "Testimonial approved and published on the website.")
            return redirect("admin_panel:manage_testimonials")

        if action == "reject":
            item.status = Testimonial.STATUS_REJECTED
            item.reviewed_by = request.user
            item.reviewed_at = now
            item.save()
            messages.success(request, "Testimonial rejected. It will not appear on the website.")
            return redirect("admin_panel:manage_testimonials")

        if action == "pending":
            item.status = Testimonial.STATUS_PENDING
            item.reviewed_by = request.user
            item.reviewed_at = now
            item.save()
            messages.success(request, "Testimonial moved back to pending review.")
            return redirect("admin_panel:review_testimonial", testimonial_id=item.pk)

        item.save()
        messages.success(request, "Testimonial details saved.")
        return redirect("admin_panel:review_testimonial", testimonial_id=item.pk)

    return render(
        request,
        "admin_panel/review_testimonial.html",
        {
            "item": item,
            "share_url": _share_url(request),
            "admin_user": request.user.admin_profile,
        },
    )
