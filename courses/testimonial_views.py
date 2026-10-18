"""Public pages for submitting and reading testimonials."""

from django.contrib import messages
from django.shortcuts import redirect, render
from django.views import View

from .models import Testimonial
from .pagination_utils import paginate, pagination_context
from .testimonials import published_testimonials, submission_errors

SHARE_SUCCESS = (
    "Thank you. We received your testimonial and will publish it on the website "
    "after we verify it."
)


def _clean_submission(request):
    rating_raw = (request.POST.get("rating") or "").strip()
    rating = None
    if rating_raw:
        try:
            rating = int(rating_raw)
        except (TypeError, ValueError):
            rating = 0
    role = (request.POST.get("role") or "").strip().lower()
    student_name = (request.POST.get("student_name") or "").strip()
    if role != Testimonial.ROLE_PARENT:
        student_name = ""
    return {
        "role": role,
        "name": (request.POST.get("name") or "").strip(),
        "email": (request.POST.get("email") or "").strip(),
        "phone": (request.POST.get("phone") or "").strip(),
        "student_name": student_name,
        "class_or_course": (request.POST.get("class_or_course") or "").strip(),
        "rating": rating,
        "message": (request.POST.get("message") or "").replace("\x00", "").strip(),
        "consent": request.POST.get("consent") in {"on", "yes", "1", "true"},
    }


class TestimonialListView(View):
    """Approved testimonials shown on the website."""

    template_name = "courses/testimonials.html"

    def get(self, request):
        role = (request.GET.get("role") or "").strip().lower()
        items = published_testimonials()
        if role in {Testimonial.ROLE_STUDENT, Testimonial.ROLE_PARENT}:
            items = items.filter(role=role)
        else:
            role = ""
        page_obj, per_page_label, choices = paginate(request, items, default=12)
        context = {
            "testimonials": page_obj.object_list,
            "role": role,
            "total_published": published_testimonials().count(),
            **pagination_context(request, page_obj, per_page_label, choices),
        }
        return render(request, self.template_name, context)


class TestimonialShareView(View):
    """Link to share with students and parents so they can upload a testimonial."""

    template_name = "courses/testimonial_share.html"

    def get(self, request):
        return render(request, self.template_name, {"form_data": {}})

    def post(self, request):
        # Hidden field. Real visitors leave it blank; filled posts are dropped.
        if (request.POST.get("company") or "").strip():
            messages.success(request, SHARE_SUCCESS)
            return redirect("courses:testimonial_share")

        data = _clean_submission(request)
        errors = submission_errors(
            data,
            request.FILES,
            email_for_limit=data["email"],
        )
        if errors:
            for err in errors:
                messages.error(request, err)
            return render(
                request,
                self.template_name,
                {"form_data": data},
                status=400,
            )

        item = Testimonial(
            role=data["role"],
            name=data["name"],
            email=data["email"],
            phone=data["phone"][:40],
            student_name=data["student_name"],
            class_or_course=data["class_or_course"],
            rating=data["rating"],
            message=data["message"],
            consent_to_publish=True,
            status=Testimonial.STATUS_PENDING,
        )
        photo = request.FILES.get("photo")
        attachment = request.FILES.get("attachment")
        if photo:
            item.photo = photo
        if attachment:
            item.attachment = attachment
        item.save()
        messages.success(request, SHARE_SUCCESS)
        return redirect("courses:testimonial_share")
