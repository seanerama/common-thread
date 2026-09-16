from django.urls import path

from crm import views

urlpatterns = [
    path("", views.people),
    path("login/", views.login_view),
    path("logout/", views.logout_view),
    path("people/", views.people),
    path("people/new/", views.person_new),
    path("people/<str:person_id>/", views.person_detail),
    path("api/v1/people/", views.api_create),
    path("api/v1/people/<str:person_id>/", views.api_detail),
    path("health/live/", views.live),
    path("health/ready/", views.ready),
]
handler404 = views.not_found
handler500 = views.server_error
