from django.contrib import admin

from .models import (KnowledgeCategory, KnowledgeMaterial, MaterialAccessRule,
                     MaterialAcknowledgmentAssignment, MaterialFavorite,
                     MaterialTag, MaterialVersion, MaterialView, TTKMetadata)

admin.site.register([KnowledgeCategory, KnowledgeMaterial, MaterialVersion, MaterialAccessRule,
                     MaterialTag, MaterialView, MaterialFavorite,
                     MaterialAcknowledgmentAssignment, TTKMetadata])
