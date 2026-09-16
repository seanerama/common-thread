from django.conf import settings


def feature_flags(request):
    return {
        "party_directory_enabled": settings.PARTY_DIRECTORY_ENABLED,
        "relationships_enabled": settings.RELATIONSHIPS_ENABLED,
        "interactions_enabled": settings.INTERACTIONS_ENABLED,
        "commitments_enabled": settings.COMMITMENTS_ENABLED,
    }
