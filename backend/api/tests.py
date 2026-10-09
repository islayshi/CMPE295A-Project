import importlib.util
import pytest
from django.conf import settings
from rest_framework.test import APIClient


def test_routing_app_not_in_installed_apps():
    """Verify that the routing app is completely deregistered from INSTALLED_APPS."""
    assert "routing" not in settings.INSTALLED_APPS
    for app in settings.INSTALLED_APPS:
        assert app != "routing" and not app.endswith(".routing")


def test_routing_endpoints_return_404():
    """Verify that deprecated routing endpoints return 404 and no longer resolve."""
    client = APIClient()
    response_post = client.post("/api/routing/evacuate/", {}, format="json")
    assert response_post.status_code == 404

    response_get = client.get("/api/routing/")
    assert response_get.status_code == 404


def test_routing_module_cannot_be_imported():
    """Verify that the routing app package has been removed from the backend directory."""
    spec = importlib.util.find_spec("routing")
    assert spec is None
