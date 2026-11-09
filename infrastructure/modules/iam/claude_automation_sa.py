"""
Claude Code automation service account.

Manages the service account used by Claude Code for read-only access
to production resources for debugging and monitoring.
"""

import pulumi
import pulumi_gcp as gcp
from pulumi_gcp import serviceaccount

from config import PROJECT_ID


def create_claude_automation_service_account() -> serviceaccount.Account:
    """
    Create the Claude Code automation service account.

    This service account provides read-only access to production resources
    for debugging and monitoring purposes.

    Returns:
        serviceaccount.Account: The service account resource.
    """
    return serviceaccount.Account(
        "claude-automation-sa",
        account_id="claude-automation",
        display_name="Claude Code Automation",
        description="Service account for Claude Code CLI with read-only GCP access",
    )


def grant_claude_automation_permissions(
    service_account: serviceaccount.Account,
) -> dict:
    """
    Grant read-only permissions to the Claude automation service account.

    All permissions are read-only/viewer level to prevent accidental modifications.

    Args:
        service_account: The Claude automation service account.

    Returns:
        dict: Dictionary of IAM binding resources.
    """
    bindings = {}

    # Grant Cloud Run viewer permissions (view services, revisions, status)
    bindings["run_viewer"] = gcp.projects.IAMMember(
        "claude-automation-run-viewer",
        project=PROJECT_ID,
        role="roles/run.viewer",
        member=service_account.email.apply(lambda email: f"serviceAccount:{email}"),
    )

    # Grant Logging viewer permissions (read logs)
    bindings["logging_viewer"] = gcp.projects.IAMMember(
        "claude-automation-logging-viewer",
        project=PROJECT_ID,
        role="roles/logging.viewer",
        member=service_account.email.apply(lambda email: f"serviceAccount:{email}"),
    )

    # Grant Monitoring viewer permissions (read metrics, dashboards)
    bindings["monitoring_viewer"] = gcp.projects.IAMMember(
        "claude-automation-monitoring-viewer",
        project=PROJECT_ID,
        role="roles/monitoring.viewer",
        member=service_account.email.apply(lambda email: f"serviceAccount:{email}"),
    )

    # Grant Cloud Build viewer permissions (view build status, logs)
    bindings["cloudbuild_viewer"] = gcp.projects.IAMMember(
        "claude-automation-cloudbuild-viewer",
        project=PROJECT_ID,
        role="roles/cloudbuild.builds.viewer",
        member=service_account.email.apply(lambda email: f"serviceAccount:{email}"),
    )

    # Grant Cloud Trace viewer permissions (view distributed traces)
    bindings["cloudtrace_viewer"] = gcp.projects.IAMMember(
        "claude-automation-cloudtrace-viewer",
        project=PROJECT_ID,
        role="roles/cloudtrace.user",
        member=service_account.email.apply(lambda email: f"serviceAccount:{email}"),
    )

    # Grant Cloud Tasks viewer permissions (view queue status)
    bindings["cloudtasks_viewer"] = gcp.projects.IAMMember(
        "claude-automation-cloudtasks-viewer",
        project=PROJECT_ID,
        role="roles/cloudtasks.viewer",
        member=service_account.email.apply(lambda email: f"serviceAccount:{email}"),
    )

    # Grant Storage viewer permissions (list buckets, view metadata - not object content)
    bindings["storage_viewer"] = gcp.projects.IAMMember(
        "claude-automation-storage-viewer",
        project=PROJECT_ID,
        role="roles/storage.objectViewer",
        member=service_account.email.apply(lambda email: f"serviceAccount:{email}"),
    )

    return bindings


def grant_impersonation_permission(
    service_account: serviceaccount.Account,
) -> serviceaccount.IAMBinding:
    """
    Allow users to impersonate the Claude automation service account.

    This enables using `gcloud auth application-default login --impersonate-service-account`
    for long-lived credentials without downloadable keys.

    Args:
        service_account: The Claude automation service account.

    Returns:
        serviceaccount.IAMBinding: The IAM binding resource.
    """
    return serviceaccount.IAMBinding(
        "claude-automation-impersonation",
        service_account_id=service_account.name,
        role="roles/iam.serviceAccountTokenCreator",
        members=[
            "user:andrew@beveridge.uk",
            "user:admin@nomadkaraoke.com",
        ],
    )
