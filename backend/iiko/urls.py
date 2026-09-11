from django.urls import path
from .views import CardCheckView
from .create_views import CardCreateView, CardCreationStatusView, CardCatalogView, CardPrepareView

urlpatterns = [
    path("connections/<slug:connection_id>/card/prepare/", CardPrepareView.as_view(), name="iiko-card-prepare"),
    path("connections/<slug:connection_id>/card/catalog/", CardCatalogView.as_view(), name="iiko-card-catalog"),
    path("connections/<slug:connection_id>/card/create/", CardCreateView.as_view(), name="iiko-card-create"),
    path("connections/<slug:connection_id>/card/operations/<uuid:operation_id>/", CardCreationStatusView.as_view(), name="iiko-card-creation-status"),
    path("connections/<slug:connection_id>/card/check/", CardCheckView.as_view(), name="iiko-card-check"),
]
