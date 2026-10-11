from django.urls import path
from django.conf import settings
from strawberry.django.views import GraphQLView
from .schema import schema
from django.views.decorators.csrf import csrf_exempt

urlpatterns = [
    path(
        "graphql",
        csrf_exempt(
            GraphQLView.as_view(
                schema=schema,
                graphql_ide="graphiql" if settings.DEBUG else None,
                multipart_uploads_enabled=True,
            )
        ),
    ),
]
