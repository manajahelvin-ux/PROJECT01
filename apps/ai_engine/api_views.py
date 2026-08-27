"""AI Engine API views."""

from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .services import ai_service


class AnalyzeRequestSerializer(serializers.Serializer):
    url = serializers.URLField()
    html = serializers.CharField(required=False, default="")


class ChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField()
    context = serializers.CharField(required=False, default="")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def analyze_page_api(request):
    ser = AnalyzeRequestSerializer(data=request.data)
    ser.is_valid(raise_exception=True)

    result = ai_service.analyze_page(ser.validated_data.get("html", ""), ser.validated_data["url"])
    if result.get("success"):
        return Response(result)
    return Response(result, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def chat_api(request):
    ser = ChatRequestSerializer(data=request.data)
    ser.is_valid(raise_exception=True)

    result = ai_service.chat(ser.validated_data["message"], ser.validated_data.get("context", ""))
    if result.get("success"):
        return Response({"message": result["content"]})
    return Response(result, status=status.HTTP_400_BAD_REQUEST)
