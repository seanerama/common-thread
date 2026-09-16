from django.urls import path

from crm import views

urlpatterns = [
    path("", views.people),
    path("login/", views.login_view),
    path("logout/", views.logout_view),
    path("people/", views.people),
    path("people/new/", views.person_new),
    path("people/<str:person_id>/", views.person_detail),
    path("people/<str:person_id>/edit/", views.person_edit),
    path("people/<str:person_id>/archive/", views.person_archive),
    path("people/<str:person_id>/restore/", views.person_archive, {"archived": False}),
    path("people/<str:person_id>/contact-points/new/", views.contact_point_new),
    path(
        "people/<str:person_id>/contact-points/<str:point_id>/edit/",
        views.contact_point_edit,
    ),
    path(
        "people/<str:person_id>/contact-points/<str:point_id>/archive/",
        views.contact_point_archive,
    ),
    path("people/<str:person_id>/notes/new/", views.context_note_form),
    path("people/<str:person_id>/notes/<str:note_id>/edit/", views.context_note_form),
    path(
        "people/<str:person_id>/notes/<str:note_id>/history/",
        views.context_note_history,
    ),
    path("organizations/", views.party_list, {"kind": "organization"}),
    path("organizations/new/", views.party_new, {"kind": "organization"}),
    path("organizations/<str:party_id>/", views.party_detail, {"kind": "organization"}),
    path(
        "organizations/<str:party_id>/edit/", views.party_edit, {"kind": "organization"}
    ),
    path(
        "organizations/<str:party_id>/archive/",
        views.party_archive,
        {"kind": "organization"},
    ),
    path(
        "organizations/<str:party_id>/restore/",
        views.party_archive,
        {"kind": "organization", "archived": False},
    ),
    path("households/", views.party_list, {"kind": "household"}),
    path("households/new/", views.party_new, {"kind": "household"}),
    path("households/<str:party_id>/", views.party_detail, {"kind": "household"}),
    path("households/<str:party_id>/edit/", views.party_edit, {"kind": "household"}),
    path(
        "households/<str:party_id>/archive/", views.party_archive, {"kind": "household"}
    ),
    path(
        "households/<str:party_id>/restore/",
        views.party_archive,
        {"kind": "household", "archived": False},
    ),
    path("relationships/new/", views.relationship_new),
    path("relationships/<str:relationship_id>/", views.relationship_detail),
    path("relationships/<str:relationship_id>/edit/", views.relationship_edit),
    path("relationships/<str:relationship_id>/close/", views.relationship_close),
    path("api/v1/people/", views.api_create),
    path("api/v1/people/<str:person_id>/", views.api_detail),
    path("health/live/", views.live),
    path("health/ready/", views.ready),
]
handler404 = views.not_found
handler500 = views.server_error
