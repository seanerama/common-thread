from django.conf import settings


def feature_flags(request):
    return {
        "party_directory_enabled": settings.PARTY_DIRECTORY_ENABLED,
        "relationships_enabled": settings.RELATIONSHIPS_ENABLED,
    }
