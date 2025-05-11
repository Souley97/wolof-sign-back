from rest_framework import renderers
import json
from rest_framework.utils.serializer_helpers import ReturnDict, ReturnList

class UserRenderer(renderers.JSONRenderer):
    """
    Custom renderer to format JSON responses for the API.
    """
    charset = 'utf-8'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        response = {}

        if isinstance(data, (ReturnDict, ReturnList)):
            response = {'data': data}
        elif isinstance(data, dict) and ('detail' in data or 'non_field_errors' in data):
            response = {'errors': data}
        elif isinstance(data, dict) and 'errors' in data:
            response = data  # Preserves the existing 'errors' key structure
        else:
            response = {'data': data}

        return json.dumps(response)
