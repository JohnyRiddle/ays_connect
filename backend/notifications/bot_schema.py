from drf_spectacular.extensions import OpenApiAuthenticationExtension


class BotAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = 'notifications.bot_api.BotAuthentication'
    name = 'CorporateBotBearer'

    def get_security_definition(self, auto_schema):
        return {'type': 'http', 'scheme': 'bearer', 'description': 'Dedicated service credential. Never a Telegram bot token or employee JWT.'}


class EmployeeAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = 'accounts.authentication.ActiveEmployeeJWTAuthentication'
    name = 'EmployeeJWT'

    def get_security_definition(self, auto_schema):
        return {'type': 'http', 'scheme': 'bearer', 'bearerFormat': 'JWT', 'description': 'Authenticated employee access token. Only self-binding endpoints.'}
