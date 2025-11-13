from rest_framework import viewsets, serializers
from catalog.models import Tool


class ToolSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tool
        fields = ["id", "name", "slug", "short_desc", "free_tier", "rating"]


class ToolViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tool.objects.all()
    serializer_class = ToolSerializer
