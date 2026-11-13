"""/api/learning/mentors: one file per endpoint, one router."""

from ninja import Router

from learning.endpoints.mentors import get_home
from learning.endpoints.mentors import get_me
from learning.endpoints.mentors import get_past
from learning.endpoints.mentors import get_class
from learning.endpoints.mentors import post_request
from learning.endpoints.mentors import post_request_cancel
from learning.endpoints.mentors import post_request_pass
from learning.endpoints.mentors import post_request_feedback
from learning.endpoints.mentors import post_request_accept
from learning.endpoints.mentors import get_mentoring
from learning.endpoints.mentors import get_request_slots
from learning.endpoints.mentors import get_settings
from learning.endpoints.mentors import put_settings
from learning.endpoints.mentors import post_apply
from learning.endpoints.mentors import post_class
from learning.endpoints.mentors import get_class_edit
from learning.endpoints.mentors import put_class_edit
from learning.endpoints.mentors import post_class_teachers
from learning.endpoints.mentors import post_class_teach
from learning.endpoints.mentors import delete_class_teach
from learning.endpoints.mentors import get_admin
from learning.endpoints.mentors import put_admin_class_status
from learning.endpoints.mentors import put_admin_mentor_status
from learning.endpoints.mentors import post_admin_mentor
from learning.endpoints.mentors import get_admin_metrics
from learning.endpoints.mentors import get_class_options
from learning.endpoints.mentors import post_discord_pass
from learning.endpoints.mentors import post_discord_cancel
from learning.endpoints.mentors import post_discord_confirm
from learning.endpoints.mentors import post_discord_feedback

router = Router(tags=["Learning Center - Mentors"])

# Fixed paths before parameterised ones that could swallow them.
_MODULES = (
    get_me,
    get_past,
    get_mentoring,
    get_settings,
    put_settings,
    post_apply,
    get_admin,
    get_admin_metrics,
    get_class_options,
    post_admin_mentor,
    put_admin_mentor_status,
    put_admin_class_status,
    post_request,
    get_request_slots,
    post_request_accept,
    post_request_pass,
    post_request_cancel,
    post_request_feedback,
    post_discord_pass,
    post_discord_cancel,
    post_discord_confirm,
    post_discord_feedback,
    post_class,
    get_class_edit,
    put_class_edit,
    post_class_teachers,
    post_class_teach,
    delete_class_teach,
    get_class,
    get_home,
)
for module in _MODULES:
    view = getattr(module, module.__name__.rsplit(".", 1)[-1])
    getattr(router, module.METHOD)(module.PATH, **module.ROUTE_SPEC)(view)

__all__ = ["router"]
