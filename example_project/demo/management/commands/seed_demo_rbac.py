from django.core.management.base import BaseCommand
from django.db import transaction

from drf_unified_rbac.models import Permission, Role, RolePermission


ROLE_GRANTS = {
    "demo_viewer": {"demo.order.view"},
    "demo_operator": {"demo.order.view", "demo.order.create"},
    "demo_approver": {"demo.order.view", "demo.order.approve"},
    "demo_admin": {
        "demo.order.view",
        "demo.order.create",
        "demo.order.approve",
    },
}


class Command(BaseCommand):
    help = "Create the roles and permissions used by the example project."

    @transaction.atomic
    def handle(self, *args, **options):
        permissions = {}
        for code in sorted(set().union(*ROLE_GRANTS.values())):
            permission, _ = Permission.objects.update_or_create(
                code=code,
                defaults={"name": code, "enabled": True},
            )
            permissions[code] = permission

        for role_code, permission_codes in ROLE_GRANTS.items():
            role, _ = Role.objects.update_or_create(
                code=role_code,
                defaults={"name": role_code, "enabled": True},
            )
            for permission_code in permission_codes:
                RolePermission.objects.get_or_create(
                    role=role,
                    permission=permissions[permission_code],
                )

        self.stdout.write(self.style.SUCCESS("Demo RBAC data is ready."))

