import json
import os

from django.contrib import admin
from django import forms
from django.forms.models import BaseInlineFormSet
from django.db.models import Max
from .models import (
    CourseCategory,
    Course,
    CourseContent,
    CourseEnrollment,
    CartItem,
    CourseOrder,
    CourseOrderItem,
    Exam,
    StudyMaterial,
    QuestionBank,
    Question,
    QuestionOption,
    Blog,
    Resource,
    PastPaper,
    DiscussionBoard,
    DiscussionPost,
    DiscussionReply,
    ContactMessage,
    StudentProfile,
)


# ==================== REGISTERED USERS ====================
@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "full_name",
        "email",
        "mobile_number",
        "created_at",
        "is_active",
    ]
    search_fields = [
        "user__username",
        "user__email",
        "user__first_name",
        "user__last_name",
        "mobile_number",
    ]
    list_filter = ["created_at", "user__is_active"]
    ordering = ["-created_at"]
    readonly_fields = ["created_at"]

    @admin.display(description="Name")
    def full_name(self, obj):
        return obj.user.get_full_name() or "—"

    @admin.display(description="Email")
    def email(self, obj):
        return obj.user.email or "—"

    @admin.display(boolean=True, description="Active")
    def is_active(self, obj):
        return obj.user.is_active


# ==================== COURSE CATEGORY ====================
@admin.register(CourseCategory)
class CourseCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "icon", "created_at"]
    search_fields = ["name", "description"]
    ordering = ["name"]


# ==================== COURSE CONTENT (inline + standalone) ====================
class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        if not data:
            return []
        files = data if isinstance(data, (list, tuple)) else [data]
        return [super(MultipleFileField, self).clean(item, initial) for item in files]


class CourseContentAdminForm(forms.ModelForm):
    folder_files = MultipleFileField(
        required=False,
        label="Select folder",
        widget=MultipleFileInput(attrs={"webkitdirectory": "", "directory": ""}),
    )
    folder_paths = forms.CharField(required=False, widget=forms.HiddenInput)
    content_files = MultipleFileField(required=False, label="Select files")
    video_urls = forms.CharField(
        required=False,
        label="YouTube links",
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "One YouTube URL per line"}),
    )
    exams = forms.ModelMultipleChoiceField(
        queryset=Exam.objects.none(),
        required=False,
        label="Exams",
        widget=forms.SelectMultiple(attrs={"size": 6}),
    )

    class Meta:
        model = CourseContent
        fields = ["content_type", "title", "parent", "order", "folder_files", "folder_paths", "content_files", "video_urls", "exams"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["exams"].queryset = Exam.objects.order_by("name")

    def clean(self):
        cleaned = super().clean()
        kind = cleaned.get("content_type")
        has_new_content = any((
            cleaned.get("folder_files"),
            cleaned.get("content_files"),
            cleaned.get("video_urls", "").strip(),
            cleaned.get("exams"),
        ))
        if self.instance.pk and not has_new_content:
            return cleaned
        if kind == "video" and not cleaned.get("content_files") and not cleaned.get("video_urls", "").strip():
            self.add_error("content_files", "Select video files or enter YouTube links.")
        elif kind in {"quiz", "subjective", "practice"} and not cleaned.get("exams"):
            self.add_error("exams", "Select one or more exams.")
        elif kind in {"document", "image"} and not cleaned.get("content_files"):
            self.add_error("content_files", "Select one or more files.")
        allowed = {
            "video": {"mp4", "webm", "ogg", "mov", "m4v"},
            "document": {"pdf", "doc", "docx", "txt"},
            "image": {"png", "jpg", "jpeg", "gif", "webp", "bmp"},
        }.get(kind)
        if allowed:
            for uploaded in cleaned.get("content_files") or []:
                extension = os.path.splitext(uploaded.name)[1].lower().lstrip(".")
                if extension not in allowed:
                    self.add_error("content_files", f"Unsupported file type: {uploaded.name}")
        return cleaned

    class Media:
        js = ("admin/js/course_content_inline.js",)


class CourseContentInlineFormSet(BaseInlineFormSet):
    def save_new(self, form, commit=True):
        data = form.cleaned_data
        kind = data["content_type"]
        course = self.instance
        root_parent = data.get("parent")
        created = []

        def create_item(item_kind, title, parent=None, file=None, video_url="", exam=None):
            order = (CourseContent.objects.filter(course=course, parent=parent).aggregate(m=Max("order"))["m"] or 0) + 1
            item = CourseContent.objects.create(
                course=course,
                parent=parent,
                content_type=item_kind,
                title=title[:200],
                order=order,
                file=file,
                video_url=video_url,
                exam=exam,
            )
            created.append(item)
            return item

        if kind == "folder":
            root = create_item("folder", data["title"], root_parent)
            folders = {"": root}
            try:
                paths = json.loads(data.get("folder_paths") or "[]")
            except (TypeError, ValueError):
                paths = []
            root_name = next((str(path).replace("\\", "/").strip("/").split("/")[0] for path in paths if path), "")
            for index, uploaded in enumerate(data.get("folder_files") or []):
                relative = (paths[index] if index < len(paths) else uploaded.name).replace("\\", "/")
                parts = [part for part in relative.split("/") if part not in {"", ".", ".."}]
                if len(parts) > 1 and parts[0] == root_name:
                    parts = parts[1:]
                filename = parts[-1] if parts else uploaded.name
                parent = root
                key = ""
                for dirname in parts[:-1]:
                    key = f"{key}/{dirname}"
                    if key not in folders:
                        folders[key] = create_item("folder", dirname, parent)
                    parent = folders[key]
                ext = os.path.splitext(filename)[1].lower().lstrip(".")
                item_kind = "image" if ext in {"png", "jpg", "jpeg", "gif", "webp", "bmp"} else "video" if ext in {"mp4", "webm", "ogg", "mov", "m4v"} else "document"
                create_item(item_kind, filename, parent, file=uploaded)
        elif kind in {"quiz", "subjective", "practice"}:
            exams = list(data.get("exams") or [])
            for exam in exams:
                title = data["title"] if len(exams) == 1 else f"{data['title']} — {exam.name}"
                create_item(kind, title, root_parent, exam=exam)
        else:
            files = list(data.get("content_files") or [])
            urls = [line.strip() for line in data.get("video_urls", "").splitlines() if line.strip()] if kind == "video" else []
            multiple = len(files) + len(urls) > 1
            for uploaded in files:
                title = f"{data['title']} — {os.path.basename(uploaded.name)}" if multiple else data["title"]
                create_item(kind, title, root_parent, file=uploaded)
            for index, url in enumerate(urls, 1):
                title = f"{data['title']} — Video {index}" if multiple else data["title"]
                create_item(kind, title, root_parent, video_url=url)

        form.instance = created[0]
        return created[0]


class CourseContentInline(admin.TabularInline):
    model = CourseContent
    form = CourseContentAdminForm
    formset = CourseContentInlineFormSet
    extra = 1
    fields = [
        "content_type",
        "title",
        "parent",
        "order",
        "folder_files",
        "content_files",
        "video_urls",
        "exams",
    ]
    raw_id_fields = ["parent"]
    show_change_link = True
    ordering = ["order", "id"]

    class Media:
        js = ("admin/js/course_content_inline.js",)


@admin.register(CourseContent)
class CourseContentAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "course",
        "content_type",
        "parent",
        "has_video_url",
        "has_file",
        "exam",
        "order",
        "created_at",
    ]
    list_filter = ["content_type", "course", "created_at"]
    search_fields = ["title", "description", "video_url", "course__title"]
    ordering = ["course", "order", "id"]
    raw_id_fields = ["course", "parent", "exam"]
    list_editable = ["order"]

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "course",
                    "parent",
                    "content_type",
                    "title",
                    "description",
                    "order",
                )
            },
        ),
        (
            "Video",
            {
                "fields": ("video_url", "file"),
                "description": (
                    "For YouTube: paste the full link in Video URL "
                    "(e.g. https://www.youtube.com/watch?v=…). "
                    "Or upload a video file."
                ),
            },
        ),
        (
            "Test / Exam",
            {
                "fields": ("exam",),
                "description": "Used when content type is Online Test, Subjective, or Practice.",
            },
        ),
    )

    @admin.display(boolean=True, description="YouTube")
    def has_video_url(self, obj):
        return bool((obj.video_url or "").strip())

    @admin.display(boolean=True, description="File")
    def has_file(self, obj):
        return bool(obj.file)


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ["user", "course", "added_at"]
    search_fields = ["user__username", "course__title"]
    raw_id_fields = ["user", "course"]


class CourseOrderItemInline(admin.TabularInline):
    model = CourseOrderItem
    extra = 0
    raw_id_fields = ["course"]


@admin.register(CourseOrder)
class CourseOrderAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "total", "created_at"]
    search_fields = ["user__username", "items__course_title"]
    raw_id_fields = ["user"]
    inlines = [CourseOrderItemInline]


@admin.register(CourseEnrollment)
class CourseEnrollmentAdmin(admin.ModelAdmin):
    list_display = ["user", "course", "enrolled_at"]
    list_filter = ["enrolled_at", "course"]
    search_fields = ["user__username", "user__email", "course__title"]
    raw_id_fields = ["user", "course"]
    ordering = ["-enrolled_at"]


# ==================== COURSE ====================
@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "category",
        "subcategory",
        "level",
        "instructor",
        "price",
        "students_enrolled",
        "rating",
        "created_at",
    ]
    list_filter = ["category", "level", "created_at"]
    search_fields = ["title", "description", "instructor", "subcategory"]
    ordering = ["-created_at"]
    inlines = [CourseContentInline]

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("title", "description", "category", "subcategory")},
        ),
        (
            "Pricing & Access",
            {
                "fields": ("price", "discount", "expires_on"),
                "description": "Price 0 = free. Leave Access expires empty for lifetime access.",
            },
        ),
        ("Course Details", {"fields": ("instructor", "duration", "level")}),
        ("Statistics", {"fields": ("students_enrolled", "rating")}),
        ("Media", {"fields": ("thumbnail",)}),
        (
            "Course Overview (Public Page)",
            {
                "fields": ("what_youll_learn", "prerequisites", "curriculum"),
                "description": (
                    "These show on the public course page. Enter one item per "
                    "line for 'What You'll Learn' and 'Prerequisites'. For "
                    "'Course Curriculum', use one module per line in the format "
                    "'Module 1: Description'."
                ),
            },
        ),
    )


# ==================== STUDY MATERIAL ====================
# (rest of file unchanged – keep everything below as it already was)


@admin.register(StudyMaterial)
class StudyMaterialAdmin(admin.ModelAdmin):
    list_display = ["title", "course", "material_type", "file_size", "created_at"]
    list_filter = ["material_type", "course", "created_at"]
    search_fields = ["title", "description", "course__title"]
    ordering = ["-created_at"]


class QuestionOptionInline(admin.TabularInline):
    model = QuestionOption
    extra = 0


@admin.register(QuestionBank)
class QuestionBankAdmin(admin.ModelAdmin):
    list_display = ["title", "course", "difficulty", "created_at"]
    list_filter = ["difficulty", "course", "created_at"]
    search_fields = ["title", "description", "course__title"]
    ordering = ["-created_at"]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "question_bank",
        "question_type",
        "created_at",
    ]
    list_filter = ["question_type", "question_bank", "created_at"]
    search_fields = ["question_text"]
    ordering = ["-created_at"]
    inlines = [QuestionOptionInline]


@admin.register(Blog)
class BlogAdmin(admin.ModelAdmin):
    list_display = ["title", "author", "published", "created_at", "updated_at"]
    list_filter = ["published", "created_at"]
    search_fields = ["title", "content", "author"]
    ordering = ["-created_at"]
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        ("Basic Info", {"fields": ("title", "slug", "author", "published")}),
        ("Content", {"fields": ("content", "image")}),
        ("Media Files", {"fields": ("video", "pdf")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ["title", "is_paid", "created_at"]
    list_filter = ["is_paid", "created_at"]
    search_fields = ["title", "description"]
    ordering = ["-created_at"]


@admin.register(PastPaper)
class PastPaperAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "category",
        "subject",
        "year",
        "season",
        "paper_code",
        "has_answer",
        "is_published",
        "created_at",
    ]
    list_filter = ["category", "subject", "year", "is_published", "season"]
    search_fields = ["title", "subject", "paper_code", "description"]
    ordering = ["-year", "subject", "title"]
    list_editable = ["is_published"]
    fields = [
        "title",
        "category",
        "subject",
        "year",
        "season",
        "paper_code",
        "pdf",
        "answer_pdf",
        "description",
        "is_published",
        "created_at",
        "updated_at",
    ]
    readonly_fields = ["created_at", "updated_at"]

    @admin.display(boolean=True, description="Answer")
    def has_answer(self, obj):
        return bool(obj.answer_pdf)


# ==================== QUESTION FORM (TOPIC BOARDS) ====================
@admin.register(DiscussionBoard)
class DiscussionBoardAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "order", "post_count"]
    search_fields = ["name", "description"]
    ordering = ["order", "name"]
    prepopulated_fields = {"slug": ("name",)}

    def post_count(self, obj):
        return obj.posts.count()

    post_count.short_description = "Questions"


class DiscussionReplyInline(admin.TabularInline):
    model = DiscussionReply
    extra = 0
    fields = ["user", "content", "image", "created_at"]
    readonly_fields = ["created_at"]


@admin.register(DiscussionPost)
class DiscussionPostAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "user",
        "board",
        "is_resolved",
        "reply_count",
        "created_at",
    ]
    list_filter = ["board", "is_resolved", "created_at"]
    search_fields = ["title", "content", "user__username"]
    ordering = ["-created_at"]
    inlines = [DiscussionReplyInline]

    def reply_count(self, obj):
        return obj.replies.count()

    reply_count.short_description = "Replies"


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ["subject", "name", "email", "category", "is_read", "created_at"]
    list_filter = ["category", "is_read", "created_at"]
    search_fields = ["subject", "name", "email", "message"]
    ordering = ["-created_at"]
    readonly_fields = ["created_at"]


@admin.register(DiscussionReply)
class DiscussionReplyAdmin(admin.ModelAdmin):
    list_display = ["post", "user", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["content", "user__username", "post__title"]
    ordering = ["-created_at"]
