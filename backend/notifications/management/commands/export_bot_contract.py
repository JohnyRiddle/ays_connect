"""Export only implemented bot and self-binding routes from their live schema."""
import json
from pathlib import Path
from django.core.management.base import BaseCommand
from django.urls import include, path
from drf_spectacular.generators import SchemaGenerator


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--output', required=True)

    def handle(self, *args, **options):
        from notifications.channel_views import TelegramLinkView, TelegramStatusView, TelegramUnlinkView
        routes = [path('api/integrations/corporate-telegram/v1/', include('notifications.bot_urls')),
                  path('api/internal/v1/notification-channels/telegram/', TelegramStatusView.as_view()),
                  path('api/internal/v1/notification-channels/telegram/link/', TelegramLinkView.as_view()),
                  path('api/internal/v1/notification-channels/telegram/unlink/', TelegramUnlinkView.as_view())]
        schema = SchemaGenerator(patterns=routes).get_schema(request=None, public=True)
        schema['info'] = {'title': 'AYS Connect corporate Telegram integration', 'version': '1.0.0'}
        schema['servers'] = [{'url': 'http://localhost:8000', 'description': 'Isolated local acceptance only'}, {'url': 'https://ays-connect.ru', 'description': 'Production base; patch NOT DEPLOYED. Staging URL must be supplied by operator.'}]
        schema['components']['schemas']['PublicError'] = {'type': 'object', 'properties': {'error': {'type': 'object', 'properties': {'code': {'type': 'string'}, 'message': {'type': 'string'}, 'details': {}}, 'required': ['code', 'message', 'details']}}, 'required': ['error']}
        for route in schema['paths'].values():
            for operation in route.values():
                for code in ('400', '401', '403', '429'):
                    operation['responses'][code] = {'description': 'Validation / credential / policy / rate error', 'content': {'application/json': {'schema': {'$ref': '#/components/schemas/PublicError'}}}}
        output = Path(options['output']); output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        self.stdout.write(f'Exported {len(schema["paths"])} implemented paths')
